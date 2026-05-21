"""Weekly curated topic refresh.

For each evergreen theme in config/refresh-topics.yaml, run a single
time-boxed Claude web_search ("what's NEW about {theme} since {date}?"),
then append a `## Refresh (YYYY-MM-DD)` digest section to the theme's
living page at Topics/_refresh-{slug}.md. The "since" date is read from
the most recent existing digest section (or default_lookback_days on the
first run).

Deliberately cheap: ~$0.30/theme with Sonnet + ~2 searches. ~15 themes
weekly = ~$18/month, vs ~$725/month to re-research all 122 topics.

Net effect: the high-value evergreen subjects stay current without
blindly re-searching the whole vault.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import structlog
import yaml
from anthropic import Anthropic

from cortex.config import get_settings
from cortex.db.connection import get_connection
from cortex.utils.timezone import now_pacific

log = structlog.get_logger(__name__)

REFRESH_PREFIX = "_refresh-"


@dataclass
class RefreshResult:
    slug: str
    theme_query: str
    domain: str
    new_sources: int
    searches_used: int
    cost_usd: float
    digest_path: str
    since_date: str
    status: str = "ok"
    error: str | None = None


def load_config() -> dict:
    from cortex import __file__ as cortex_init
    repo_root = Path(cortex_init).resolve().parents[2]
    with open(repo_root / "config" / "refresh-topics.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


_PRICES = {  # USD per million tokens
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
}
_PER_SEARCH = 0.01


def _theme_digest_path(vault: Path, slug: str) -> Path:
    return vault / "Topics" / f"{REFRESH_PREFIX}{slug}.md"


def _last_refresh_date(path: Path, default_days: int) -> str:
    """Most recent ## Refresh (YYYY-MM-DD) in the digest, else N days ago."""
    fallback = (now_pacific() - timedelta(days=default_days)).strftime("%Y-%m-%d")
    if not path.exists():
        return fallback
    dates = re.findall(r"##\s*Refresh\s*\((\d{4}-\d{2}-\d{2})\)", path.read_text(encoding="utf-8"))
    return max(dates) if dates else fallback


def _system_prompt(since: str) -> str:
    return f"""You are a research scout for a knowledge brain. Find content
about a given theme that was published AFTER {since}.

Use web_search to look specifically for RECENT material (articles, papers,
GitHub releases, videos, blog posts) published since {since}. Ignore
anything older — we already have it.

Return STRICT JSON, no markdown fencing:
{{
  "new_sources": [
    {{
      "title": "...",
      "url": "...",
      "published": "approx date if known, else ''",
      "why_it_matters": "1 sentence — what NEW thing this adds"
    }}
  ],
  "summary": "2-3 sentences on what changed in this theme since {since}, or 'No significant new developments.' if nothing genuinely new."
}}

Rules:
- Only include genuinely NEW, authoritative sources from after {since}.
- If nothing meaningfully new exists, return an empty new_sources list and
  say so in summary. Do NOT pad with old or low-quality results.
- Max 8 sources. Quality over quantity.
"""


