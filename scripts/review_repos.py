"""
Daily Cortex repo-review pass — analyses N private repos against the
Cortex vault brain and opens a PR in each with improvement prompts.

    uv run python scripts/review_repos.py
    uv run python scripts/review_repos.py --max-repos 2     # smoke test
    uv run python scripts/review_repos.py --only technijian-usa/tech-web-myjian
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog
structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

from cortex.repo_review.lister import load_config
from cortex.repo_review.runner import run_daily, review_one


def main() -> None:
    p = argparse.ArgumentParser(description="Cortex daily repo-review runner")
    p.add_argument("--max-repos", type=int, default=None,
                   help="Override max_repos_per_run (default from YAML)")
    p.add_argument("--only", type=str, default=None,
                   help="Only review this repo full_name (overrides allowlist)")
    args = p.parse_args()

    if args.only:
        cfg = load_config()
        entry = next((r for r in (cfg.get("repos") or [])
                      if r["name"] == args.only), None)
        if not entry:
            print(f"'{args.only}' not in config/reviewed-repos.yaml")
            sys.exit(1)
        result = review_one(
            full_name=args.only,
            domain=entry.get("domain", "agent-orchestration"),
            max_prompts=int(cfg.get("max_prompts_per_repo", 5)),
            model=cfg.get("analysis_model", "claude-sonnet-4-6"),
            branch_prefix=cfg.get("pr_branch_prefix", "cortex-knowledge"),
        )
        print(json.dumps(result, indent=2))
        return

    summary = run_daily(max_repos=args.max_repos)
    print("\n" + "=" * 60)
    print(f"processed: {summary['repos_processed']}   "
          f"PRs opened: {summary['prs_opened']}   "
          f"no improvements: {summary['no_improvements']}   "
          f"failed: {summary['failed']}")
    for r in summary["results"]:
        line = f"  [{r['status']:<16}] {r['repo']}"
        if r.get("pr_url"):
            line += f"  -> {r['pr_url']}"
        if r.get("error"):
            line += f"  ERR: {r['error'][:120]}"
        print(line)


if __name__ == "__main__":
    main()
