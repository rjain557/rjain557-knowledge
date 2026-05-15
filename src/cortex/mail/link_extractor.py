"""Extract, classify, and deduplicate URLs from email HTML bodies."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import structlog

log = structlog.get_logger(__name__)

# URLs containing these patterns are ignored
_SKIP_PATTERNS = re.compile(
    r"unsubscribe|optout|opt-out|mailto:|tel:|"
    r"click\.email|track\.|tracking\.|open\.email|"
    r"list-manage|mailchimp|sendgrid|mandrillapp|"
    r"linkedin\.com/uas/|twitter\.com/i/|"
    r"pixel\.|beacon\.|img\.",
    re.IGNORECASE,
)

_ARXIV    = re.compile(r"arxiv\.org/abs/|arxiv\.org/pdf/")
_YOUTUBE  = re.compile(r"youtube\.com/watch|youtu\.be/")
_GITHUB   = re.compile(r"github\.com/[^/]+/[^/]+")
_PDF      = re.compile(r"\.pdf(\?|$)", re.IGNORECASE)


@dataclass
class ExtractedLink:
    url: str
    link_type: str  # article | arxiv | youtube | github | pdf | other


def extract_links(html: str, plain_text: str = "") -> list[ExtractedLink]:
    """Return classified, deduplicated links from email body."""
    seen: set[str] = set()
    results: list[ExtractedLink] = []

    urls = _extract_hrefs(html) + _extract_urls_from_text(plain_text)

    for raw_url in urls:
        url = _normalise(raw_url)
        if not url or url in seen:
            continue
        if _SKIP_PATTERNS.search(url):
            continue
        if not _is_http(url):
            continue
        seen.add(url)
        results.append(ExtractedLink(url=url, link_type=_classify(url)))

    log.debug("mail.links_extracted", total=len(results))
    return results


# ── Internals ─────────────────────────────────────────────────────────────────

def _extract_hrefs(html: str) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    return [a.get("href", "") for a in soup.find_all("a", href=True)]


def _extract_urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r"https?://\S+", text)


def _normalise(url: str) -> str:
    url = url.strip().rstrip(".,;)")
    # Remove common tracking query params
    url = re.sub(r"[?&](utm_[^&]+|mc_cid=[^&]+|mc_eid=[^&]+)", "", url)
    return url


def _is_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _classify(url: str) -> str:
    if _ARXIV.search(url):
        return "arxiv"
    if _YOUTUBE.search(url):
        return "youtube"
    if _GITHUB.search(url):
        return "github"
    if _PDF.search(url):
        return "pdf"
    return "article"
