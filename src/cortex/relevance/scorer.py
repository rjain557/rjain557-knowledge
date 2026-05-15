"""Relevance scorer — asks Claude to score content against each domain."""

from __future__ import annotations

import json
import re

import structlog

from cortex.config import get_domains_config, get_yaml_config
from cortex.llm import complete

log = structlog.get_logger(__name__)

_SYSTEM = """You are a relevance classifier for a knowledge system that tracks three AI domains.
Score how relevant a piece of content is to each domain on a scale of 0.0 to 1.0.
Return ONLY a JSON object with domain names as keys and float scores as values.
Example: {"agent-orchestration": 0.82, "seo-agents": 0.05, "tech-support-agents": 0.0}"""


def score(title: str, body_markdown: str, max_body_chars: int = 2000) -> dict[str, float]:
    """Return a relevance score per domain for the given content."""
    domains_cfg = get_domains_config().get("domains", {})
    settings_cfg = get_yaml_config()

    domain_descriptions = "\n".join(
        f"- {name}: {cfg.get('description', '').strip()}"
        for name, cfg in domains_cfg.items()
    )

    body_preview = body_markdown[:max_body_chars]
    prompt = f"""Domains:
{domain_descriptions}

Content title: {title}

Content (first {max_body_chars} chars):
{body_preview}

Score each domain 0.0–1.0. Return only JSON."""

    try:
        raw = complete(
            system=_SYSTEM,
            prompt=prompt,
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            temperature=0.0,
        )
        scores = _parse_scores(raw, list(domains_cfg.keys()))
    except Exception as exc:
        log.warning("relevance.score_failed", error=str(exc), title=title)
        scores = {d: 0.0 for d in domains_cfg}

    log.debug("relevance.scored", title=title, scores=scores)
    return scores


def is_relevant(scores: dict[str, float]) -> bool:
    """True if any domain score exceeds its configured threshold."""
    domains_cfg = get_domains_config().get("domains", {})
    for domain, score_val in scores.items():
        threshold = domains_cfg.get(domain, {}).get("relevance_threshold", 0.35)
        if score_val >= threshold:
            return True
    return False


# ── Internals ─────────────────────────────────────────────────────────────────

def _parse_scores(raw: str, domain_keys: list[str]) -> dict[str, float]:
    # Strip any markdown fencing
    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    data = json.loads(raw)
    result = {}
    for key in domain_keys:
        val = data.get(key, 0.0)
        result[key] = float(max(0.0, min(1.0, val)))
    return result
