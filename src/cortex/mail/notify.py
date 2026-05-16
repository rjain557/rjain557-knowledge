"""Send alert/notification emails from knowledge@technijian.com via Graph."""

from __future__ import annotations

import requests
import structlog

from cortex.mail.watcher import GRAPH_BASE, MailWatcher

log = structlog.get_logger(__name__)


def send_alert(
    subject: str,
    body_markdown: str,
    to: str = "rjain@technijian.com",
    cc: list[str] | None = None,
) -> bool:
    """Send a plain-text email via Microsoft Graph using the existing Cortex cert."""
    try:
        watcher = MailWatcher()
        token = watcher._get_token()
        sender = watcher._settings.m365_mailbox

        payload = {
            "message": {
                "subject": subject[:255],
                "body": {"contentType": "Text", "content": body_markdown[:50000]},
                "toRecipients": [{"emailAddress": {"address": to}}],
                "ccRecipients": [{"emailAddress": {"address": c}} for c in (cc or [])],
            },
            "saveToSentItems": "false",
        }
        resp = requests.post(
            f"{GRAPH_BASE}/users/{sender}/sendMail",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload, timeout=30,
        )
        if resp.status_code in (200, 202):
            log.info("notify.email_sent", to=to, subject=subject[:60])
            return True
        log.warning("notify.email_failed", status=resp.status_code, body=resp.text[:300])
        return False
    except Exception as exc:
        log.error("notify.email_exception", error=str(exc))
        return False
