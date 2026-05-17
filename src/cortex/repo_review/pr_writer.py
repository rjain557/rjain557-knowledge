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
    pr_number: int | None
    pr_url: str | None
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
    branch_prefix: str = "cortex-knowledge",
) -> PRResult:
    """knowledge_files = {filename inside knowledge/ : markdown content}."""
    if not knowledge_files:
        return PRResult(repo=full_name, branch="", pr_number=None,
                        pr_url=None, files_written=0, status="empty")

    token = get_settings().github_token
    if not token:
        return PRResult(repo=full_name, branch="", pr_number=None,
                        pr_url=None, files_written=0,
                        status="failed", error="GITHUB_TOKEN missing")

    today = now_pacific().strftime("%Y-%m-%d")
    branch = f"{branch_prefix}/{today}"
    clone_url = f"https://x-access-token:{token}@github.com/{full_name}.git"

    tmp = Path(tempfile.mkdtemp(prefix="cortex_pr_"))
    try:
        # Shallow clone the default branch (fast, doesn't need full history)
        r = subprocess.run(
            ["git", "clone", "--depth=1", "--branch", default_branch,
             clone_url, str(tmp / "repo")],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode != 0:
            return PRResult(repo=full_name, branch=branch, pr_number=None,
                            pr_url=None, files_written=0,
                            status="failed", error=f"clone: {r.stderr[:300]}")

        repo_dir = tmp / "repo"

        # Identity for the commits
        _git(repo_dir, "config", "user.name", "Cortex Repo Review")
        _git(repo_dir, "config", "user.email", "cortex@technijian.com")

        # Always create the branch fresh from the (shallow) default branch.
        # If the branch already exists upstream from an earlier same-day
        # run, we overwrite with --force-with-lease at push time — the
        # branch is auto-generated content, no human commits to lose.
        _git(repo_dir, "checkout", "-B", branch)

        # Write knowledge/ files
        kdir = repo_dir / "knowledge"
        kdir.mkdir(exist_ok=True)
        for fname, content in knowledge_files.items():
            (kdir / fname).write_text(content, encoding="utf-8")

        # Stage + commit + push
        _git(repo_dir, "add", "knowledge/")
        diff = _git(repo_dir, "diff", "--cached", "--name-only")
        if not diff.stdout.strip():
            shutil.rmtree(tmp, ignore_errors=True)
            return PRResult(repo=full_name, branch=branch, pr_number=None,
                            pr_url=None, files_written=0, status="no_changes")

        files_changed = len(diff.stdout.strip().splitlines())
        commit_msg = pr_title + "\n\n" + pr_body[:2000]
        c = _git(repo_dir, "commit", "-m", commit_msg)
        if c.returncode != 0 and "nothing to commit" not in c.stdout:
            shutil.rmtree(tmp, ignore_errors=True)
            return PRResult(repo=full_name, branch=branch, pr_number=None,
                            pr_url=None, files_written=files_changed,
                            status="failed",
                            error=f"commit: {c.stderr[:300]}")

        # plain --force (not --force-with-lease) because shallow clone has
        # no remote-tracking ref for the auto-generated branch to lease against
        p = _git(repo_dir, "push", "--force",
                 "--set-upstream", "origin", branch)
        if p.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return PRResult(repo=full_name, branch=branch, pr_number=None,
                            pr_url=None, files_written=files_changed,
                            status="failed",
                            error=f"push: {p.stderr[:300]}")

        # Open the PR (or no-op if already open)
        pr_number, pr_url = _open_or_get_pr(
            full_name, branch, default_branch, pr_title, pr_body,
        )

        return PRResult(repo=full_name, branch=branch, pr_number=pr_number,
                        pr_url=pr_url, files_written=files_changed,
                        status="ok")
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
