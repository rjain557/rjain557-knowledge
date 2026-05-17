"""
Hourly GitHub-trending scanner — thin CLI wrapper around
`cortex.feeds.scan_runner.run_scan`. Picks the top-N repos per Technijian
AI category, dedups against rows already in dbo.sources, and feeds the
new ones into the ingestion pipeline (github extractor -> relevance ->
vault note -> embedding -> maybe auto-DR).

    uv run python scripts/scan_github.py
    uv run python scripts/scan_github.py --dry-run
    uv run python scripts/scan_github.py --top-n 10
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

from cortex.feeds.scan_runner import run_scan


def main() -> None:
    p = argparse.ArgumentParser(description="Hourly GitHub trending scanner")
    p.add_argument("--top-n", type=int, default=5,
                   help="Top N repos per category (default 5)")
    p.add_argument("--dry-run", action="store_true",
                   help="List candidates without ingesting")
    args = p.parse_args()

    summary = run_scan(top_n=args.top_n, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print(f"checked: {summary['checked']}   "
          f"new: {summary['new']}   "
          f"already-known: {summary['skipped_known']}   "
          f"extract-failed: {summary['extract_failed']}   "
          f"auto-DR fired: {summary['auto_dr_fired']}")
    for cat, s in summary["by_category"].items():
        print(f"\n[{cat}]  new={s['new']}  skipped={s['skipped']}")
        for line in s["top"]:
            print(f"  - {line}")


if __name__ == "__main__":
    main()
