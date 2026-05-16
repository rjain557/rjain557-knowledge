"""Twitter/X extractor — best-effort via embed API; no auth.

X aggressively blocks unauthenticated scraping. For real coverage you need
twscrape with a pool of accounts. This extractor returns whatever the public
oEmbed/syndication endpoint gives us; for hard fails, returns None gracefully.
"""

from __future__ import annotations

import re
from urllib.parse import quote

import requests
import structlog

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.twitter.start", url=url)
    tweet_id = _extract_id(url)
    if not tweet_id:
        return None

    # Try Twitter's public syndication endpoint (used by oEmbed widgets)
    try:
        resp = requests.get(
            f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code == 200 and resp.text and resp.text != "{}":
            data = resp.json()
            text = data.get("text", "")
            author = (data.get("user") or {}).get("screen_name")
            title = (text[:80] + "…") if len(text) > 80 else text
            return ExtractedContent(
                source_url=url,
                source_type="twitter",
                canonical_url=url,
                title=title or f"Tweet by @{author or 'unknown'}",
                body_markdown=f"# Tweet by @{author}\n\n{text}",
                author=author,
                metadata={"extractor": "twitter_syndication", "tweet_id": tweet_id},
            )
    except Exception as exc:
        log.debug("extractor.twitter.syndication_failed", error=str(exc))

    log.warning("extractor.twitter.blocked", url=url,
                hint="install twscrape + add an account pool for full coverage")
    return None


def _extract_id(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None
