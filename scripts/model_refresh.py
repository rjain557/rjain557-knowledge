"""
Weekly model-refresh — liveness-check routed models + research newer/cheaper
options, then write a proposal (Meta/Proposals/pending/ + dbo.proposed_changes).
Never auto-applies; model routing is manual_only.

    uv run python scripts/model_refresh.py
    uv run python scripts/model_refresh.py --liveness-only   # skip web research
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

from cortex.model_refresh.runner import run, run_liveness


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--liveness-only", action="store_true", help="ping models, skip web research")
    args = p.parse_args()

    print("=" * 60)
    if args.liveness_only:
        results = run_liveness()
        for r in results:
            mark = "OK " if r["ok"] else "DEAD"
            print(f"  [{mark}] {r['label']:<28} {r['provider']}/{r['model']}  {r['detail']}")
        dead = [r for r in results if not r["ok"]]
        print(f"\n{len(results)} models checked, {len(dead)} dead.")
        return

    summary = run()
    print(f"date: {summary['date']}")
    print(f"dead models: {len(summary['dead_models'])}")
    for r in summary["dead_models"]:
        print(f"  DEAD {r['provider']}/{r['model']} — {r['detail']}")
    recs = summary["research"].get("recommendations", [])
    print(f"recommendations: {len(recs)}")
    for r in recs:
        print(f"  {r.get('task','')}: {r.get('current','')} -> {r.get('recommend','')}  ({r.get('reason','')[:80]})")
    print(f"\nproposal note: {summary['proposal_note']}")
    print(f"proposal_id:   {summary['proposal_id']}")


if __name__ == "__main__":
    main()