def refresh_theme(theme: dict, cfg: dict) -> RefreshResult:
    settings = get_settings()
    vault = settings.vault_path
    slug = theme["slug"]
    query = theme["query"]
    domain = theme.get("domain", "agent-orchestration")
    model = cfg.get("model", "claude-sonnet-4-6")
    max_searches = int(cfg.get("max_searches_per_theme", 4))
    default_lookback = int(cfg.get("default_lookback_days", 14))

    digest_path = _theme_digest_path(vault, slug)
    since = _last_refresh_date(digest_path, default_lookback)

    log.info("refresh.theme.start", slug=slug, since=since, model=model)

    client = Anthropic(api_key=settings.anthropic_api_key)
    messages = [{"role": "user",
                 "content": f"Theme: {query}\n\nFind what's new since {since}. Return the JSON."}]
    total_in = total_out = searches = 0
    last = None
    try:
        for _ in range(12):
            resp = client.messages.create(
                model=model, max_tokens=4000,
                system=_system_prompt(since), messages=messages,
                tools=[{"type": "web_search_20250305", "name": "web_search",
                        "max_uses": max_searches}],
            )
            total_in += resp.usage.input_tokens
            total_out += resp.usage.output_tokens
            last = resp
            for b in resp.content:
                if getattr(b, "type", None) == "server_tool_use" and getattr(b, "name", None) == "web_search":
                    searches += 1
            if resp.stop_reason == "end_turn":
                break
            if resp.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": resp.content})
                continue
            break
        text = "".join(getattr(b, "text", "") for b in last.content
                       if getattr(b, "type", None) == "text")
        data = _parse_json(text)
    except Exception as exc:
        log.warning("refresh.theme.error", slug=slug, error=str(exc)[:200])
        return RefreshResult(slug=slug, theme_query=query, domain=domain,
                             new_sources=0, searches_used=searches,
                             cost_usd=_cost(model, total_in, total_out, searches),
                             digest_path="", since_date=since,
                             status="failed", error=str(exc)[:300])

    new_sources = data.get("new_sources", []) or []
    summary = (data.get("summary") or "").strip()
    cost = _cost(model, total_in, total_out, searches)

    _append_digest(digest_path, slug, query, domain, since,
                   new_sources, summary, cost)

    log.info("refresh.theme.done", slug=slug, new=len(new_sources),
             searches=searches, cost=round(cost, 3))
    return RefreshResult(slug=slug, theme_query=query, domain=domain,
                         new_sources=len(new_sources), searches_used=searches,
                         cost_usd=cost,
                         digest_path=str(digest_path.relative_to(vault)).replace("\\", "/"),
                         since_date=since)


def _append_digest(path: Path, slug: str, query: str, domain: str,
                   since: str, new_sources: list, summary: str, cost: float) -> None:
    today = now_pacific().strftime("%Y-%m-%d")
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        header = (
            f"---\n"
            f"type: topic\n"
            f"subtype: refresh-digest\n"
            f"domain: {domain}\n"
            f"theme_slug: {slug}\n"
            f"generated_by: cortex-topic-refresh\n"
            f"volatility: evolving\n"
            f"---\n\n"
            f"# Refresh digest — {query}\n\n"
            f"_Living page. Each weekly run appends a `## Refresh` section with "
            f"genuinely new sources on this theme. Maintained by "
            f"`cortex.topic_refresh`._\n"
        )
        path.write_text(header, encoding="utf-8")

    block = [f"\n## Refresh ({today}) — window since {since}\n"]
    if new_sources:
        block.append(f"_{len(new_sources)} new source(s). {summary}_\n")
        for s in new_sources:
            title = (s.get("title") or "untitled").strip()
            url = (s.get("url") or "").strip()
            pub = (s.get("published") or "").strip()
            why = (s.get("why_it_matters") or "").strip()
            pub_str = f" ({pub})" if pub else ""
            block.append(f"- [{title}]({url}){pub_str} — {why}")
    else:
        block.append(f"_No significant new developments. {summary}_")
    block.append(f"\n_(refresh cost ${cost:.3f})_\n")

    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(block) + "\n")


def run_weekly_refresh(max_themes: int | None = None) -> dict:
    cfg = load_config()
    themes = cfg.get("themes", []) or []
    if max_themes is None:
        max_themes = int(cfg.get("max_themes_per_run", 20))

    results: list[RefreshResult] = []
    for theme in themes[:max_themes]:
        try:
            results.append(refresh_theme(theme, cfg))
        except Exception as exc:
            log.error("refresh.exception", slug=theme.get("slug"), error=str(exc)[:200])
            results.append(RefreshResult(
                slug=theme.get("slug", "?"), theme_query=theme.get("query", ""),
                domain=theme.get("domain", ""), new_sources=0, searches_used=0,
                cost_usd=0.0, digest_path="", since_date="",
                status="exception", error=str(exc)[:300]))

    total_new = sum(r.new_sources for r in results)
    total_cost = sum(r.cost_usd for r in results)
    summary = {
        "themes_refreshed": len(results),
        "total_new_sources": total_new,
        "total_cost_usd": round(total_cost, 2),
        "failed": sum(1 for r in results if r.status != "ok"),
        "results": [r.__dict__ for r in results],
    }
    log.info("refresh.batch_done", **{k: v for k, v in summary.items() if k != "results"})
    return summary


def _cost(model: str, tin: int, tout: int, searches: int) -> float:
    pin, pout = _PRICES.get(model, (3.0, 15.0))
    return tin * pin / 1e6 + tout * pout / 1e6 + searches * _PER_SEARCH


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?|```\s*$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)
