"""
FastAPI webhook server — receives /poll triggers from n8n (or any caller).

Run:
    uv run python scripts/webhook_server.py
    # or under uvicorn with workers/log config:
    uv run uvicorn scripts.webhook_server:app --host 0.0.0.0 --port 8765

Auth: every protected endpoint requires header `X-Webhook-Secret: <secret>`
where the secret comes from the WEBHOOK_SECRET env var (set in .env).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from cortex.config import get_settings, get_yaml_config

structlog.configure(processors=[structlog.dev.ConsoleRenderer()])
log = structlog.get_logger(__name__)

# Secret is read via pydantic-settings (loads from .env automatically).
WEBHOOK_SECRET = get_settings().webhook_secret

app = FastAPI(
    title="Cortex Webhook",
    description="Internal trigger surface for the Inbox Brain pipeline. "
                "Called by n8n (or any scheduler) to run a poll cycle on demand.",
    version="0.1.0",
)


def _check_secret(x_webhook_secret: str = Header(...)):
    if not WEBHOOK_SECRET:
        raise HTTPException(503, "Server has no WEBHOOK_SECRET configured")
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(401, "Bad webhook secret")


class PollResult(BaseModel):
    status: str
    exit_code: int
    duration_seconds: float
    notes_written: int
    notes_log_tail: str
    started_at: str
    finished_at: str


@app.get("/health")
def health():
    """No-auth heartbeat — confirms the process is up and DB+M365 are reachable."""
    from cortex.db.connection import get_connection
    from cortex.mail.watcher import MailWatcher
    out: dict = {"ok": True, "checks": {}}
    try:
        get_connection().execute("SELECT 1").fetchone()
        out["checks"]["sql"] = "ok"
    except Exception as exc:
        out["ok"] = False
        out["checks"]["sql"] = f"FAIL: {exc}"
    try:
        MailWatcher()._get_token()
        out["checks"]["m365"] = "ok"
    except Exception as exc:
        out["ok"] = False
        out["checks"]["m365"] = f"FAIL: {exc}"
    return out


@app.post("/poll", response_model=PollResult, dependencies=[Depends(_check_secret)])
def trigger_poll():
    """Run one poll cycle via scripts/poll.py --once and return the outcome."""
    from cortex.utils.timezone import now_pacific, fmt_pacific

    started_at = now_pacific()
    t0 = time.monotonic()
    log.info("webhook.poll.start")

    # Find the venv python next to this script
    venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    cmd = [str(venv_py), str(REPO_ROOT / "scripts" / "poll.py"), "--once"]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=env,
        cwd=str(REPO_ROOT), timeout=3000, encoding="utf-8", errors="replace",
    )
    finished_at = now_pacific()
    duration = time.monotonic() - t0

    # Parse "notes_written=N" out of the structured log
    notes_written = 0
    for line in proc.stdout.splitlines():
        if "poll.cycle.done" in line and "notes_written=" in line:
            try:
                notes_written = int(line.split("notes_written=", 1)[1].split()[0])
            except Exception:
                pass

    status = "ok" if proc.returncode == 0 else "failed"
    log_tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-40:])

    if status != "ok":
        # Cortex sends its own email alert independent of n8n
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] Poll FAILED ({proc.returncode}) at {fmt_pacific(finished_at, '%Y-%m-%d %H:%M %Z')}",
                body_markdown=(
                    f"Poll cycle failed.\n\n"
                    f"Exit code: {proc.returncode}\n"
                    f"Duration:  {duration:.1f} s\n"
                    f"Started:   {fmt_pacific(started_at)}\n"
                    f"Finished:  {fmt_pacific(finished_at)}\n\n"
                    f"--- log tail ---\n{log_tail}\n"
                ),
            )
        except Exception as exc:
            log.error("webhook.alert_email_failed", error=str(exc))

    return PollResult(
        status=status,
        exit_code=proc.returncode,
        duration_seconds=round(duration, 2),
        notes_written=notes_written,
        notes_log_tail=log_tail,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
    )


class GithubScanResult(BaseModel):
    status: str
    checked: int
    new: int
    skipped_known: int
    extract_failed: int
    auto_dr_fired: int
    duration_seconds: float
    by_category: dict


@app.post("/github-scan", response_model=GithubScanResult,
          dependencies=[Depends(_check_secret)])
def trigger_github_scan(top_n: int = 5):
    """Discover top-N trending GitHub repos per Technijian AI category,
    dedup, and feed any new ones into the ingestion pipeline.

    Idempotent — repos already in dbo.processed_links are skipped.
    """
    from cortex.utils.timezone import now_pacific
    from cortex.feeds.scan_runner import run_scan

    t0 = time.monotonic()
    log.info("webhook.github_scan.start", top_n=top_n)
    try:
        summary = run_scan(top_n=top_n, dry_run=False)
        duration = time.monotonic() - t0
        log.info("webhook.github_scan.done",
                 new=summary["new"], known=summary["skipped_known"],
                 duration=round(duration, 1))
        return GithubScanResult(
            status="ok",
            checked=summary["checked"],
            new=summary["new"],
            skipped_known=summary["skipped_known"],
            extract_failed=summary["extract_failed"],
            auto_dr_fired=summary["auto_dr_fired"],
            duration_seconds=round(duration, 2),
            by_category=summary["by_category"],
        )
    except Exception as exc:
        log.error("webhook.github_scan.failed", error=str(exc))
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] GitHub scan FAILED at {now_pacific():%Y-%m-%d %H:%M %Z}",
                body_markdown=(
                    f"GitHub scan threw an exception.\n\n"
                    f"Error: {exc}\n\n"
                    f"Duration before failure: {time.monotonic() - t0:.1f} s"
                ),
            )
        except Exception:
            pass
        raise HTTPException(500, f"GitHub scan failed: {exc}")


class RepoReviewResult(BaseModel):
    status: str
    repos_processed: int
    prs_opened: int
    no_improvements: int
    failed: int
    duration_seconds: float
    results: list


@app.post("/repo-review", response_model=RepoReviewResult,
          dependencies=[Depends(_check_secret)])
def trigger_repo_review(max_repos: int | None = None):
    """Run the daily Cortex repo-review pass over the configured allowlist.
    Opens / updates a PR per repo with knowledge/*.md improvement prompts."""
    from cortex.utils.timezone import now_pacific
    from cortex.repo_review.runner import run_daily

    t0 = time.monotonic()
    log.info("webhook.repo_review.start", max_repos=max_repos)
    try:
        summary = run_daily(max_repos=max_repos)
        duration = time.monotonic() - t0
        log.info("webhook.repo_review.done",
                 prs=summary["prs_opened"],
                 duration=round(duration, 1))
        return RepoReviewResult(
            status="ok",
            repos_processed=summary["repos_processed"],
            prs_opened=summary["prs_opened"],
            no_improvements=summary["no_improvements"],
            failed=summary["failed"],
            duration_seconds=round(duration, 2),
            results=summary["results"],
        )
    except Exception as exc:
        log.error("webhook.repo_review.failed", error=str(exc))
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] Repo review FAILED at {now_pacific():%Y-%m-%d %H:%M %Z}",
                body_markdown=(
                    f"Repo-review batch threw an exception.\n\n"
                    f"Error: {exc}\n\n"
                    f"Duration before failure: {time.monotonic() - t0:.1f} s"
                ),
            )
        except Exception:
            pass
        raise HTTPException(500, f"Repo review failed: {exc}")


class LintResult(BaseModel):
    status: str
    output_path: str
    notes_checked: int
    orphan_topics: int
    near_dup_pairs: int
    contradictions_flagged: int
    stale_topics: int
    duration_seconds: float


@app.post("/lint", response_model=LintResult, dependencies=[Depends(_check_secret)])
def trigger_lint(max_pair_checks: int = 15):
    """Daily wiki health check — finds contradictions, orphans, near-dups, stale topics.
    Writes Meta/lint-YYYY-MM-DD.md inside the vault."""
    from cortex.utils.timezone import now_pacific
    from cortex.lint.wiki_lint import run_lint

    t0 = time.monotonic()
    log.info("webhook.lint.start", max_pair_checks=max_pair_checks)
    try:
        findings = run_lint(max_pair_checks=max_pair_checks)
        duration = time.monotonic() - t0
        return LintResult(
            status="ok",
            output_path=findings.output_path,
            notes_checked=findings.stats["notes_checked"],
            orphan_topics=findings.stats["orphan_topics"],
            near_dup_pairs=findings.stats["near_dup_pairs"],
            contradictions_flagged=findings.stats["contradictions_flagged"],
            stale_topics=findings.stats["stale_topics"],
            duration_seconds=round(duration, 2),
        )
    except Exception as exc:
        log.error("webhook.lint.failed", error=str(exc))
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] Wiki lint FAILED at {now_pacific():%Y-%m-%d %H:%M %Z}",
                body_markdown=f"Lint pass threw an exception.\n\nError: {exc}",
            )
        except Exception:
            pass
        raise HTTPException(500, f"Lint failed: {exc}")


class RefreshResultModel(BaseModel):
    status: str
    themes_refreshed: int
    total_new_sources: int
    total_cost_usd: float
    failed: int
    duration_seconds: float


@app.post("/refresh-topics", response_model=RefreshResultModel,
          dependencies=[Depends(_check_secret)])
def trigger_refresh(max_themes: int | None = None):
    """Weekly curated topic refresh — time-boxed 'what's new' per evergreen
    theme in config/refresh-topics.yaml. Appends digests to
    Topics/_refresh-{slug}.md."""
    from cortex.utils.timezone import now_pacific
    from cortex.topic_refresh.runner import run_weekly_refresh

    t0 = time.monotonic()
    log.info("webhook.refresh.start", max_themes=max_themes)
    try:
        summary = run_weekly_refresh(max_themes=max_themes)
        duration = time.monotonic() - t0
        return RefreshResultModel(
            status="ok",
            themes_refreshed=summary["themes_refreshed"],
            total_new_sources=summary["total_new_sources"],
            total_cost_usd=summary["total_cost_usd"],
            failed=summary["failed"],
            duration_seconds=round(duration, 2),
        )
    except Exception as exc:
        log.error("webhook.refresh.failed", error=str(exc))
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] Topic refresh FAILED at {now_pacific():%Y-%m-%d %H:%M %Z}",
                body_markdown=f"Weekly topic refresh threw an exception.\n\nError: {exc}",
            )
        except Exception:
            pass
        raise HTTPException(500, f"Topic refresh failed: {exc}")


class ModelRefreshResult(BaseModel):
    status: str
    date: str
    dead_models: int
    recommendations: int
    proposal_note: str
    proposal_id: int | None = None
    duration_seconds: float


@app.post("/model-refresh", response_model=ModelRefreshResult,
          dependencies=[Depends(_check_secret)])
def trigger_model_refresh(liveness_only: bool = False):
    """Weekly model-refresh — liveness-check routed models + research newer/
    cheaper options. Writes a proposal to Meta/Proposals/pending/ and a
    dbo.proposed_changes row. Never auto-applies routing changes."""
    from cortex.utils.timezone import now_pacific
    from cortex.model_refresh.runner import run, run_liveness

    t0 = time.monotonic()
    log.info("webhook.model_refresh.start", liveness_only=liveness_only)
    try:
        if liveness_only:
            results = run_liveness()
            dead = [r for r in results if not r["ok"]]
            return ModelRefreshResult(
                status="ok",
                date=now_pacific().strftime("%Y-%m-%d"),
                dead_models=len(dead),
                recommendations=0,
                proposal_note="(liveness-only, no proposal written)",
                proposal_id=None,
                duration_seconds=round(time.monotonic() - t0, 2),
            )
        summary = run()
        return ModelRefreshResult(
            status="ok",
            date=summary["date"],
            dead_models=len(summary["dead_models"]),
            recommendations=len(summary["research"].get("recommendations", [])),
            proposal_note=summary["proposal_note"],
            proposal_id=summary["proposal_id"],
            duration_seconds=round(time.monotonic() - t0, 2),
        )
    except Exception as exc:
        log.error("webhook.model_refresh.failed", error=str(exc))
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] Model refresh FAILED at {now_pacific():%Y-%m-%d %H:%M %Z}",
                body_markdown=f"Weekly model refresh threw an exception.\n\nError: {exc}",
            )
        except Exception:
            pass
        raise HTTPException(500, f"Model refresh failed: {exc}")


if __name__ == "__main__":
    import uvicorn
    port = get_settings().webhook_port
    # Pass the app object directly (scripts/ isn't a Python package, so
    # the import-string form "scripts.webhook_server:app" doesn't resolve).
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
