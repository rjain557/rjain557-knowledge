"""Article extractor: trafilatura primary, requests+BS4 fallback."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
import structlog
import trafilatura
from trafilatura.settings import use_config

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# trafilatura config: favour recall over precision for markdown output
_TRAF_CFG = use_config()
_TRAF_CFG.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


def extract(url: str, timeout: int = 30) -> ExtractedContent | None:
    """Fetch and extract article content. Returns None if extraction fails."""
    log.info("extractor.article.start", url=url)
    html = _fetch_html(url, timeout=timeout)
    if not html:
        log.warning("extractor.article.fetch_failed", url=url)
        return None

    result = _try_trafilatura(url, html)
    if result and not result.is_empty:
        log.info("extractor.article.success", url=url, chars=len(result.body_markdown))
        return result

    result = _try_bs4_fallback(url, html)
    if result and not result.is_empty:
        log.info("extractor.article.bs4_fallback", url=url, chars=len(result.body_markdown))
        return result

    log.warning("extractor.article.empty", url=url)
    return None


# ── Internals ─────────────────────────────────────────────────────────────────

def _fetch_html(url: str, timeout: int) -> str | None:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        log.warning("extractor.article.http_error", url=url, error=str(exc))
        return None


def _try_trafilatura(url: str, html: str) -> ExtractedContent | None:
    try:
        result = trafilatura.extract(
            html,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            config=_TRAF_CFG,
            with_metadata=True,
        )
        if not result:
            return None

        meta = trafilatura.extract_metadata(html, default_url=url)
        title = (meta.title if meta else None) or _title_from_url(url)
        author = meta.author if meta else None
        published_at = _parse_date(meta.date if meta else None)

        return ExtractedContent(
            source_url=url,
            source_type="article",
            canonical_url=url,
            title=title,
            body_markdown=result,
            author=author,
            published_at=published_at,
            metadata={"extractor": "trafilatura"},
        )
    except Exception as exc:
        log.debug("extractor.article.trafilatura_error", url=url, error=str(exc))
        return None


def _try_bs4_fallback(url: str, html: str) -> ExtractedContent | None:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else _title_from_url(url)

        body = soup.find("article") or soup.find("main") or soup.find("body")
        text = body.get_text(separator="\n", strip=True) if body else ""
        markdown = _text_to_markdown(text, title)

        return ExtractedContent(
            source_url=url,
            source_type="article",
            canonical_url=url,
            title=title,
            body_markdown=markdown,
            metadata={"extractor": "bs4_fallback"},
        )
    except Exception as exc:
        log.debug("extractor.article.bs4_error", url=url, error=str(exc))
        return None


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/").split("/")[-1]
    return re.sub(r"[-_]", " ", path).title() or url


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _text_to_markdown(text: str, title: str) -> str:
    lines = [f"# {title}", ""]
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)
