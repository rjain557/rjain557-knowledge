"""Clone the target repo, write knowledge/*.md, commit + push a branch,
and open a PR. Uses the github PAT from cortex.config (scope `repo`).

Idempotency: branch name includes the run date so re-runs on the same
day update the existing branch + PR; runs on a different day open a
fresh PR.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests
import structlog

from cortex.config import get_settings
from cortex.utils.timezone import now_pacific

log = structlog.get_logger(__name__)
GITHUB_API = "https://api.github.com"


@dataclass
class PRResult:
    repo: str
    branch: str
    pr_number: int | None     # always None in direct-commit mode
    pr_url: str | None        # commit URL in direct-commit mode
    files_written: int
    status: str
    error: str | None = None


def _git(repo_dir: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo_dir), *args],
                          capture_output=True, text=True, timeout=120,
                          env=env)


def _gh_headers() -> dict:
    s = get_settings()
    return {"Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {s.github_token}"}


def write_pr(
    *, full_name: str, default_branch: str,
    knowledge_files: dict[str, str], pr_title: str, pr_body: str,
    branch_prefix: str = "cortex-knowledge",   # kept for API compatibility; ignored
) -> PRResult:
    """Commit `knowledge/*.md` files directly to the repo's default branch.

    Per user directive (2026-05-20): no PR review step — push knowledge/
    straight to master/main. If branch-protection rules require PRs, the
    push will fail and the run is marked failed (the user can then
    relax protection for the path or open the PR manually).

    knowledge_files = {filename inside knowledge/ : markdown content}.
    """
    if not knowledge_files:
        return PRResult(repo=full_name, branch=default_branch, pr_number=None,
                        pr_url=None, files_written=0, status="empty")

    token = get_settings().github_token
    if not token:
        return PRResult(repo=full_name, branch=default_branch, pr_number=None,
                        pr_url=None, files_written=0,
                        status="failed", error="GITHUB_TOKEN missing")

    clone_url = f"https://x-access-token:{token}@github.com/{full_name}.git"

    tmp = Path(tempfile.mkdtemp(prefix="cortex_pr_"))
    try:
        # Shallow clone the default branch (fast, no history needed)
        r = subprocess.run(
            ["git", "clone", "--depth=1", "--branch", default_branch,
             clone_url, str(tmp / "repo")],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            return PRResult(repo=full_name, branch=default_branch,
                            pr_number=None, pr_url=None, files_written=0,
                            status="failed", error=f"clone: {r.stderr[:300]}")

        repo_dir = tmp / "repo"
        _git(repo_dir, "config", "user.name", "Cortex Repo Review")
        _git(repo_dir, "config", "user.email", "cortex@technijian.com")

        # Stay on the default branch — no feature branch.
        # Write knowledge/ files
        kdir = repo_dir / "knowledge"
        kdir.mkdir(exist_ok=True)
        for fname, content in knowledge_files.items():
            (kdir / fname).write_text(content, encoding="utf-8")

        _git(repo_dir, "add", "knowledge/")
        diff = _git(repo_dir, "diff", "--cached", "--name-only")
        if not diff.stdout.strip():
            shutil.rmtree(tmp, ignore_errors=True)
            return PRResult(repo=full_name, branch=default_branch,
                            pr_number=None, pr_url=None,
                            files_written=0, status="no_changes")

        files_changed = len(diff.stdout.strip().splitlines())
        commit_msg = pr_title + "\n\n" + pr_body[:2000]
        c = _git(repo_dir, "commit", "-m", commit_msg)
        if c.returncode != 0 and "nothing to commit" not in c.stdout:
            shutil.rmtree(tmp, ignore_errors=True)
            return PRResult(repo=full_name, branch=default_branch,
                            pr_number=None, pr_url=None,
                            files_written=files_changed,
                            status="failed",
                            error=f"commit: {c.stderr[:300]}")

        # Push the default branch. NOT --force — if there are concurrent
        # commits, fail loud rather than overwrite real human work.
        p = _git(repo_dir, "push", "origin", default_branch)
        if p.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return PRResult(repo=full_name, branch=default_branch,
                            pr_number=None, pr_url=None,
                            files_written=files_changed,
                            status="failed",
                            error=f"push (branch protection?): {p.stderr[:400]}")

        # Grab the new commit SHA for a clickable URL
        sha = _git(repo_dir, "rev-parse", "HEAD").stdout.strip()[:40]
        commit_url = f"https://github.com/{full_name}/commit/{sha}" if sha else None

        return PRResult(repo=full_name, branch=default_branch,
                        pr_number=None, pr_url=commit_url,
                        files_written=files_changed, status="ok")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _open_or_get_pr(full_name: str, branch: str, base: str,
                    title: str, body: str) -> tuple[int | None, str | None]:
    # Is there already an open PR for this head?
    r = requests.get(f"{GITHUB_API}/repos/{full_name}/pulls",
                     headers=_gh_headers(),
                     params={"head": f"{full_name.split('/')[0]}:{branch}",
                             "state": "open"}, timeout=15)
    if r.ok and r.json():
        pr = r.json()[0]
        # Refresh title + body so re-runs reflect the latest analysis
        requests.patch(
            f"{GITHUB_API}/repos/{full_name}/pulls/{pr['number']}",
            headers=_gh_headers(),
            json={"title": title, "body": body[:60000]},
            timeout=15,
        )
        return pr.get("number"), pr.get("html_url")

    # Create new
    r = requests.post(
        f"{GITHUB_API}/repos/{full_name}/pulls",
        headers=_gh_headers(),
        json={"title": title, "body": body[:60000],
              "head": branch, "base": base, "draft": False},
        timeout=20,
    )
    if not r.ok:
        log.warning("repo_review.pr_create_failed", repo=full_name,
                    status=r.status_code, body=r.text[:400])
        return None, None
    pr = r.json()
    return pr.get("number"), pr.get("html_url")
