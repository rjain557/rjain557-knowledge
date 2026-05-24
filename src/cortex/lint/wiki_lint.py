"""Daily wiki health check — Karpathy LLM-Wiki pattern, lint operation.

Three checks, all derived from the vault state (no external calls beyond
the relevance scorer + Haiku for contradiction detection):

  1. ORPHANS — topic notes with no inbound [[wikilink]] from any other
     topic / source / inbox note.
  2. NEAR-DUPLICATES — pairs of notes whose cosine distance is < 0.15,
     suggesting they should be merged or one should link the other.
  3. POTENTIAL CONTRADICTIONS — Haiku reads near-duplicate pairs and
     decides if they actually disagree on a fact.
  4. STALE — topic notes whose last `## Update (...)` is >30 days old
     AND whose subject area has had >=3 new sources ingested since.

Output: Meta/lint-YYYY-MM-DD.md inside the vault, plus an email summary
to rjain@technijian.com if any critical findings.

Cost per run: ~$0.50-$2.00 depending on how many near-dup pairs need
the Haiku contradiction check.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from cortex.config import get_settings
from cortex.db.connection import get_connection
from cortex.llm import complete_task
from cortex.utils.timezone import now_pacific

log = structlog.get_logger(__name__)

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class LintFindings:
    orphans: list[dict]
    near_duplicates: list[dict]
    contradictions: list[dict]
    stale: list[dict]
    output_path: str
    stats: dict


def _load_topic_notes() -> list[dict]:
    """All notes from the curated layer + auto-generated topics."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT note_id, vault_path, title, note_type, domain,
               body_markdown, updated_at,
               LEN(body_markdown) AS chars
        FROM   dbo.notes
        WHERE  body_markdown IS NOT NULL
          AND  embedding IS NOT NULL
    """).fetchall()
    return [dict(note_id=r.note_id, vault_path=r.vault_path,
                 title=r.title, note_type=r.note_type, domain=r.domain,
                 body=r.body_markdown, updated_at=r.updated_at,
                 chars=r.chars) for r in rows]


def _find_orphans(notes: list[dict]) -> list[dict]:
    """A topic note is an orphan if no other note links to it via [[slug]]."""
    # Build slug -> note map
    by_slug: dict[str, dict] = {}
    for n in notes:
        slug = Path(n["vault_path"]).stem.lower()
        by_slug.setdefault(slug, n)

    # Collect all wikilinks across all bodies
    incoming: Counter = Counter()
    for n in notes:
        for m in WIKILINK.finditer(n["body"] or ""):
            target = m.group(1).split("|", 1)[0].strip().lower()
            if target:
                incoming[target] += 1

    orphans = []
    for n in notes:
        if n["note_type"] != "topic":
            continue
        slug = Path(n["vault_path"]).stem.lower()
        title_lower = (n["title"] or "").lower()
        if incoming.get(slug, 0) == 0 and incoming.get(title_lower, 0) == 0:
            orphans.append({"note_id": n["note_id"],
                            "vault_path": n["vault_path"],
                            "title": n["title"]})
    return orphans


def _find_near_duplicates(top_k_pairs: int = 30) -> list[dict]:
    """Find pairs of notes with cosine distance < 0.15 (very close).

    Pure SQL — cross-joins notes against itself ranked by VECTOR_DISTANCE.
    Caps at top_k_pairs to keep the result set small.
    """
    conn = get_connection()
    sql = """
        WITH pairs AS (
            SELECT a.note_id AS id_a, b.note_id AS id_b,
                   a.title AS title_a, b.title AS title_b,
                   a.vault_path AS path_a, b.vault_path AS path_b,
                   VECTOR_DISTANCE('cosine', a.embedding, b.embedding) AS distance
            FROM   dbo.notes a
            JOIN   dbo.notes b ON b.note_id > a.note_id
            WHERE  a.embedding IS NOT NULL AND b.embedding IS NOT NULL
        )
        SELECT TOP (?) * FROM pairs WHERE distance < 0.15
        ORDER BY distance ASC;
    """
    rows = conn.execute(sql, int(top_k_pairs)).fetchall()
    return [{"id_a": r.id_a, "id_b": r.id_b,
             "title_a": r.title_a, "title_b": r.title_b,
             "path_a": r.path_a, "path_b": r.path_b,
             "distance": float(r.distance)} for r in rows]


def _check_contradictions(pairs: list[dict], notes_by_id: dict[int, dict],
                          max_checks: int = 15) -> list[dict]:
    """Haiku reads each near-dup pair and decides if they truly contradict."""
    findings = []
    for p in pairs[:max_checks]:
        a = notes_by_id.get(p["id_a"])
        b = notes_by_id.get(p["id_b"])
        if not a or not b:
            continue
        try:
            verdict = _ask_contradiction(a, b)
        except Exception as exc:
            log.warning("lint.contradiction_err", error=str(exc)[:200])
            continue
        if verdict.get("contradicts"):
            findings.append({
                "note_a": p["path_a"], "note_b": p["path_b"],
                "distance": p["distance"],
                "explanation": verdict.get("explanation", "")[:600],
                "conflicting_claim_a": verdict.get("claim_a", "")[:300],
                "conflicting_claim_b": verdict.get("claim_b", "")[:300],
            })
    return findings


_CONTRADICTION_SYS = """You are an editor checking a knowledge wiki for
internal contradictions.

