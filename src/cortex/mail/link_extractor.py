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

# Ordered classification patterns: first match wins
_CLASSIFIERS: list[tuple[str, re.Pattern]] = [
    ("arxiv",      re.compile(r"arxiv\.org/abs/|arxiv\.org/pdf/")),
    ("youtube",    re.compile(r"youtube\.com/watch|youtu\.be/|youtube\.com/shorts/")),
    ("tiktok",     re.compile(r"tiktok\.com/")),
    ("reddit",     re.compile(r"reddit\.com/r/|reddit\.com/comments/|redd\.it/")),
    ("hackernews", re.compile(r"news\.ycombinator\.com/")),
    ("github",     re.compile(r"github\.com/[^/]+/[^/]+")),
    ("twitter",    re.compile(r"twitter\.com/[^/]+/status/|x\.com/[^/]+/status/")),
    ("instagram",  re.compile(r"instagram\.com/(p|reel)/")),
    ("facebook",   re.compile(r"facebook\.com/")),
    ("pdf",        re.compile(r"\.pdf(\?|$)", re.IGNORECASE)),
]


@dataclass
class ExtractedLink:
    url: str
    link_type: str  # arxiv | youtube | tiktok | reddit | hackernews | github |
                    # twitter | instagram | facebook | pdf | article


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
    url = re.sub(r"[?&](utm_[^&]+|mc_cid=[^&]+|mc_eid=[^&]+)", "", url)
    return url


def _is_http(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _classify(url: str) -> str:
    for name, pattern in _CLASSIFIERS:
        if pattern.search(url):
            return name
    return "article"
