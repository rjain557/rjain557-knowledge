"""Microsoft Graph mail poller — reads from the Brain folder using cert auth."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Iterator

import msal
import requests
import structlog

from cortex.config import get_settings

log = structlog.get_logger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class MailWatcher:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # ── Auth ──────────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token

        settings = self._settings
        authority = f"https://login.microsoftonline.com/{settings.m365_tenant_id}"
        private_key_pem, public_cert_pem = _load_pfx(
            settings.m365_cert_pfx_path, settings.m365_cert_pfx_password
        )
        app = msal.ConfidentialClientApplication(
            client_id=settings.m365_client_id,
            authority=authority,
            client_credential={
                "thumbprint": settings.m365_cert_thumbprint,
                "private_key": private_key_pem,
                "public_certificate": public_cert_pem,
            },
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise RuntimeError(f"MSAL token error: {result.get('error_description', result)}")

        self._token = result["access_token"]
        self._token_expiry = now + result.get("expires_in", 3600)
        log.info("mail.token_acquired", expires_in=result.get("expires_in"))
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}

    # ── Folder resolution ─────────────────────────────────────────────────

    def _get_folder_id(self) -> str:
        settings = self._settings
        mailbox = settings.m365_mailbox
        folder_name = settings.m365_folder

        url = f"{GRAPH_BASE}/users/{mailbox}/mailFolders"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        for folder in resp.json().get("value", []):
            if folder["displayName"].lower() == folder_name.lower():
                return folder["id"]

        raise ValueError(f"Mail folder '{folder_name}' not found in {mailbox}")

    # ── Polling ───────────────────────────────────────────────────────────

    def poll(self, max_messages: int = 20) -> Iterator[dict]:
        """Yield unread messages from the Brain folder, oldest first."""
        settings = self._settings
        folder_id = self._get_folder_id()

        url = (
            f"{GRAPH_BASE}/users/{settings.m365_mailbox}"
            f"/mailFolders/{folder_id}/messages"
            f"?$filter=isRead eq false"
            f"&$orderby=receivedDateTime asc"
            f"&$top={max_messages}"
            f"&$select=id,subject,from,receivedDateTime,body,isRead"
        )
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()

        messages = resp.json().get("value", [])
        log.info("mail.poll", folder=settings.m365_folder, count=len(messages))
        for msg in messages:
            yield _normalise_message(msg)

    def mark_read(self, message_id: str) -> None:
        settings = self._settings
        url = f"{GRAPH_BASE}/users/{settings.m365_mailbox}/messages/{message_id}"
        resp = requests.patch(url, headers=self._headers(), json={"isRead": True}, timeout=15)
        resp.raise_for_status()
        log.debug("mail.marked_read", message_id=message_id)

    def apply_label(self, message_id: str, label_name: str) -> None:
        """Add a category label to a message."""
        settings = self._settings
        url = f"{GRAPH_BASE}/users/{settings.m365_mailbox}/messages/{message_id}"
        resp = requests.patch(
            url,
            headers=self._headers(),
            json={"categories": [label_name]},
            timeout=15,
        )
        resp.raise_for_status()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_message(msg: dict) -> dict:
    sender_obj = msg.get("from", {}).get("emailAddress", {})
    return {
        "message_id": msg["id"],
        "subject": msg.get("subject", ""),
        "sender": sender_obj.get("address", ""),
        "sender_name": sender_obj.get("name", ""),
        "received_at": _parse_dt(msg.get("receivedDateTime")),
        "body_html": msg.get("body", {}).get("content", ""),
        "body_type": msg.get("body", {}).get("contentType", "text"),
    }


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_pfx(pfx_path: str, password: str) -> tuple[str, str]:
    """Load a PFX file and return (private_key_pem, public_cert_pem)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    with open(pfx_path, "rb") as f:
        pfx_bytes = f.read()

    private_key, certificate, _additional = pkcs12.load_key_and_certificates(
        pfx_bytes, password.encode() if password else None
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    return private_pem, public_pem
