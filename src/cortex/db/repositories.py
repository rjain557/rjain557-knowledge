"""All SQL Server access for Cortex. No raw pyodbc calls outside this module."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

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
    body_preview: str = "",
    folder: str = "Brain",
) -> int:
    with transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO dbo.processed_emails
                   (message_id, sender, subject, received_at,
                    body_preview, folder, captured_at, processed_at, status)
            OUTPUT INSERTED.email_id AS id
            VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), SYSUTCDATETIME(), 'processed')
            """,
            message_id, sender, subject, received_at, body_preview[:1000], folder,
        ).fetchone()
        return int(row.id)


# ── Links ─────────────────────────────────────────────────────────────────────

def is_link_processed(url: str) -> bool:
    conn = get_connection()
    url_hash = _hash(url)
    row = conn.execute(
        "SELECT 1 FROM dbo.processed_links WHERE url_hash = ?", url_hash
    ).fetchone()
    return row is not None


def record_link(
    original_url: str,
    source_type: str,
    email_id: int | None = None,
    canonical_url: str | None = None,
) -> int:
    canonical = canonical_url or original_url
    url_hash = _hash(canonical)
    with transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO dbo.processed_links
                   (email_id, original_url, canonical_url, url_hash,
                    source_type, classified_at, status)
            OUTPUT INSERTED.link_id AS id
            VALUES (?, ?, ?, ?, ?, SYSUTCDATETIME(), 'classified')
            """,
            email_id, original_url, canonical, url_hash, source_type,
        ).fetchone()
        return int(row.id)


# ── Sources ───────────────────────────────────────────────────────────────────

def upsert_source(
    source_url: str,
    source_type: str,
    title: str | None,
    author: str | None,
    published_at: datetime | None,
    body_markdown: str,
    metadata: dict | None = None,
    feed_id: int | None = None,
    link_id: int | None = None,
    canonical_url: str | None = None,
    extractor: str | None = None,
) -> int:
    canonical = canonical_url or source_url
    url_hash = _hash(canonical)

    with transaction() as conn:
        existing = conn.execute(
            "SELECT source_id FROM dbo.sources WHERE url_hash = ?", url_hash
        ).fetchone()

        if existing:
            source_id = existing.source_id
            conn.execute(
                """
                UPDATE dbo.sources
                SET title = ?, author = ?, published_at = ?,
                    body_markdown = ?, metadata = ?, extractor = ?,
                    extraction_status = 'success'
                WHERE source_id = ?
                """,
                title, author, published_at, body_markdown,
                json.dumps(metadata or {}), extractor, source_id,
            )
        else:
            row = conn.execute(
                """
                INSERT INTO dbo.sources
                       (link_id, feed_id, source_url, canonical_url, url_hash,
                        source_type, title, author, published_at, captured_at,
                        body_markdown, metadata, extractor, extraction_status)
                OUTPUT INSERTED.source_id AS id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(),
                        ?, ?, ?, 'success')
                """,
                link_id, feed_id, source_url, canonical, url_hash,
                source_type, title, author, published_at,
                body_markdown, json.dumps(metadata or {}), extractor,
            ).fetchone()
            source_id = int(row.id)

    log.debug("db.source.upserted", source_id=source_id, url=source_url, source_type=source_type)
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
        json.dumps(frontmatter or {}, default=str),
        json.dumps(tags or []),
    ).fetchone()
    conn.commit()
    note_id = int(row.note_id)
    log.debug("db.note.upserted", note_id=note_id, vault_path=vault_path)
    return note_id


# ── Relevance scores ──────────────────────────────────────────────────────────

def record_relevance_scores(
    source_id: int,
    scores: dict[str, float],
    model: str = "claude-haiku-4-5-20251001",
) -> None:
    with transaction() as conn:
        for domain, score in scores.items():
            conn.execute(
                """
                MERGE dbo.relevance_scores AS tgt
                USING (SELECT ? AS source_id, ? AS domain) AS src
                   ON tgt.source_id = src.source_id AND tgt.domain = src.domain
                WHEN MATCHED THEN
                    UPDATE SET score = ?, scored_at = SYSUTCDATETIME(), model = ?
                WHEN NOT MATCHED THEN
                    INSERT (source_id, domain, score, scored_at, model)
                    VALUES (?, ?, ?, SYSUTCDATETIME(), ?);
                """,
                source_id, domain, score, model,
                source_id, domain, score, model,
            )


# ── Embeddings ────────────────────────────────────────────────────────────────

def embed_note(note_id: int) -> dict:
    """Generate the OpenAI embedding for one note and store it on dbo.notes.

    Wraps `EXEC dbo.usp_embed_note`. Returns the proc's result row as a dict.
    Never raises — embedding failures are logged but should NOT block the
    surrounding ingestion / DR pipeline.
    """
    try:
        conn = get_connection()
        row = conn.execute("EXEC dbo.usp_embed_note @note_id = ?", note_id).fetchone()
        conn.commit()
        result = {"note_id": int(row.note_id) if row else note_id,
                  "norm": float(row.norm) if row and row.norm is not None else None,
                  "status": row.status if row else "no result"}
        log.info("db.embed_note", **result)
        return result
    except Exception as exc:
        log.warning("db.embed_note.error", note_id=note_id, error=str(exc)[:200])
        return {"note_id": note_id, "norm": None, "status": f"error: {exc}"}


# ── Deep research housekeeping ────────────────────────────────────────────────

def deep_research_count_today() -> int:
    """Count successful deep-research runs that started in the last 24h (UTC)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM dbo.deep_research_runs "
        "WHERE started_at >= DATEADD(hour, -24, SYSUTCDATETIME()) AND status = 'completed'"
    ).fetchone()
    return int(row.n) if row else 0


def source_already_researched(source_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM dbo.deep_research_runs "
        "WHERE triggered_source_id = ? AND status = 'completed'",
        source_id,
    ).fetchone()
    return row is not None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(url: str) -> bytes:
    return hashlib.sha256(url.encode()).digest()
