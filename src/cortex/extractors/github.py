"""GitHub repo extractor: README + topics + recent releases via GitHub REST."""

from __future__ import annotations

import re

import requests
import structlog

from cortex.config import get_settings
from cortex.extractors.base import ExtractedContent

log = structlog.get_logger(__name__)


def extract(url: str) -> ExtractedContent | None:
    log.info("extractor.github.start", url=url)
    owner_repo = _extract_owner_repo(url)
    if not owner_repo:
        return None
    owner, repo = owner_repo
    token = get_settings().github_token
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        repo_resp = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers, timeout=15,
        )
        if repo_resp.status_code == 404:
            return None
        repo_resp.raise_for_status()
        meta = repo_resp.json()
    except Exception as exc:
        log.warning("extractor.github.api_failed", url=url, error=str(exc))
        return None

    # README
    readme = ""
    try:
        rd = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/readme",
            headers={**headers, "Accept": "application/vnd.github.raw"},
            timeout=15,
        )
        if rd.ok:
            readme = rd.text[:20000]
    except Exception:
        pass

    # Latest 5 releases
    releases_md = ""
    try:
        rel = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5",
            headers=headers, timeout=15,
        )
        if rel.ok:
            rows = []
            for r in rel.json():
                rows.append(f"- **{r.get('tag_name','?')}** ({r.get('published_at','')[:10]}): "
                            f"{(r.get('name') or '')[:80]}")
            if rows:
                releases_md = "\n".join(rows)
    except Exception:
        pass

    title = f"{owner}/{repo}: {meta.get('description','')}".strip(": ")
    parts = [
        f"# {owner}/{repo}", "",
        meta.get("description") or "",
        "",
        f"- **Stars:** {meta.get('stargazers_count',0)}",
        f"- **Forks:** {meta.get('forks_count',0)}",
        f"- **Language:** {meta.get('language','?')}",
        f"- **License:** {(meta.get('license') or {}).get('spdx_id','?')}",
        f"- **Topics:** {', '.join(meta.get('topics', []))}",
        f"- **Updated:** {meta.get('updated_at','')[:10]}",
    ]
    if releases_md:
        parts += ["", "## Recent Releases", releases_md]
    if readme:
        parts += ["", "## README", readme]

    return ExtractedContent(
        source_url=url,
        source_type="github",
        canonical_url=meta.get("html_url") or url,
        title=title[:200],
        body_markdown="\n".join(parts).strip(),
        author=owner,
        metadata={"extractor": "github_rest", "stars": meta.get("stargazers_count"),
                  "language": meta.get("language"),
                  "topics": meta.get("topics", [])},
    )


def _extract_owner_repo(url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com/([^/]+)/([^/?#]+)", url)
    if not m:
        return None
    repo = m.group(2).rstrip(".git")
    return m.group(1), repo
