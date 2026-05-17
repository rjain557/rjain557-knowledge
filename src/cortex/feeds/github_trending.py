"""
Discover public GitHub repos relevant to Technijian's four AI initiatives:
development, SEO, tech-support, office-ops.

Per category we run a small set of search queries against the GitHub Search
API (`/search/repositories?sort=stars`), merge the hits, dedup against
already-ingested sources by URL, and return the top N per category.

The actual ingestion (extractor → score → vault note → embedding → maybe
auto-DR) is handled by the regular pipeline once we hand it a URL list —
see scripts/scan_github.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
import structlog

from cortex.config import get_settings

log = structlog.get_logger(__name__)

GITHUB_SEARCH = "https://api.github.com/search/repositories"

# Search queries per category. Each query gets per_page=10 results; we dedup
# and rank by stars before truncating to top N per category.
#
# Time filters: `pushed:>YYYY-MM-DD` keeps us out of abandoned repos.
# `stars:>N` drops noise. Tune as needed.
CATEGORIES: dict[str, list[str]] = {
    "development": [
        "claude code skills stars:>30 pushed:>2026-01-01",
        "ai agent harness stars:>50 pushed:>2026-01-01",
        "mcp server stars:>30 pushed:>2026-01-01",
        "llm agent framework stars:>100 pushed:>2026-01-01",
        "autonomous coding agent stars:>50 pushed:>2026-01-01",
    ],
    "seo": [
        "answer engine optimization stars:>10 pushed:>2025-06-01",
        "generative engine optimization stars:>10 pushed:>2025-06-01",
        "ai seo tool stars:>30 pushed:>2025-06-01",
        "llm seo agent stars:>20 pushed:>2026-01-01",
    ],
    "tech-support": [
        "ai helpdesk stars:>30 pushed:>2025-06-01",
        "msp automation stars:>30 pushed:>2025-06-01",
        "aiops incident response stars:>30 pushed:>2025-06-01",
        "rmm automation tool stars:>50 pushed:>2025-06-01",
    ],
    "office-ops": [
        "small business ai automation stars:>30 pushed:>2025-06-01",
        "office productivity ai stars:>30 pushed:>2025-06-01",
        "msp toolkit stars:>20 pushed:>2025-06-01",
        "business workflow automation ai stars:>50 pushed:>2025-06-01",
    ],
}


@dataclass
class TrendingRepo:
    url: str
    full_name: str
    description: str
    stars: int
    pushed_at: str
    topics: list[str]
    category: str
    license: str | None


def _headers() -> dict:
    settings = get_settings()
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def _search(query: str, per_page: int = 10, retries: int = 2) -> list[dict]:
    """One GitHub search. Handles 401/403 + rate-limit with sleep+retry."""
    for attempt in range(retries + 1):
        try:
            r = requests.get(
                GITHUB_SEARCH,
                params={"q": query, "sort": "stars", "order": "desc",
                        "per_page": per_page},
                headers=_headers(),
                timeout=20,
            )
            if r.status_code == 401:
                log.warning("github.search.bad_credentials",
                            hint="GITHUB_TOKEN in .env is invalid/revoked — "
                                 "falling back to unauthenticated (10/min cap)")
                # Strip the bad token from this call and retry unauthenticated
                r = requests.get(
                    GITHUB_SEARCH,
                    params={"q": query, "sort": "stars", "order": "desc",
                            "per_page": per_page},
                    headers={"Accept": "application/vnd.github+json",
                             "X-GitHub-Api-Version": "2022-11-28"},
                    timeout=20,
                )
            if r.status_code in (403, 429):
                reset_epoch = int(r.headers.get("X-RateLimit-Reset", "0") or 0)
                now_epoch = int(time.time())
                wait = max(1, min(60, reset_epoch - now_epoch))
                log.warning("github.search.rate_limited", attempt=attempt,
                            wait_seconds=wait, reset=reset_epoch)
                if attempt < retries:
                    time.sleep(wait)
                    continue
                return []
            r.raise_for_status()
            return r.json().get("items", []) or []
        except Exception as exc:
            log.warning("github.search.error", query=query[:60],
                        attempt=attempt, error=str(exc)[:200])
            if attempt < retries:
                time.sleep(2)
                continue
            return []
    return []


def fetch_top_per_category(top_n: int = 5) -> dict[str, list[TrendingRepo]]:
    """Return {category: [TrendingRepo, ...]} with the top `top_n` per category."""
    out: dict[str, list[TrendingRepo]] = {}
    for cat, queries in CATEGORIES.items():
        merged: dict[str, TrendingRepo] = {}
        for q in queries:
            for item in _search(q):
                url = item["html_url"]
                if url in merged:
                    continue
                merged[url] = TrendingRepo(
                    url=url,
                    full_name=item["full_name"],
                    description=(item.get("description") or "").strip(),
                    stars=int(item.get("stargazers_count") or 0),
                    pushed_at=item.get("pushed_at") or "",
                    topics=item.get("topics", []) or [],
                    category=cat,
                    license=(item.get("license") or {}).get("spdx_id"),
                )
            time.sleep(0.4)  # be polite to the search API
        ranked = sorted(merged.values(), key=lambda r: -r.stars)[:top_n]
        out[cat] = ranked
        log.info("github.category.done", category=cat,
                 hits=len(merged), kept=len(ranked))
    return out
