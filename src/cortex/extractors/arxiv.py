"""arXiv extractor: API for metadata + PDF text via pdfplumber."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import requests
import structlog

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.arxiv.start", url=url)
    arxiv_id = _extract_id(url)
    if not arxiv_id:
        return None

    try:
        import arxiv as arxiv_lib
        search = arxiv_lib.Search(id_list=[arxiv_id])
        result = next(arxiv_lib.Client().results(search), None)
        if not result:
            return None
    except Exception as exc:
        log.warning("extractor.arxiv.api_failed", id=arxiv_id, error=str(exc))
        return None

    title = result.title.strip()
    abstract = result.summary.strip()
    authors = ", ".join(a.name for a in result.authors)

    # Pull PDF text
    pdf_text = ""
    try:
        pdf_url = result.pdf_url
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            r = requests.get(pdf_url, timeout=60)
            r.raise_for_status()
            tmp.write(r.content)
            tmp_path = Path(tmp.name)
        pdf_text = _pdf_to_text(tmp_path)
        tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        log.warning("extractor.arxiv.pdf_failed", id=arxiv_id, error=str(exc))

    parts = [
        f"# {title}", "",
        f"**Authors:** {authors}",
        f"**Published:** {result.published.strftime('%Y-%m-%d')}",
        f"**Categories:** {', '.join(result.categories)}",
        f"**arXiv ID:** {arxiv_id}",
        "", "## Abstract", abstract,
    ]
    if pdf_text:
        parts += ["", "## Full Text", pdf_text[:50000]]

    return ExtractedContent(
        source_url=url,
        source_type="arxiv",
        canonical_url=f"https://arxiv.org/abs/{arxiv_id}",
        title=title,
        body_markdown="\n".join(parts),
        author=authors,
        published_at=result.published,
        metadata={"extractor": "arxiv+pdfplumber", "arxiv_id": arxiv_id,
                  "categories": list(result.categories)},
    )


def _extract_id(url: str) -> str | None:
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([\d.]+)(?:v\d+)?", url)
    return m.group(1) if m else None


def _pdf_to_text(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception as exc:
        log.warning("pdf.extract_failed", error=str(exc))
        return ""
