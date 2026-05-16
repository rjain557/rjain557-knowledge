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
    from datetime import datetime, timezone

    started_at = datetime.now(timezone.utc)
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
    finished_at = datetime.now(timezone.utc)
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
                subject=f"[Cortex] Poll FAILED ({proc.returncode}) at {finished_at:%Y-%m-%d %H:%M UTC}",
                body_markdown=(
                    f"Poll cycle failed.\n\n"
                    f"Exit code: {proc.returncode}\n"
                    f"Duration:  {duration:.1f} s\n"
                    f"Started:   {started_at:%Y-%m-%d %H:%M:%S UTC}\n"
                    f"Finished:  {finished_at:%Y-%m-%d %H:%M:%S UTC}\n\n"
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


if __name__ == "__main__":
    import uvicorn
    port = get_settings().webhook_port
    # Pass the app object directly (scripts/ isn't a Python package, so
    # the import-string form "scripts.webhook_server:app" doesn't resolve).
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
