"""Reddit extractor via the public .json endpoint (no OAuth required for public posts)."""

from __future__ import annotations

import re

import requests
import structlog

from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)

_HEADERS = {
    "User-Agent": "cortex-knowledge-brain/0.1 (+technijian.com)",
}


def extract(url: str, max_comments: int = 10) -> ExtractedContent | None:
    log.info("extractor.reddit.start", url=url)
    json_url = _to_json_url(url)
    if not json_url:
        return None

    try:
        resp = requests.get(json_url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("extractor.reddit.fetch_failed", url=url, error=str(exc))
        return None

    if not isinstance(data, list) or len(data) < 1:
        return None

    post = data[0]["data"]["children"][0]["data"]
    title = post.get("title", "Reddit post")
    author = post.get("author")
    body = post.get("selftext") or ""
    subreddit = post.get("subreddit")
    score = post.get("score")
    canonical = "https://www.reddit.com" + post.get("permalink", "")

    parts = [f"# {title}", ""]
    if subreddit: parts.append(f"**Subreddit:** r/{subreddit}")
    if author:    parts.append(f"**Author:** u/{author}")
    if score is not None: parts.append(f"**Score:** {score}")
    if body:      parts += ["", body]

    # Top comments
    if len(data) > 1:
        comments = data[1].get("data", {}).get("children", [])
        top = []
        for c in comments[:max_comments]:
            cd = c.get("data", {})
            ctext = cd.get("body")
            if ctext and not cd.get("stickied"):
                top.append(f"- **u/{cd.get('author','?')}** ({cd.get('score',0)} pts): {ctext}")
        if top:
            parts += ["", "## Top Comments", *top]

    return ExtractedContent(
        source_url=url,
        source_type="reddit",
        canonical_url=canonical,
        title=title,
        body_markdown="\n".join(parts).strip(),
        author=author,
        metadata={"extractor": "reddit_json", "subreddit": subreddit,
                  "score": score, "num_comments": post.get("num_comments")},
    )


def _to_json_url(url: str) -> str | None:
    # Strip query, add .json
    base = re.sub(r"\?.*$", "", url.rstrip("/"))
    if "/comments/" in base or "/r/" in base:
        return base + ".json"
    return None
