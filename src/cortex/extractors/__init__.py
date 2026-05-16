"""Per-type content extractors.

Use `extract_for_type()` to dispatch to the right extractor by link_type.
"""

from __future__ import annotations

import structlog

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)


def extract_for_type(url: str, link_type: str) -> ExtractedContent | None:
    """Route a URL to the right extractor based on its classified link_type."""
    if link_type == "youtube":
        from cortex.extractors import youtube
        return youtube.extract(url)
    if link_type == "tiktok":
        from cortex.extractors import tiktok
        return tiktok.extract(url)
    if link_type == "reddit":
        from cortex.extractors import reddit
        return reddit.extract(url)
    if link_type == "hackernews":
        from cortex.extractors import hackernews
        return hackernews.extract(url)
    if link_type == "github":
        from cortex.extractors import github
        return github.extract(url)
    if link_type == "arxiv":
        from cortex.extractors import arxiv as arxiv_mod
        return arxiv_mod.extract(url)
    if link_type == "pdf":
        from cortex.extractors import pdf
        return pdf.extract(url)
    if link_type == "twitter":
        from cortex.extractors import twitter
        return twitter.extract(url)
    if link_type in ("instagram", "facebook"):
        # No realistic free unauthenticated path; skip gracefully.
        log.info("extractor.skip.social_blocked", url=url, link_type=link_type)
        return None
    if link_type == "article":
        from cortex.extractors import article
        return article.extract(url)

    # Unknown type → article fallback
    from cortex.extractors import article
    return article.extract(url)
