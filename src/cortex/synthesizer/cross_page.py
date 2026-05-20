"""Cross-page synthesizer — implements the Karpathy LLM-Wiki pattern.

When a new source is ingested OR a Deep Research article is written, find
the top-K existing vault topic notes that are semantically closest (via
VECTOR_SEARCH on the OpenAI embedding) and append a fresh "Update" section
to each, summarizing what the new source corroborates / contradicts /
refines vs the existing topic.

Net effect: one ingest touches ~3-4 existing pages, building up
compounding cross-references over time. Per Karpathy: "the wiki keeps
getting richer with every source you add."

Cost per ingest: 1 vector search (free) + 3 Haiku calls (~$0.01 total).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import structlog

from cortex.config import get_settings
from cortex.db import repositories as repo
from cortex.db.connection import get_connection
from cortex.llm import complete
from cortex.repo_review.vault_search import find_relevant_notes
from cortex.utils.timezone import now_pacific

log = structlog.get_logger(__name__)

_SYSTEM = """You are a wiki synthesizer for a personal knowledge brain.

You receive:
  1. An EXISTING wiki note (its title + body excerpt)
  2. A NEW source just ingested (title + body excerpt)

Your job: decide if the new source materially adds to, refines, or
contradicts the existing note. If so, write a SHORT update paragraph
(2-4 sentences) to append. Otherwise return an empty update.

Output STRICT JSON, no markdown fencing:
{
  "relation": "corroborates" | "refines" | "contradicts" | "tangential",
  "update_text": "the paragraph to append (or empty string if relation=tangential)",
  "headline": "5-12 word summary for the update section header"
}

Rules:
- If `tangential`, return empty update_text and a generic headline. Don't pad.
- If `contradicts`, lead the update with "⚠️ CONTRADICTION:" so it's
  scannable when the reviewer lints later.
- Cite the new source title in the update (the lint pass relies on this).
- Don't repeat content already in the existing note — only the delta.
- Keep technical claims tight; no marketing prose.
"""


@dataclass
class UpdateAction:
    note_id: int
    vault_path: str
    relation: str
    headline: str
    update_text: str
    distance: float


def synthesize_cross_page_updates(
    *,
    new_source_title: str,
    new_source_body: str,
    primary_domain: str | None = None,
    top_k: int = 3,
    min_distance: float = 0.55,
    skip_note_ids: set[int] | None = None,
) -> list[UpdateAction]:
    """Find top-K similar existing notes, decide updates, append to vault files.

    skip_note_ids — note_ids to exclude from the candidate set (typically
    the new source's own note + the just-written DR topic, to avoid
    self-updates).
    """
    settings = get_settings()
    vault = settings.vault_path
    skip_note_ids = skip_note_ids or set()

    query = f"{new_source_title}\n\n{new_source_body[:6000]}"
    candidates = find_relevant_notes(query, top_k=top_k + len(skip_note_ids),
                                     domain=primary_domain)
    candidates = [c for c in candidates if c["note_id"] not in skip_note_ids][:top_k]

    if not candidates:
        log.info("synthesizer.no_candidates",
                 source_title=new_source_title[:60])
        return []

    actions: list[UpdateAction] = []
    for cand in candidates:
        if cand["distance"] > min_distance:
            # Too far — skip
            log.debug("synthesizer.too_far",
                      note_id=cand["note_id"], distance=cand["distance"])
            continue

        try:
            verdict = _ask_should_update(
                existing_title=cand["title"],
                existing_preview=cand["preview"],
                new_title=new_source_title,
                new_body=new_source_body,
            )
        except Exception as exc:
            log.warning("synthesizer.llm_error",
                        note_id=cand["note_id"], error=str(exc)[:200])
            continue

        relation = verdict.get("relation", "tangential")
        update_text = (verdict.get("update_text") or "").strip()
        headline = (verdict.get("headline") or "Update").strip()[:120]

        if relation == "tangential" or not update_text:
            log.debug("synthesizer.skip_tangential",
                      note_id=cand["note_id"])
            continue

        action = UpdateAction(
            note_id=cand["note_id"],
            vault_path=cand["vault_path"],
            relation=relation,
            headline=headline,
            update_text=update_text,
            distance=cand["distance"],
        )
        if _append_update_to_vault(vault, action):
            actions.append(action)

    if actions:
        log.info("synthesizer.applied",
                 source=new_source_title[:60], updates=len(actions),
                 candidates=len(candidates))
        # Re-embed the updated notes so future VECTOR_SEARCH reflects the
        # new content
        for a in actions:
            try:
                repo.embed_note(a.note_id)
            except Exception:
                pass
    return actions


def _ask_should_update(*, existing_title: str, existing_preview: str,
                       new_title: str, new_body: str) -> dict:
    user_msg = (
        f"## EXISTING wiki note\n\n"
        f"**Title:** {existing_title}\n\n"
        f"**Body excerpt:**\n{existing_preview[:3000]}\n\n"
        f"## NEW source just ingested\n\n"
        f"**Title:** {new_title}\n\n"
        f"**Body excerpt:**\n{new_body[:4000]}\n\n"
        f"---\n\nReturn the verdict JSON now."
    )
    raw = complete(
        system=_SYSTEM,
        prompt=user_msg,
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        temperature=0.1,
    )
    raw = re.sub(r"^```[a-z]*\n?|```\s*$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


def _append_update_to_vault(vault: Path, action: UpdateAction) -> bool:
    """Append the update section to the vault file. Returns True on success."""
    fpath = vault / action.vault_path.replace("/", "\\")
    if not fpath.exists():
        log.warning("synthesizer.vault_missing", path=str(fpath))
        return False

    try:
        current = fpath.read_text(encoding="utf-8")
        # Avoid re-appending if we already have an update with the same headline
        if f"## Update ({_today_str()}) — {action.headline}" in current:
            log.debug("synthesizer.already_appended", path=action.vault_path)
            return False

        appended = current.rstrip() + "\n\n"
        appended += f"## Update ({_today_str()}) — {action.headline}\n\n"
        appended += f"_relation: **{action.relation}** · cosine distance: {action.distance:.3f}_\n\n"
        appended += action.update_text.strip() + "\n"

        fpath.write_text(appended, encoding="utf-8")
        return True
    except Exception as exc:
        log.warning("synthesizer.write_error",
                    path=str(fpath), error=str(exc)[:200])
        return False


def _today_str() -> str:
    return now_pacific().strftime("%Y-%m-%d")
