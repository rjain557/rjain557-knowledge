"""PDF extractor: fetch + pdfplumber."""

from __future__ import annotations

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import structlog

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 cortex/0.1",
    "Accept": "application/pdf,*/*;q=0.8",
}


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.pdf.start", url=url)
    try:
        r = requests.get(url, headers=_HEADERS, timeout=60, allow_redirects=True)
        r.raise_for_status()
        if "pdf" not in (r.headers.get("Content-Type", "").lower()):
            log.debug("extractor.pdf.not_pdf", content_type=r.headers.get("Content-Type"))
            return None
    except Exception as exc:
        log.warning("extractor.pdf.fetch_failed", url=url, error=str(exc))
        return None

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(r.content)
        path = Path(tmp.name)

    try:
        import pdfplumber
        title = None
        text_parts = []
        with pdfplumber.open(str(path)) as pdf:
            meta = pdf.metadata or {}
            title = meta.get("Title") or _title_from_url(url)
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t:
                    text_parts.append(t)
        text = "\n\n".join(text_parts)
    finally:
        path.unlink(missing_ok=True)

    if not text or len(text) < 100:
        return None

    return ExtractedContent(
        source_url=url,
        source_type="pdf",
        canonical_url=url,
        title=(title or "PDF").strip()[:200],
        body_markdown=f"# {title}\n\n{text[:50000]}",
        metadata={"extractor": "pdfplumber"},
    )


def _title_from_url(url: str) -> str:
    name = urlparse(url).path.rstrip("/").split("/")[-1]
    return name.replace(".pdf", "").replace("-", " ").replace("_", " ").title()
