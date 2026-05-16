"""
Run the Deep Research pipeline (SPEC §3.13) over existing sources.

Modes:
    # Smoke test — run on one source
    uv run python scripts/deep_research.py --source-id 12

    # Run on all unique sources with any domain score >= threshold
    uv run python scripts/deep_research.py --min-score 0.5 --max-runs 25

    # Dry-run: show what would be processed without calling Claude
    uv run python scripts/deep_research.py --min-score 0.5 --dry-run
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
from cortex.deep_research.orchestrator import run_deep_research

log = structlog.get_logger(__name__)


def _candidates(min_score: float, max_runs: int, skip_existing: bool = True) -> list[dict]:
    """Pick ONE row per unique title (the highest-scoring of any duplicates),
    sorted by best domain score desc."""
    skip_clause = ""
    if skip_existing:
        # Skip sources that already have a completed deep_research_runs row
        skip_clause = """
              AND  NOT EXISTS (
                  SELECT 1 FROM dbo.deep_research_runs dr
                  WHERE  dr.triggered_source_id = s.source_id
                    AND  dr.status = 'completed'
              )
        """
    sql = f"""
        WITH ranked AS (
            SELECT s.source_id, s.title, s.body_markdown,
                   rs.domain, rs.score,
                   ROW_NUMBER() OVER (
                     PARTITION BY s.title ORDER BY rs.score DESC
                   ) AS rk_in_title
            FROM   dbo.sources s
            JOIN   dbo.relevance_scores rs ON rs.source_id = s.source_id
            WHERE  s.title IS NOT NULL AND LEN(s.title) > 0
              AND  rs.score >= ?
              {skip_clause}
        )
        SELECT TOP (?) source_id, title, body_markdown, domain, score
        FROM   ranked
        WHERE  rk_in_title = 1
        ORDER BY score DESC, source_id;
    """
    conn = get_connection()
    rows = conn.execute(sql, float(min_score), int(max_runs)).fetchall()
    return [
        dict(source_id=r.source_id, title=r.title,
             body=r.body_markdown or "", domain=r.domain, score=float(r.score))
        for r in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Cortex Deep Research runner")
    parser.add_argument("--source-id", type=int, help="Run on a single source_id")
    parser.add_argument("--min-score", type=float, default=0.5,
                        help="Minimum relevance score (any domain) — default 0.5")
    parser.add_argument("--max-runs", type=int, default=25,
                        help="Max number of runs in batch mode")
    parser.add_argument("--max-searches", type=int, default=8,
                        help="Max web_search uses per topic")
    parser.add_argument("--model", default="claude-opus-4-7")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.source_id:
        conn = get_connection()
        row = conn.execute(
            """
            SELECT TOP 1 s.source_id, s.title, s.body_markdown,
                   rs.domain, rs.score
            FROM   dbo.sources s
            LEFT JOIN dbo.relevance_scores rs ON rs.source_id = s.source_id
            WHERE  s.source_id = ?
            ORDER BY rs.score DESC
            """,
            args.source_id,
        ).fetchone()
        if not row:
            log.error("deep_research.source_not_found", source_id=args.source_id)
            sys.exit(1)
        candidates = [dict(
            source_id=row.source_id, title=row.title,
            body=row.body_markdown or "",
            domain=row.domain or "agent-orchestration",
            score=float(row.score or 0),
        )]
    else:
        candidates = _candidates(args.min_score, args.max_runs)

    print(f"\nPlanning {len(candidates)} deep-research run(s):")
    for i, c in enumerate(candidates, 1):
        print(f"  {i:>2}. [{c['domain']:>20} {c['score']:.2f}] {c['title'][:70]}")

    if args.dry_run:
        print("\n(dry-run, nothing executed)")
        return

    total_cost = 0.0
    completed = 0
    failed = 0

    for i, c in enumerate(candidates, 1):
        print(f"\n[{i}/{len(candidates)}] {c['title'][:80]}")
        result = run_deep_research(
            source_id=c["source_id"],
            topic=c["title"],
            body_excerpt=c["body"],
            primary_domain=c["domain"],
            max_searches=args.max_searches,
            model=args.model,
        )
        total_cost += result.cost_usd
        if result.status == "completed":
            completed += 1
            print(f"  → {result.article_path}")
            print(f"  searches={result.web_searches_used} "
                  f"in={result.input_tokens} out={result.output_tokens} "
                  f"cost=${result.cost_usd:.3f} dur={result.duration_seconds:.1f}s")
        else:
            failed += 1
            print(f"  FAILED: {result.failure_reason}")

    print()
    print("=" * 60)
    print(f"completed: {completed}   failed: {failed}   "
          f"total cost: ${total_cost:.2f}")


if __name__ == "__main__":
    main()
