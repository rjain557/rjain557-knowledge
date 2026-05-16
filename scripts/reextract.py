"""
Re-extract sources for previously-failed or skipped links.

Pulls every row from dbo.processed_links that does NOT have a corresponding
row in dbo.sources, re-classifies, and runs the proper extractor for its
type. Useful after adding new extractors (Phase 2+).

    uv run python scripts/reextract.py --dry-run
    uv run python scripts/reextract.py
    uv run python scripts/reextract.py --types tiktok,youtube
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog
structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

from cortex.db import repositories as repo
from cortex.db.connection import get_connection
from cortex.extractors import extract_for_type
from cortex.mail.link_extractor import _classify
from cortex.relevance.scorer import score as score_relevance, is_relevant
from cortex.vault.writer import write_inbox_note

log = structlog.get_logger(__name__)


def _missing_links(only_types: set[str] | None = None) -> list[dict]:
    sql = """
        SELECT pl.link_id, pl.email_id, pl.original_url, pl.canonical_url,
               pl.source_type AS stored_type
        FROM   dbo.processed_links pl
        LEFT JOIN dbo.sources s ON s.canonical_url = pl.canonical_url
        WHERE  s.source_id IS NULL
        ORDER BY pl.link_id;
    """
    conn = get_connection()
    rows = conn.execute(sql).fetchall()
    out = []
    for r in rows:
        link_type = _classify(r.original_url)
        if only_types and link_type not in only_types:
            continue
        out.append(dict(
            link_id=r.link_id, email_id=r.email_id,
            original_url=r.original_url, canonical_url=r.canonical_url,
            link_type=link_type, stored_type=r.stored_type,
        ))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-extract missing sources")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--types", help="comma-separated link_types to limit to "
                                        "(e.g. tiktok,youtube)")
    parser.add_argument("--skip-score", action="store_true",
                        help="don't run relevance scoring (skip Anthropic spend)")
    args = parser.parse_args()

    only_types = set(t.strip() for t in args.types.split(",")) if args.types else None
    missing = _missing_links(only_types)

    # Distribution
    by_type: dict[str, int] = {}
    for m in missing:
        by_type[m["link_type"]] = by_type.get(m["link_type"], 0) + 1

    print(f"\n{len(missing)} missing links to re-extract:")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:<15} {n}")

    if args.dry_run or not missing:
        return

    extracted = 0
    skipped = 0
    failed = 0

    for i, m in enumerate(missing, 1):
        url = m["original_url"]
        ltype = m["link_type"]
        print(f"\n[{i}/{len(missing)}] [{ltype}] {url[:80]}")
        try:
            content = extract_for_type(url, ltype)
        except Exception as exc:
            log.warning("reextract.exception", url=url, error=str(exc)[:200])
            content = None

        if not content:
            skipped += 1
            print("  → no content (extractor returned None)")
            continue

        scores: dict[str, float] = {}
        if not args.skip_score:
            try:
                scores = score_relevance(content.title, content.body_markdown)
            except Exception as exc:
                log.warning("reextract.score_failed", error=str(exc))

        source_id = repo.upsert_source(
            source_url=url,
            source_type=content.source_type,
            title=content.title,
            author=content.author,
            published_at=content.published_at,
            body_markdown=content.body_markdown,
            metadata=content.metadata,
            link_id=m["link_id"],
            canonical_url=content.canonical_url,
            extractor=content.metadata.get("extractor"),
        )
        if scores:
            repo.record_relevance_scores(source_id, scores)

        vault_path, note_id = write_inbox_note(content, source_id, scores)
        extracted += 1
        print(f"  → source_id={source_id} note_id={note_id} "
              f"{'relevant' if is_relevant(scores) else 'low-rel'}")

    print()
    print("=" * 60)
    print(f"extracted: {extracted}   skipped: {skipped}   failed: {failed}")


if __name__ == "__main__":
    main()
