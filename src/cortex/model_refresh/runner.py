"""7-day model-refresh job.

Two responsibilities, run weekly (n8n -> POST /model-refresh):

  1. LIVENESS  — ping every provider+model currently routed in
     config/models.yaml (primaries AND fallbacks). Catches dead model ids,
     auth failures, and unfunded accounts before they break a real cycle.

  2. RESEARCH  — use Claude + web_search to find newer / cheaper models that
     could match-or-beat the current picks per task type, at lower cost.

Output is a PROPOSAL, never an auto-apply. Model routing is a manual_only
category (same discipline as schema/domain/vault-structure changes): the job
writes a note to Meta/Proposals/pending/ and a dbo.proposed_changes row, and a
human edits config/models.yaml to accept. This keeps "use the newest cheaper
model" deliberate rather than silently mutating an unattended pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

from cortex.config import get_models_config, get_settings
from cortex.llm import probe

log = structlog.get_logger(__name__)

PT = ZoneInfo("America/Los_Angeles")

_RESEARCH_SYSTEM = """You are a cost-optimization analyst for an LLM pipeline.
The pipeline already routes each task to a model (given below). Using the
web_search tool, find the CURRENT (as of today) newest and cheapest models that
could match or beat each current pick on quality while lowering cost.

Rules:
- Only recommend a change when there is a concrete quality-neutral cost win, OR
  a clear quality win at similar cost. "No change" is a valid, common answer.
- Verify current per-1M-token pricing via web_search; don't rely on memory.
- Respect constraints: tasks needing web_search MUST stay on Anthropic Claude
  (only Anthropic exposes the server-side web_search tool here). GLM/Zhipu is
  US-IP-blocked and must not be recommended for this unattended pipeline.
- Prefer providers already wired: anthropic, gemini, deepseek. Others
  (openai, kimi/moonshot, minimax, nvidia) are acceptable only with a strong win.

