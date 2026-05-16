"""Write vault notes and mirror to dbo.notes in the same logical transaction."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import structlog

from cortex.config import get_settings
from cortex.db import repositories as repo
from cortex.extractors.base import ExtractedContent
from cortex.utils.timezone import now_pacific, to_pacific

log = structlog.get_logger(__name__)

VAULT_INBOX = "Inbox"


def write_inbox_note(
    content: ExtractedContent,
    source_id: int,
    domain_scores: dict[str, float],
) -> tuple[str, int]:
    """Write a note to /Inbox/, mirror to dbo.notes. Returns (vault_path, note_id)."""
    settings = get_settings()
    vault = settings.vault_path

    slug = _slugify(content.title)
    # Filename date is the source's published date if known, else today in PT
    base = to_pacific(content.published_at) if content.published_at else now_pacific()
    filename = f"{base.strftime('%Y-%m-%d')}-{slug}.md"
    inbox_dir = vault / VAULT_INBOX
    inbox_dir.mkdir(parents=True, exist_ok=True)
    file_path = inbox_dir / filename

    # Resolve primary domain (highest score)
    primary_domain = max(domain_scores, key=lambda d: domain_scores[d]) if domain_scores else None

    fm_data = {
        "type": "source",
        "source_type": content.source_type,
        "source_url": content.source_url,
        "title": content.title,
        "author": content.author,
        # Captured time in America/Los_Angeles with -07:00/-08:00 offset
        "captured_at": now_pacific().isoformat(),
        "domain": primary_domain,
        "relevance": domain_scores,
        "tags": [],
        "status": "raw",
    }

    post = frontmatter.Post(content.body_markdown, **fm_data)
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    relative_path = str(file_path.relative_to(vault)).replace("\\", "/")
    log.info("vault.note_written", path=relative_path, title=content.title)

    note_id = repo.upsert_note(
        vault_path=relative_path,
        title=content.title,
        note_type="source",
        body_markdown=content.body_markdown,
        source_id=source_id,
        domain=primary_domain,
        frontmatter=fm_data,
        tags=[],
    )

    return relative_path, note_id


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text[:max_len]
