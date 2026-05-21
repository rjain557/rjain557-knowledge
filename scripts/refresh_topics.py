"""
Weekly curated topic refresh — time-boxed "what's new" per evergreen theme.

    uv run python scripts/refresh_topics.py
    uv run python scripts/refresh_topics.py --max-themes 1   # smoke test
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

from cortex.topic_refresh.runner import run_weekly_refresh


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--max-themes", type=int, default=None)
    args = p.parse_args()

    summary = run_weekly_refresh(max_themes=args.max_themes)
    print("\n" + "=" * 60)
    print(f"themes: {summary['themes_refreshed']}   "
          f"new sources: {summary['total_new_sources']}   "
          f"cost: ${summary['total_cost_usd']}   "
          f"failed: {summary['failed']}")
    for r in summary["results"]:
        print(f"  [{r['status']:<10}] {r['slug']:<32} new={r['new_sources']:>2}  "
              f"${r['cost_usd']:.3f}  since {r['since_date']}")


if __name__ == "__main__":
    main()