Return ONLY a JSON object:
{
  "as_of": "YYYY-MM-DD",
  "recommendations": [
    {"task": "...", "current": "provider/model", "recommend": "provider/model | KEEP",
     "current_price_in_out": "$x/$y per 1M", "new_price_in_out": "$x/$y per 1M",
     "est_monthly_saving": "qualitative or $", "reason": "1-2 sentences"}
  ],
  "new_models_noticed": ["provider/model — one line why it matters"],
  "summary": "2-3 sentence bottom line"
}"""


def run_liveness() -> list[dict]:
    """Ping every routed model (primary + fallback). Returns per-model results."""
    cfg = get_models_config()
    seen: set[tuple[str, str]] = set()
    checks: list[tuple[str, str, str]] = []  # (label, provider, model)

    for task, spec in cfg.get("tasks", {}).items():
        for role, node in (("primary", spec), ("fallback", spec.get("fallback"))):
            if not node:
                continue
            key = (node["provider"], node["model"])
            if key in seen:
                continue
            seen.add(key)
            checks.append((f"{task}:{role}", node["provider"], node["model"]))

    results = []
    for label, provider, model in checks:
        ok, detail = probe(provider, model)
        log.info("model_refresh.ping", label=label, provider=provider, model=model, ok=ok)
        results.append(
            {"label": label, "provider": provider, "model": model, "ok": ok, "detail": detail}
        )
    return results


def run_research(max_searches: int = 8) -> dict:
    """Ask Claude (with web_search) for newer/cheaper model recommendations."""
    from anthropic import Anthropic

    settings = get_settings()
    cfg = get_models_config()

    current = {
        t: f"{s['provider']}/{s['model']}" for t, s in cfg.get("tasks", {}).items()
    }
    pricing = cfg.get("pricing", {})
    today = datetime.now(PT).strftime("%Y-%m-%d")

    user_msg = (
        f"Today is {today}.\n\n"
        f"Current task -> model routing:\n{json.dumps(current, indent=2)}\n\n"
        f"Pricing snapshot we have on file (USD per 1M in/out):\n"
        f"{json.dumps(pricing, indent=2)}\n\n"
        f"Research current model options and return the recommendations JSON."
    )

    client = Anthropic(api_key=settings.anthropic_api_key)
    messages = [{"role": "user", "content": user_msg}]
    last = None
    searches = 0
    for _ in range(12):
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=_RESEARCH_SYSTEM,
            messages=messages,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}],
        )
        last = resp
        for block in resp.content:
            if getattr(block, "type", None) == "server_tool_use" and getattr(block, "name", None) == "web_search":
                searches += 1
        if resp.stop_reason == "end_turn":
            break
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break

    text = "".join(b.text for b in last.content if getattr(b, "type", None) == "text")
    data = _parse_json(text)
    data["_searches_used"] = searches
    return data


def _parse_json(raw: str) -> dict:
    import re

    raw = re.sub(r"```[a-z]*\n?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    try:
        return json.loads(raw)
    except Exception as exc:
        log.warning("model_refresh.parse_failed", error=str(exc))
        return {"summary": "Could not parse research output.", "raw": raw[:2000]}


def run() -> dict:
    """Full weekly refresh: liveness + research -> proposal note + DB row."""
    today = datetime.now(PT).strftime("%Y-%m-%d")
    liveness = run_liveness()
    dead = [r for r in liveness if not r["ok"]]

    try:
        research = run_research()
    except Exception as exc:
        log.warning("model_refresh.research_failed", error=str(exc))
        research = {"summary": f"Research step failed: {exc}", "recommendations": []}

    note_path = _write_proposal_note(today, liveness, dead, research)
    proposal_id = _insert_proposal_row(today, liveness, dead, research, note_path)

    log.info(
        "model_refresh.done",
        date=today,
        dead=len(dead),
        recs=len(research.get("recommendations", [])),
        proposal_id=proposal_id,
        note=note_path,
    )
    return {
        "date": today,
        "liveness": liveness,
        "dead_models": dead,
        "research": research,
        "proposal_note": note_path,
        "proposal_id": proposal_id,
    }


def _write_proposal_note(today: str, liveness: list[dict], dead: list[dict], research: dict) -> str:
    settings = get_settings()
    rel = f"Meta/Proposals/pending/model-refresh-{today}.md"
    path = settings.vault_path / rel.replace("/", "\\")
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        "type: proposal",
        "category: model_routing",
        f"created: {today}",
        "status: pending",
        "---",
        "",
        f"# Model-refresh proposal — {today}",
        "",
        "Weekly automated check for newer/cheaper models. **Not auto-applied** —",
        "edit `config/models.yaml` to accept any recommendation below.",
        "",
        "## Liveness (current routed models)",
        "",
        "| Task:role | Provider | Model | OK | Detail |",
        "|---|---|---|:--:|---|",
    ]
    for r in liveness:
        ok = "✅" if r["ok"] else "❌"
        lines.append(f"| {r['label']} | {r['provider']} | {r['model']} | {ok} | {r['detail']} |")

    if dead:
        lines += ["", f"> ⚠️ **{len(dead)} model(s) failed liveness — fix routing or funding.**"]

    lines += ["", "## Research", "", research.get("summary", "(none)"), ""]
    recs = research.get("recommendations", [])
    if recs:
        lines += [
            "| Task | Current | Recommend | Current $ | New $ | Saving | Reason |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in recs:
            lines.append(
                f"| {r.get('task','')} | {r.get('current','')} | {r.get('recommend','')} "
                f"| {r.get('current_price_in_out','')} | {r.get('new_price_in_out','')} "
                f"| {r.get('est_monthly_saving','')} | {r.get('reason','')} |"
            )
    noticed = research.get("new_models_noticed", [])
    if noticed:
        lines += ["", "## New models noticed", ""] + [f"- {n}" for n in noticed]

    path.write_text("\n".join(lines), encoding="utf-8")
    return rel


def _insert_proposal_row(today, liveness, dead, research, note_path) -> int | None:
    """Insert a dbo.proposed_changes row. Returns proposal_id or None on failure."""
    try:
        from cortex.db.connection import transaction

        action = {
            "kind": "model_routing_refresh",
            "dead_models": dead,
            "recommendations": research.get("recommendations", []),
            "new_models_noticed": research.get("new_models_noticed", []),
        }
        n_dead = len(dead)
        n_rec = len([r for r in research.get("recommendations", []) if r.get("recommend") not in (None, "", "KEEP")])
        title = f"Model refresh {today}: {n_rec} change(s) suggested, {n_dead} dead"
        with transaction() as conn:
            cur = conn.cursor()
            row = cur.execute(
                """
                INSERT INTO dbo.proposed_changes
                    (proposed_at, category, title, description, rationale, impact,
                     proposed_action, vault_path, status)
                OUTPUT INSERTED.proposal_id
                VALUES (SYSUTCDATETIME(), ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                "model_routing",
                title[:200],
                research.get("summary", "")[:4000],
                "Weekly 7-day model-refresh job (scripts/model_refresh.py).",
                ("Routing changes are manual_only; review and edit config/models.yaml."),
                json.dumps(action),
                note_path,
            ).fetchone()
            return int(row[0]) if row else None
    except Exception as exc:
        log.warning("model_refresh.db_row_failed", error=str(exc))
        return None
