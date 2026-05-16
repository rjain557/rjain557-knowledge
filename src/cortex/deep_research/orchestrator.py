"""
Deep Research orchestrator — SPEC §3.13.

Per source (or topic): hand Claude Opus 4.7 the source title + body excerpt
with the server-side `web_search` tool enabled. Claude does the multi-turn
search loop itself, returns a synthesised topic article with inline citations.
We persist the article to `/Topics/{slug}.md` and a `dbo.deep_research_runs`
row.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import structlog
from anthropic import Anthropic

from cortex.config import get_settings
from cortex.db.connection import get_connection, transaction

log = structlog.get_logger(__name__)

VAULT_TOPICS = "Topics"

# Pricing (USD per million tokens) — Opus 4.7
PRICE_INPUT_PER_M = 15.0
PRICE_OUTPUT_PER_M = 75.0
PRICE_PER_SEARCH = 0.01   # web_search ~ $10 per 1000 searches


@dataclass
class ResearchResult:
    run_id: int | None
    topic: str
    article_markdown: str
    article_path: str
    citations: list[dict] = field(default_factory=list)
    web_searches_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    status: str = "completed"          # completed | failed | partial
    failure_reason: str | None = None


def run_deep_research(
    *,
    source_id: int,
    topic: str,
    body_excerpt: str,
    primary_domain: str,
    triggered_by: str = "manual",
    max_searches: int = 8,
    model: str = "claude-opus-4-7",
) -> ResearchResult:
    """Execute one deep-research run. Always writes a dbo.deep_research_runs row."""
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()

    run_id = _insert_run_row(
        topic=topic,
        triggered_by=triggered_by,
        triggered_source_id=source_id,
        domains=[primary_domain],
        started_at=started_at,
    )

    try:
        result = _execute(topic, body_excerpt, primary_domain, max_searches, model)
        result.run_id = run_id
        result.duration_seconds = time.monotonic() - t0

        article_path = _write_topic_article(
            topic=topic,
            article_markdown=result.article_markdown,
            primary_domain=primary_domain,
            triggered_source_id=source_id,
            citations=result.citations,
            run_id=run_id,
            cost_usd=result.cost_usd,
        )
        result.article_path = article_path

        _finalise_run_row(run_id, result)
        log.info(
            "deep_research.done",
            run_id=run_id, topic=topic[:60], searches=result.web_searches_used,
            cost_usd=round(result.cost_usd, 3), path=article_path,
        )
        return result

    except Exception as exc:
        log.error("deep_research.failed", run_id=run_id, topic=topic[:60], error=str(exc))
        _mark_run_failed(run_id, str(exc))
        return ResearchResult(
            run_id=run_id, topic=topic, article_markdown="", article_path="",
            status="failed", failure_reason=str(exc),
            duration_seconds=time.monotonic() - t0,
        )


# ── Claude call loop ──────────────────────────────────────────────────────────

def _execute(
    topic: str,
    body_excerpt: str,
    primary_domain: str,
    max_searches: int,
    model: str,
) -> ResearchResult:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    system = f"""You are a deep-research synthesizer for the Cortex knowledge brain.

Domain context: {primary_domain}

Your job:
1. Use the web_search tool to find 5-10 authoritative adjacent sources on the topic.
   Cover multiple perspectives: technical depth, related approaches, contested claims,
   practical applications, recent developments. Prefer primary sources (papers, vendor
   docs, well-known engineering blogs, official repos) over aggregators.
2. After searching, write a structured topic article in markdown:
   - Begin with a short overview (3-5 sentences)
   - Then 3-6 H2 sections covering the topic from different angles
   - Every non-trivial claim must cite at least one source inline using [^N] footnotes
   - End with a `## References` section listing each [^N] with title and URL
   - Aim for 800-1500 words; substantive but tight
3. Output ONLY the article markdown. Do not include preamble or meta-commentary.
"""

    user_msg = f"""Topic: {topic}

Primary domain: {primary_domain}