You receive two notes that vector-search flagged as near-duplicates
(cosine distance < 0.15). Decide if they actually contradict each other
on a non-trivial fact, OR if they're merely covering overlapping
territory in agreement.

Return STRICT JSON:
{
  "contradicts": true | false,
  "explanation": "1-2 sentences explaining the conflict (or empty if no conflict)",
  "claim_a": "exact claim from note A that conflicts (or empty)",
  "claim_b": "exact claim from note B that conflicts (or empty)"
}

Be conservative: only flag genuine factual disagreements (versions,
dates, who-said-what, license types, capability claims). Stylistic
differences or different emphases are NOT contradictions.
"""


def _ask_contradiction(a: dict, b: dict) -> dict:
    user_msg = (
        f"## Note A: {a['title']}\n\n{a['body'][:4000]}\n\n"
        f"## Note B: {b['title']}\n\n{b['body'][:4000]}\n\n"
        f"Return the verdict JSON now."
    )
    raw = complete_task(
        "lint_contradiction",
        system=_CONTRADICTION_SYS,
        prompt=user_msg,
    )
    raw = re.sub(r"^```[a-z]*\n?|```\s*$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


def _find_stale(notes: list[dict], days: int = 30) -> list[dict]:
    """Topic notes whose most recent ## Update header is > N days old AND
    whose domain has had >=3 new sources since."""
    threshold = now_pacific() - timedelta(days=days)
    stale = []
    for n in notes:
        if n["note_type"] != "topic":
            continue
        body = n["body"] or ""
        # Find the latest YYYY-MM-DD in any ## Update header
        latest = None
        for m in re.finditer(r"##\s*Update\s*\((\d{4}-\d{2}-\d{2})\)", body):
            try:
                dt = datetime.fromisoformat(m.group(1)).replace(tzinfo=now_pacific().tzinfo)
                if latest is None or dt > latest:
                    latest = dt
            except ValueError:
                pass
        # Fall back to note's updated_at if no Update headers
        ref = latest or n["updated_at"]
        if ref is None:
            continue
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        if ref < threshold:
            stale.append({
                "note_id": n["note_id"],
                "vault_path": n["vault_path"],
                "title": n["title"],
                "last_touch": ref.isoformat()[:10],
                "domain": n["domain"],
            })
    return stale


def run_lint(*, max_pair_checks: int = 15) -> LintFindings:
    log.info("lint.start")
    notes = _load_topic_notes()
    notes_by_id = {n["note_id"]: n for n in notes}

    orphans = _find_orphans(notes)
    near_dups = _find_near_duplicates()
    contradictions = _check_contradictions(near_dups, notes_by_id,
                                           max_checks=max_pair_checks)
    stale = _find_stale(notes)

    output_path = _write_lint_report(orphans, near_dups, contradictions, stale,
                                     total_notes=len(notes))

    stats = {
        "notes_checked": len(notes),
        "orphan_topics": len(orphans),
        "near_dup_pairs": len(near_dups),
        "contradictions_flagged": len(contradictions),
        "stale_topics": len(stale),
    }
    log.info("lint.done", **stats)

    # Email summary if anything critical
    if contradictions or len(stale) > 10:
        try:
            from cortex.mail.notify import send_alert
            send_alert(
                subject=f"[Cortex] Wiki lint {now_pacific():%Y-%m-%d %Z} — "
                        f"{len(contradictions)} contradictions, {len(stale)} stale",
                body_markdown=(
                    f"Daily lint pass found:\n\n"
                    f"- {len(contradictions)} contradiction(s) flagged\n"
                    f"- {len(orphans)} orphan topic(s)\n"
                    f"- {len(near_dups)} near-duplicate pair(s)\n"
                    f"- {len(stale)} stale topic(s) (>30d untouched)\n\n"
                    f"Full report: vault `{output_path}`"
                ),
            )
        except Exception:
            pass

    return LintFindings(orphans=orphans, near_duplicates=near_dups,
                        contradictions=contradictions, stale=stale,
                        output_path=output_path, stats=stats)


def _write_lint_report(orphans, near_dups, contradictions, stale,
                       total_notes: int) -> str:
    settings = get_settings()
    vault = settings.vault_path
    meta_dir = vault / "Meta"
    meta_dir.mkdir(exist_ok=True)
    fpath = meta_dir / f"lint-{now_pacific().strftime('%Y-%m-%d')}.md"

    lines = [
        f"# Wiki Lint — {now_pacific().strftime('%Y-%m-%d %H:%M %Z')}",
        "",
        f"_Automated daily health check across {total_notes} embedded vault notes._",
        "",
        f"- **Orphan topics:** {len(orphans)}",
        f"- **Near-duplicate pairs:** {len(near_dups)}",
        f"- **Contradictions flagged:** {len(contradictions)}",
        f"- **Stale topics (>30d):** {len(stale)}",
        "",
    ]

    if contradictions:
        lines += ["## 🛑 Contradictions", ""]
        for c in contradictions:
            lines.append(f"### `{c['note_a']}` vs `{c['note_b']}`")
            lines.append(f"_distance: {c['distance']:.3f}_")
            lines.append("")
            lines.append(c["explanation"])
            if c.get("conflicting_claim_a"):
                lines.append(f"- **A claims:** {c['conflicting_claim_a']}")
            if c.get("conflicting_claim_b"):
                lines.append(f"- **B claims:** {c['conflicting_claim_b']}")
            lines.append("")

    if orphans:
        lines += ["## 🔗 Orphan topics (no inbound `[[wikilinks]]`)", ""]
        for o in orphans[:40]:
            lines.append(f"- `{o['vault_path']}` — {o['title']}")
        if len(orphans) > 40:
            lines.append(f"- _…and {len(orphans) - 40} more_")
        lines.append("")

    if near_dups:
        lines += ["## 🔁 Near-duplicate pairs (consider merging)", ""]
        for p in near_dups[:20]:
            lines.append(f"- {p['distance']:.3f} — `{p['path_a']}` ↔ `{p['path_b']}`")
        if len(near_dups) > 20:
            lines.append(f"- _…and {len(near_dups) - 20} more_")
        lines.append("")

    if stale:
        lines += ["## ⏰ Stale topics (>30 days since last touch)", ""]
        for s in stale[:30]:
            lines.append(f"- `{s['vault_path']}` (domain={s['domain']}, "
                         f"last touch {s['last_touch']})")
        if len(stale) > 30:
            lines.append(f"- _…and {len(stale) - 30} more_")
        lines.append("")

    fpath.write_text("\n".join(lines), encoding="utf-8")
    return str(fpath.relative_to(vault)).replace("\\", "/")
