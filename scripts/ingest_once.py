"""
One-shot ingestion for a single URL. Use for testing.

    uv run python scripts/ingest_once.py <url>
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ]
)

import argparse

from cortex.extractors.article import extract
from cortex.relevance.scorer import score, is_relevant
from cortex.db import repositories as repo
from cortex.vault.writer import write_inbox_note

log = structlog.get_logger(__name__)


def ingest_url(url: str) -> None:
    log.info("ingest.start", url=url)

    # 1. Extract content
    content = extract(url)
    if not content:
        log.error("ingest.extract_failed", url=url)
        sys.exit(1)

    log.info("ingest.extracted", title=content.title, chars=len(content.body_markdown))

    # 2. Dedup check
    if repo.is_link_processed(url):
        log.info("ingest.already_processed", url=url)
        return

    # 3. Score relevance
    scores = score(content.title, content.body_markdown)
    log.info("ingest.scores", scores=scores)

    # 4. Save source to DB
    link_id = repo.record_link(
        original_url=url, source_type=content.source_type, email_id=None
    )
    source_id = repo.upsert_source(
        source_url=url,
        source_type=content.source_type,
        title=content.title,
        author=content.author,
        published_at=content.published_at,
        body_markdown=content.body_markdown,
        metadata=content.metadata,
        link_id=link_id,
        canonical_url=content.canonical_url,
        extractor=content.metadata.get("extractor"),
    )
    repo.record_relevance_scores(source_id, scores)

    # 5. Write vault note
    vault_path, note_id = write_inbox_note(content, source_id, scores)

    log.info(
        "ingest.done",
        url=url,
        source_id=source_id,
        note_id=note_id,
        vault_path=vault_path,
        relevant=is_relevant(scores),
    )
    print(f"\n✓ Ingested: {content.title}")
    print(f"  Vault: {vault_path}")
    print(f"  source_id={source_id}  note_id={note_id}")
    print(f"  Scores: {scores}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a single URL into Cortex")
    parser.add_argument("url", help="URL to ingest")
    args = parser.parse_args()
    ingest_url(args.url)


if __name__ == "__main__":
    main()
