"""Auto-trigger logic for the Deep Research orchestrator.

Called from the ingestion pipeline (scripts/poll.py) immediately after a new
source has been scored. Decides — under cost/relevance/dedup gates — whether
to fire Deep Research on the new source synchronously.

Gates (all read from config/settings.yaml > deep_research):
  * auto_trigger_in_poll       — master on/off
  * auto_min_score             — skip pure noise (default 0.3)
  * max_auto_per_day           — daily cap on auto-runs (default 25)
  * auto_model                 — which Claude model (default Opus 4.7)
  * auto_max_searches          — web_search budget per run (default 5)
  * skip_already_researched    — skip if dbo.deep_research_runs already
                                  has a 'completed' row for this source

Returns: (decision, reason)
  decision ∈ {"ran", "skipped"}
  reason   = short human string
"""

from __future__ import annotations

import structlog

from cortex.config import get_yaml_config
from cortex.db import repositories as repo

log = structlog.get_logger(__name__)


def maybe_auto_research(
    *,
    source_id: int,
    title: str,
    body_markdown: str,
    primary_domain: str | None,
    domain_scores: dict[str, float],
) -> tuple[str, str]:
    cfg = get_yaml_config().get("deep_research", {})

    if not cfg.get("auto_trigger_in_poll", False):
        return "skipped", "auto_trigger_in_poll=false"

    min_score = float(cfg.get("auto_min_score", 0.3))
    best_score = max(domain_scores.values()) if domain_scores else 0.0
    if best_score < min_score:
        return "skipped", f"top score {best_score:.2f} < min {min_score:.2f}"

    if cfg.get("skip_already_researched", True) and repo.source_already_researched(source_id):
        return "skipped", "already has a completed dbo.deep_research_runs row"

    cap = int(cfg.get("max_auto_per_day", 25))
    today = repo.deep_research_count_today()
    if today >= cap:
        return "skipped", f"daily cap reached ({today}/{cap} runs in last 24h)"

    model = cfg.get("auto_model", "claude-opus-4-7")
    max_searches = int(cfg.get("auto_max_searches", 5))
    domain = primary_domain or "agent-orchestration"

    # Imported here to avoid a top-level import cycle (orchestrator imports
    # this module indirectly via the verifier path).
    from cortex.deep_research.orchestrator import run_deep_research
    log.info("auto_dr.firing", source_id=source_id, title=title[:60],
             score=best_score, today=today, cap=cap, model=model)
    result = run_deep_research(
        source_id=source_id,
        topic=title,
        body_excerpt=body_markdown,
        primary_domain=domain,
        triggered_by="auto_post_ingest",
        max_searches=max_searches,
        model=model,
    )
    if result.status == "completed":
        return "ran", f"run_id={result.run_id} cost=${result.cost_usd:.2f} cites={len(result.citations)}"
    return "skipped", f"orchestrator returned status={result.status}: {result.failure_reason}"
