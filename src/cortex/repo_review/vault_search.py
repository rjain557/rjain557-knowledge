"""VECTOR_SEARCH against dbo.notes to find vault knowledge relevant to a repo.

Uses the activated OpenAI EmbeddingModel + SQL Server 2025 VECTOR_DISTANCE.
"""

from __future__ import annotations

import structlog

from cortex.db.connection import get_connection

log = structlog.get_logger(__name__)


def find_relevant_notes(query_text: str, *, top_k: int = 10,
                        domain: str | None = None) -> list[dict]:
    """Return up to top_k vault notes whose embedding is closest to query_text.

    domain — optional filter (agent-orchestration | seo-agents |
    tech-support-agents | office-ops); when set, biases the search to
    notes scoring above 0.3 for that domain in dbo.relevance_scores.
    """
    if not query_text or len(query_text.strip()) < 10:
        return []

    # Only the 3 SPEC domains have rows in dbo.relevance_scores.
    # 'office-ops' / unknown -> no filter (fall back to global vector search).
    _SCORED_DOMAINS = {"agent-orchestration", "seo-agents", "tech-support-agents"}
    domain_filter = domain if domain in _SCORED_DOMAINS else None

    conn = get_connection()
    rows = conn.execute(
        "EXEC dbo.usp_vector_search_notes @query_text=?, @top_k=?, @domain=?",
        query_text[:30000], int(top_k), domain_filter,
    ).fetchall()
    out = [{"note_id": r.note_id, "vault_path": r.vault_path,
            "title": r.title, "note_type": r.note_type,
            "domain": r.domain, "preview": r.preview,
            "distance": float(r.distance) if r.distance is not None else 1.0}
           for r in rows]
    log.info("vault_search.done", query_chars=len(query_text),
             hits=len(out), top_distance=out[0]["distance"] if out else None)
    return out
