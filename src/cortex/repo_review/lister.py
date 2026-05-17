"""Pick which repos to review this cycle + pull context for each.

Reads `config/reviewed-repos.yaml` for the allowlist. Tracks last-reviewed
date in `dbo.repo_reviews` (new helper table) so each repo is reviewed at
the configured cadence and we don't burn budget on the same repo twice.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests
import structlog
import yaml

from cortex.config import get_settings

log = structlog.get_logger(__name__)
GITHUB_API = "https://api.github.com"


def _headers() -> dict:
    s = get_settings()
    h = {"Accept": "application/vnd.github+json",
         "X-GitHub-Api-Version": "2022-11-28"}
    if s.github_token:
        h["Authorization"] = f"Bearer {s.github_token}"
    return h


def load_config() -> dict:
    settings = get_settings()
    cfg_path = Path("config/reviewed-repos.yaml")
    if not cfg_path.is_absolute():
        # Walk up from the cortex package to the repo root
        from cortex import __file__ as cortex_init
        repo_root = Path(cortex_init).resolve().parents[2]
        cfg_path = repo_root / "config" / "reviewed-repos.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class RepoContext:
    full_name: str
    domain: str
    default_branch: str
    description: str
    language: str | None
    readme: str
    recent_commits: list[dict]
    top_files: list[str]
    sample_files: dict[str, str]   # path -> first ~3000 chars


def get_repo_context(full_name: str, *, max_files: int = 25,
                     sample_size: int = 3) -> RepoContext | None:
    log.info("repo_review.fetch", repo=full_name)
    owner, repo = full_name.split("/", 1)

    # Repo metadata
    r = requests.get(f"{GITHUB_API}/repos/{full_name}",
                     headers=_headers(), timeout=20)
    if not r.ok:
        log.warning("repo_review.meta_failed", repo=full_name,
                    status=r.status_code)
        return None
    meta = r.json()
    default_branch = meta.get("default_branch", "master")

    # README
    readme = ""
    try:
        rr = requests.get(
            f"{GITHUB_API}/repos/{full_name}/readme",
            headers={**_headers(), "Accept": "application/vnd.github.raw"},
            timeout=15,
        )
        if rr.ok:
            readme = rr.text[:15000]
    except Exception:
        pass

    # Last 30 commits
    commits: list[dict] = []
    try:
        rc = requests.get(f"{GITHUB_API}/repos/{full_name}/commits",
                          headers=_headers(),
                          params={"per_page": 30}, timeout=20)
        if rc.ok:
            for c in rc.json():
                commits.append({
                    "sha": c.get("sha", "")[:7],
                    "date": (c.get("commit", {}).get("author", {})
                             .get("date", ""))[:10],
                    "author": c.get("commit", {}).get("author", {}).get("name", ""),
                    "message": (c.get("commit", {}).get("message", "")
                                .split("\n", 1)[0])[:150],
                })
    except Exception as exc:
        log.warning("repo_review.commits_failed", error=str(exc)[:200])

    # Top-level tree
    top_files: list[str] = []
    sample_files: dict[str, str] = {}
    try:
        rt = requests.get(
            f"{GITHUB_API}/repos/{full_name}/git/trees/{default_branch}",
            headers=_headers(), timeout=20,
        )
        if rt.ok:
            entries = rt.json().get("tree", [])
            top_files = [e["path"] for e in entries if e["type"] in ("blob", "tree")]
            # Sample a few likely-important files for the analyzer to see
            wanted = {"README.md", "package.json", "pyproject.toml",
                      "requirements.txt", "setup.py", "Cargo.toml",
                      ".gitignore", "tsconfig.json", "next.config.js"}
            picks = [p for p in top_files if p in wanted][:sample_size]
            for p in picks:
                try:
                    rb = requests.get(
                        f"{GITHUB_API}/repos/{full_name}/contents/{p}",
                        headers=_headers(), timeout=15,
                    )
                    if rb.ok:
                        body = rb.json()
                        if body.get("encoding") == "base64":
                            data = base64.b64decode(body["content"]).decode(
                                "utf-8", errors="replace")
                            sample_files[p] = data[:3000]
                except Exception:
                    continue
    except Exception as exc:
        log.warning("repo_review.tree_failed", error=str(exc)[:200])

    return RepoContext(
        full_name=full_name,
        domain="",   # injected later from config
        default_branch=default_branch,
        description=(meta.get("description") or "")[:500],
        language=meta.get("language"),
        readme=readme,
        recent_commits=commits[:30],
        top_files=top_files[:max_files],
        sample_files=sample_files,
    )
