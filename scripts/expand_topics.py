"""
One-time topic-expansion backfill (Karpathy LLM-Wiki pattern).

For each note_type='topic' in the vault, query VECTOR_SEARCH for the top
5 most-similar OTHER notes and append a `## Update (YYYY-MM-DD) —` section
per related note that has new information. Mirrors what
synthesize_cross_page_updates does on every new ingest, but applied
historically to the existing 70+ topic articles.

Cost estimate: ~$0.05/topic in Haiku calls => ~$5 for the current vault.

    uv run python scripts/expand_topics.py --dry-run
    uv run python scripts/expand_topics.py --max-topics 10
    uv run python scripts/expand_topics.py             # all topics
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

from cortex.db.connection import get_connection
from cortex.synthesizer.cross_page import synthesize_cross_page_updates


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--max-topics", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    conn = get_connection()
    sql = """
        SELECT note_id, vault_path, title, domain, body_markdown
        FROM   dbo.notes
        WHERE  note_type = 'topic'
          AND  embedding IS NOT NULL
          AND  body_markdown IS NOT NULL
        ORDER BY note_id;
    """
    if args.max_topics:
        sql = sql.replace("SELECT note_id",
                          f"SELECT TOP ({args.max_topics}) note_id")
    rows = conn.execute(sql).fetchall()
    print(f"Planning {len(rows)} topic expansions"
          + (" (dry-run)" if args.dry_run else ""))

    total_updates = 0
    for i, r in enumerate(rows, 1):
        title = r.title or "(no title)"
        print(f"\n[{i}/{len(rows)}] {title[:70]}")
        if args.dry_run:
            continue
        try:
            actions = synthesize_cross_page_updates(
                new_source_title=title,
                new_source_body=r.body_markdown,
                primary_domain=r.domain,
                top_k=5,
                skip_note_ids={r.note_id},   # don't update self
            )
            total_updates += len(actions)
            print(f"  applied {len(actions)} updates to related notes")
            for a in actions:
                print(f"    -> {a.vault_path}  ({a.relation}, d={a.distance:.3f})")
        except Exception as exc:
            print(f"  ERROR: {exc}")

    print(f"\n== total updates applied: {total_updates} ==")


if __name__ == "__main__":
    main()
