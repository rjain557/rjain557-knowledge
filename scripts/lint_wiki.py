"""
Daily wiki health check (Karpathy LLM-Wiki pattern, lint operation).

    uv run python scripts/lint_wiki.py
    uv run python scripts/lint_wiki.py --max-pair-checks 30
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

from cortex.lint.wiki_lint import run_lint


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--max-pair-checks", type=int, default=15,
                   help="Max near-duplicate pairs to Haiku-check for contradictions")
    args = p.parse_args()

    findings = run_lint(max_pair_checks=args.max_pair_checks)
    print("\n" + "=" * 60)
    print(f"orphans: {len(findings.orphans)}   "
          f"near-dups: {len(findings.near_duplicates)}   "
          f"contradictions: {len(findings.contradictions)}   "
          f"stale: {len(findings.stale)}")
    print(f"report: {findings.output_path}")


if __name__ == "__main__":
    main()
