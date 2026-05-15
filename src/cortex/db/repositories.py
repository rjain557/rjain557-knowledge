"""All SQL Server access for Cortex. No raw pyodbc calls outside this module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from cortex.db.connection import get_connection, transaction

log = structlog.get_logger(__name__)


# ── Emails ────────────────────────────────────────────────────────────────────

def is_email_processed(message_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM dbo.processed_emails WHERE message_id = ?", message_id
    ).fetchone()
    return row is not None


def record_email(
    message_id: str,
    sender: str,
    subject: str,
    received_at: datetime,
    link_count: int,
) -> int:
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO dbo.processed_emails
                   (message_id, sender, subject, received_at, link_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            message_id, sender, subject, received_at, link_count,
        )
        row = conn.execute("SELECT SCOPE_IDENTITY() AS id").fetchone()
        return int(row.id)


# ── Links ─────────────────────────────────────────────────────────────────────

def is_link_processed(url: str) -> bool:
    conn = get_connection()
    import hashlib
    url_hash = hashlib.sha256(url.encode()).digest()
    row = conn.execute(
        "SELECT 1 FROM dbo.processed_links WHERE url_hash = ?", pyodbc_binary(url_hash)
    ).fetchone()
    return row is not None


def record_link(email_id: int | None, url: str, link_type: str) -> int:
    import hashlib
    url_hash = hashlib.sha256(url.encode()).digest()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO dbo.processed_links (email_id, url, url_hash, link_type)
            VALUES (?, ?, ?, ?)
            """,
            email_id, url, pyodbc_binary(url_hash), link_type,
        )
        row = conn.execute("SELECT SCOPE_IDENTITY() AS id").fetchone()
        return int(row.id)


# ── Sources ───────────────────────────────────────────────────────────────────

def upsert_source(
    url: str,
    source_type: str,
    title: str | None,
    author: str | None,
    published_at: datetime | None,
    body_markdown: str,
    metadata: dict | None = None,
    feed_id: str | None = None,
) -> int:
    import hashlib
    url_hash = hashlib.sha256(url.encode()).digest()

    with transaction() as conn:
        existing = conn.execute(
            "SELECT source_id FROM dbo.sources WHERE url_hash = ?",
            pyodbc_binary(url_hash),
        ).fetchone()

        if existing:
            source_id = existing.source_id
            conn.execute(
                """
                UPDATE dbo.sources
                SET title = ?, author = ?, published_at = ?,
                    metadata = ?, updated_at = SYSUTCDATETIME()
                WHERE source_id = ?
                """,
                title, author, published_at,
                json.dumps(metadata or {}), source_id,
            )
        else:
            conn.execute(
                """
                INSERT INTO dbo.sources
                       (url, url_hash, source_type, feed_id, title, author,
                        published_at, body_markdown, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                url, pyodbc_binary(url_hash), source_type, feed_id,
                title, author, published_at, body_markdown,
                json.dumps(metadata or {}),
            )
            row = conn.execute("SELECT SCOPE_IDENTITY() AS id").fetchone()
            source_id = int(row.id)

    log.debug("db.source.upserted", source_id=source_id, url=url, source_type=source_type)
    return source_id


# ── Notes ─────────────────────────────────────────────────────────────────────

def upsert_note(
    vault_path: str,
    title: str,
    note_type: str,
    body_markdown: str,
    source_id: int | None = None,
    domain: str | None = None,
    frontmatter: dict | None = None,
    tags: list[str] | None = None,
) -> int:
    conn = get_connection()
    row = conn.execute(
        "EXEC dbo.usp_upsert_note ?, ?, ?, ?, ?, ?, ?, ?",
        vault_path, source_id, title, note_type, domain,
        body_markdown,
        json.dumps(frontmatter or {}),
        json.dumps(tags or []),
    ).fetchone()
    conn.commit()
    note_id = int(row.note_id)
    log.debug("db.note.upserted", note_id=note_id, vault_path=vault_path)
    return note_id


# ── Relevance scores ──────────────────────────────────────────────────────────

def record_relevance_scores(source_id: int, scores: dict[str, float]) -> None:
    with transaction() as conn:
        for domain, score in scores.items():
            conn.execute(
                """
                MERGE dbo.relevance_scores AS tgt
                USING (SELECT ? AS source_id, ? AS domain) AS src
                   ON tgt.source_id = src.source_id AND tgt.domain = src.domain
                WHEN MATCHED THEN
                    UPDATE SET score = ?, scored_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (source_id, domain, score) VALUES (?, ?, ?);
                """,
                source_id, domain, score, source_id, domain, score,
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def pyodbc_binary(data: bytes):
    """Wrap bytes so pyodbc sends them as BINARY/VARBINARY."""
    return bytes(data)
