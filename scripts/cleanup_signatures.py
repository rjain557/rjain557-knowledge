"""
Remove sources/links/notes that were ingested from email signatures or
security-tool banners (INKY, calendar links, brand social profiles).

Run with --dry-run first to preview the affected rows + files.

    uv run python scripts/cleanup_signatures.py --dry-run
    uv run python scripts/cleanup_signatures.py
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

from cortex.config import get_settings
from cortex.db.connection import get_connection, transaction

log = structlog.get_logger(__name__)

# Same patterns as link_extractor._SKIP_PATTERNS (URL-only — applied
# retroactively to dbo.sources/processed_links rows).
SQL_LIKE_FILTERS = [
    "%inkyphishfence.com%",
    "%outlook.office.com/bookwithme%",
    "%outlook.office365.com/owa/calendar/%/bookings%",
    "%calendly.com/%",
    "%//technijian.com%",
    "%www.technijian.com%",
    "%linkedin.com/company/technijian%",
    "%youtube.com/@TechnijianIT%",
    "%instagram.com/technijianinc%",
    "%facebook.com/Technijian01%",
    "%twitter.com/technijian_%",
    "%x.com/technijian_%",
    "%pinterest.com/technijian01%",
    "%tiktok.com/@technijian/%",
    "%tiktok.com/@technijian",
]

DEEP_RESEARCH_TOPIC_LIKE = [
    "%technijian%", "%inky%",
]


def _build_where(col: str) -> tuple[str, list[str]]:
    clauses = [f"LOWER({col}) LIKE LOWER(?)" for _ in SQL_LIKE_FILTERS]
    return "(" + " OR ".join(clauses) + ")", SQL_LIKE_FILTERS


def _find_polluted_sources() -> list[dict]:
    conn = get_connection()
    where, params = _build_where("source_url")
    rows = conn.execute(
        f"SELECT source_id, source_url, source_type, title FROM dbo.sources WHERE {where}",
        *params,
    ).fetchall()
    return [dict(source_id=r.source_id, source_url=r.source_url,
                 source_type=r.source_type, title=r.title) for r in rows]


def _find_polluted_links() -> list[int]:
    conn = get_connection()
    where, params = _build_where("original_url")
    rows = conn.execute(
        f"SELECT link_id FROM dbo.processed_links WHERE {where}",
        *params,
    ).fetchall()
    return [int(r.link_id) for r in rows]


def _find_polluted_research_runs() -> list[dict]:
    conn = get_connection()
    clauses = [f"LOWER(topic) LIKE LOWER(?)" for _ in DEEP_RESEARCH_TOPIC_LIKE]
    rows = conn.execute(
        "SELECT run_id, topic, output_topic_path, cost_usd FROM dbo.deep_research_runs WHERE "
        + " OR ".join(clauses),
        *DEEP_RESEARCH_TOPIC_LIKE,
    ).fetchall()
    return [dict(run_id=r.run_id, topic=r.topic,
                 output_topic_path=r.output_topic_path,
                 cost_usd=float(r.cost_usd or 0)) for r in rows]


def _vault_files_for_notes(source_ids: list[int], run_ids: list[int]) -> list[Path]:
    settings = get_settings()
    vault = settings.vault_path
    conn = get_connection()
    paths: list[Path] = []

    if source_ids:
        marks = ",".join("?" for _ in source_ids)
        rows = conn.execute(
            f"SELECT vault_path FROM dbo.notes WHERE source_id IN ({marks})",
            *source_ids,
        ).fetchall()
        paths += [vault / r.vault_path.replace("/", "\\") for r in rows if r.vault_path]

    if run_ids:
        marks = ",".join("?" for _ in run_ids)
        rows = conn.execute(
            f"SELECT output_topic_path FROM dbo.deep_research_runs WHERE run_id IN ({marks})",
            *run_ids,
        ).fetchall()
        paths += [vault / r.output_topic_path.replace("/", "\\") for r in rows if r.output_topic_path]
    return paths


def delete_pollution(source_ids: list[int], link_ids: list[int],
                     run_ids: list[int], vault_paths: list[Path]) -> None:
    with transaction() as conn:
        if source_ids:
            marks = ",".join("?" for _ in source_ids)
            conn.execute(f"DELETE FROM dbo.relevance_scores WHERE source_id IN ({marks})",
                         *source_ids)
            conn.execute(f"DELETE FROM dbo.notes WHERE source_id IN ({marks})",
                         *source_ids)
        if run_ids:
            marks = ",".join("?" for _ in run_ids)
            # Null out any notes that reference these runs' source_id'd topics
            conn.execute(
                f"DELETE FROM dbo.notes WHERE vault_path IN ("
                f"  SELECT output_topic_path FROM dbo.deep_research_runs WHERE run_id IN ({marks}))",
                *run_ids,
            )
            conn.execute(f"DELETE FROM dbo.deep_research_runs WHERE run_id IN ({marks})",
                         *run_ids)
        if source_ids:
            marks = ",".join("?" for _ in source_ids)
            conn.execute(f"DELETE FROM dbo.sources WHERE source_id IN ({marks})",
                         *source_ids)
        if link_ids:
            marks = ",".join("?" for _ in link_ids)
            conn.execute(f"DELETE FROM dbo.processed_links WHERE link_id IN ({marks})",
                         *link_ids)

    removed_files = 0
    for p in vault_paths:
        try:
            if p.exists():
                p.unlink()
                removed_files += 1
        except Exception as exc:
            log.warning("cleanup.file_unlink_failed", path=str(p), error=str(exc))
    log.info("cleanup.files_removed", count=removed_files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sources = _find_polluted_sources()
    links = _find_polluted_links()
    runs = _find_polluted_research_runs()
    source_ids = [s["source_id"] for s in sources]
    run_ids = [r["run_id"] for r in runs]
    vault_paths = _vault_files_for_notes(source_ids, run_ids)

    print(f"\nPolluted rows to remove:")
    print(f"  dbo.processed_links     : {len(links)}")
    print(f"  dbo.sources             : {len(sources)}")
    print(f"  dbo.deep_research_runs  : {len(runs)}  "
          f"(total cost spent: ${sum(r['cost_usd'] for r in runs):.2f})")
    print(f"  vault files (Inbox+Topics) : {len(vault_paths)}")

    if sources:
        print(f"\nSample of source URLs being removed:")
        # Group by host for readability
        from collections import Counter
        by_host = Counter()
        for s in sources:
            host = s["source_url"].split("/")[2] if "://" in s["source_url"] else s["source_url"]
            by_host[host] += 1
        for host, n in by_host.most_common(10):
            print(f"  {n:>4}  {host}")

    if runs:
        print(f"\nDeep research topics being removed:")
        for r in runs:
            print(f"  run_id={r['run_id']}  ${r['cost_usd']:.2f}  {r['topic'][:70]}")

    if args.dry_run:
        print("\n(dry-run, nothing deleted)")
        return

    if not (sources or links or runs):
        print("\nNothing to remove.")
        return

    print("\nDeleting…")
    delete_pollution(source_ids, links, run_ids, vault_paths)
    print("Done.")


if __name__ == "__main__":
    main()