Original source excerpt (what the user forwarded — research the broader topic, don't just summarise this):
---
{body_excerpt[:3000]}
---

Research adjacent authoritative sources via web_search, then produce the topic article."""

    messages = [{"role": "user", "content": user_msg}]
    total_input = 0
    total_output = 0
    searches_used = 0
    last_response = None

    for iteration in range(20):  # hard safety cap on agent-loop iterations
        log.debug("deep_research.iter", iteration=iteration, topic=topic[:50])
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=system,
            messages=messages,
            tools=[{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_searches,
            }],
        )
        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens
        last_response = response

        # Count any web_search uses in this response
        for block in response.content:
            if getattr(block, "type", None) == "server_tool_use":
                if getattr(block, "name", None) == "web_search":
                    searches_used += 1

        if response.stop_reason == "end_turn":
            break
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        # Any other stop reason (max_tokens, tool_use error etc.) — break and use what we have
        log.warning("deep_research.unexpected_stop", stop=response.stop_reason)
        break

    # Extract final text + citations from the last response
    article_text = ""
    citations: list[dict] = []
    for block in last_response.content:
        if getattr(block, "type", None) == "text":
            article_text += block.text
            for c in getattr(block, "citations", None) or []:
                citations.append({
                    "url": getattr(c, "url", None),
                    "title": getattr(c, "title", None),
                    "cited_text": getattr(c, "cited_text", None),
                })

    cost = _calc_cost(total_input, total_output, searches_used)

    return ResearchResult(
        run_id=None,
        topic=topic,
        article_markdown=article_text.strip(),
        article_path="",
        citations=citations,
        web_searches_used=searches_used,
        input_tokens=total_input,
        output_tokens=total_output,
        cost_usd=cost,
    )


# ── Persistence ───────────────────────────────────────────────────────────────

def _insert_run_row(
    topic: str,
    triggered_by: str,
    triggered_source_id: int,
    domains: list[str],
    started_at: datetime,
) -> int:
    with transaction() as conn:
        row = conn.execute(
            """
            INSERT INTO dbo.deep_research_runs
                   (topic, triggered_by, triggered_source_id, domains,
                    started_at, status)
            OUTPUT INSERTED.run_id AS id
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            topic, triggered_by, triggered_source_id,
            json.dumps(domains), started_at,
        ).fetchone()
        return int(row.id)


def _finalise_run_row(run_id: int, result: ResearchResult) -> None:
    with transaction() as conn:
        conn.execute(
            """
            UPDATE dbo.deep_research_runs
            SET    finished_at = SYSUTCDATETIME(),
                   sources_consulted = ?,
                   sources_cited = ?,
                   search_engines_used = ?,
                   cost_usd = ?,
                   output_topic_path = ?,
                   status = 'completed'
            WHERE  run_id = ?
            """,
            result.web_searches_used,
            len(result.citations),
            json.dumps(["claude_web_search"]),
            float(result.cost_usd),
            result.article_path,
            run_id,
        )


def _mark_run_failed(run_id: int, reason: str) -> None:
    try:
        with transaction() as conn:
            conn.execute(
                """
                UPDATE dbo.deep_research_runs
                SET    finished_at = SYSUTCDATETIME(),
                       status = 'failed',
                       failure_reason = ?
                WHERE  run_id = ?
                """,
                reason[:4000], run_id,
            )
    except Exception:
        pass


def _write_topic_article(
    *,
    topic: str,
    article_markdown: str,
    primary_domain: str,
    triggered_source_id: int,
    citations: list[dict],
    run_id: int,
    cost_usd: float,
) -> str:
    settings = get_settings()
    vault = settings.vault_path

    slug = _slugify(topic)
    topics_dir = vault / VAULT_TOPICS
    topics_dir.mkdir(parents=True, exist_ok=True)
    file_path = topics_dir / f"{slug}.md"

    fm = {
        "type": "topic",
        "domain": primary_domain,
        "generated_by": "deep_research",
        "research_run_id": run_id,
        "triggered_source_id": triggered_source_id,
        "sources_cited": len(citations),
        "search_engines_used": ["claude_web_search"],
        "cost_usd": round(float(cost_usd), 4),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "title": topic,
        "tags": ["deep-research"],
    }
    post = frontmatter.Post(article_markdown, **fm)
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    # Mirror to dbo.notes via the same path the regular writer uses
    relative_path = str(file_path.relative_to(vault)).replace("\\", "/")
    conn = get_connection()
    conn.execute(
        "EXEC dbo.usp_upsert_note ?, ?, ?, ?, ?, ?, ?, ?",
        relative_path, triggered_source_id, topic, "topic", primary_domain,
        article_markdown, json.dumps(fm, default=str), json.dumps(["deep-research"]),
    ).fetchone()
    conn.commit()
    return relative_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calc_cost(input_tokens: int, output_tokens: int, searches: int) -> float:
    return (
        input_tokens * PRICE_INPUT_PER_M / 1_000_000
        + output_tokens * PRICE_OUTPUT_PER_M / 1_000_000
        + searches * PRICE_PER_SEARCH
    )


def _slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:max_len]
