"""HN extractor via Algolia API (free, no auth)."""

from __future__ import annotations

import re

import requests
import structlog

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.hn.start", url=url)
    item_id = _extract_id(url)
    if not item_id:
        return None

    try:
        resp = requests.get(
            f"https://hn.algolia.com/api/v1/items/{item_id}", timeout=15
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("extractor.hn.fetch_failed", url=url, error=str(exc))
        return None

    title = data.get("title") or f"HN {item_id}"
    author = data.get("author")
    text = data.get("text") or ""
    points = data.get("points")
    story_url = data.get("url")

    parts = [f"# {title}", ""]
    if author:    parts.append(f"**Author:** {author}")
    if points is not None: parts.append(f"**Points:** {points}")
    if story_url: parts.append(f"**URL:** {story_url}")
    if text:      parts += ["", text]

    # Flatten top comments (one level deep)
    def flatten(node, depth=0):
        out = []
        for child in node.get("children", []) or []:
            ctext = child.get("text") or ""
            if ctext:
                out.append(f"- **{child.get('author','?')}**: {ctext[:500]}")
            if depth < 1:
                out.extend(flatten(child, depth + 1))
        return out
    comments = flatten(data)[:20]
    if comments:
        parts += ["", "## Top Comments", *comments]

    return ExtractedContent(
        source_url=url,
        source_type="hackernews",
        canonical_url=f"https://news.ycombinator.com/item?id={item_id}",
        title=title,
        body_markdown="\n".join(parts).strip(),
        author=author,
        metadata={"extractor": "hn_algolia", "points": points,
                  "story_url": story_url},
    )


def _extract_id(url: str) -> int | None:
    m = re.search(r"id=(\d+)", url)
    return int(m.group(1)) if m else None
