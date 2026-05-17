"""Reusable runner for the GitHub-trending scan. Called by both the CLI
(`scripts/scan_github.py`) and the webhook server's `/github-scan` endpoint.
"""

from __future__ import annotations

import structlog

from cortex.db import repositories as repo
from cortex.deep_research.auto import maybe_auto_research
from cortex.extractors.github import extract as extract_github
from cortex.feeds.github_trending import TrendingRepo, fetch_top_per_category
from cortex.relevance.scorer import score as score_relevance
from cortex.vault.writer import write_inbox_note

log = structlog.get_logger(__name__)


def ingest_repo(tr: TrendingRepo) -> dict:
    """Run the full pipeline on one repo. Returns a result dict."""
    url = tr.url
    log.info("scan_github.ingest", repo=tr.full_name, stars=tr.stars,
             category=tr.category)

    content = extract_github(url)
    if not content:
        log.warning("scan_github.extract_failed", repo=tr.full_name)
        repo.record_link(original_url=url, source_type="github", email_id=None)
        return {"status": "extract_failed", "url": url}

    try:
        scores = score_relevance(content.title, content.body_markdown)
    except Exception as exc:
        log.warning("scan_github.score_error", error=str(exc)[:200])
        scores = {}

    link_id = repo.record_link(
        original_url=url, source_type="github", email_id=None,
        canonical_url=content.canonical_url,
    )
    source_id = repo.upsert_source(
        source_url=url,
        source_type="github",
        title=content.title,
        author=content.author,
        published_at=content.published_at,
        body_markdown=content.body_markdown,
        metadata={**content.metadata,
                  "discovered_via": "github_trending",
                  "discovery_category": tr.category,
                  "discovery_stars": tr.stars,
                  "discovery_license": tr.license,
                  "discovery_topics": tr.topics},
        link_id=link_id,
        canonical_url=content.canonical_url,
        extractor="github_trending",
    )
    if scores:
        repo.record_relevance_scores(source_id, scores)

    vault_path, note_id = write_inbox_note(content, source_id, scores)

    dr_decision, dr_reason = ("skipped", "no scores")
    if scores:
        try:
            dr_decision, dr_reason = maybe_auto_research(
                source_id=source_id,
                title=content.title,
                body_markdown=content.body_markdown,
                primary_domain=max(scores, key=scores.get),
                domain_scores=scores,
            )
        except Exception as exc:
            dr_reason = f"error: {exc}"

    return {
        "status": "ingested",
        "url": url, "source_id": source_id, "note_id": note_id,
        "vault_path": vault_path, "scores": scores,
        "auto_dr": dr_decision, "auto_dr_reason": dr_reason,
    }


def run_scan(top_n: int = 5, dry_run: bool = False) -> dict:
    log.info("scan_github.start", top_n=top_n)
    per_category = fetch_top_per_category(top_n=top_n)

    summary = {"checked": 0, "new": 0, "skipped_known": 0,
               "extract_failed": 0, "auto_dr_fired": 0,
               "by_category": {}}

    for cat, repos in per_category.items():
        cat_stats: dict = {"top": [], "new": 0, "skipped": 0}
        for tr in repos:
            summary["checked"] += 1
            cat_stats["top"].append(f"{tr.full_name} ({tr.stars}★)")
            # Skip only if the link has a SUCCESSFUL source row. A bare
            # processed_links entry with no source means an earlier extraction
            # failed (bad token, transient API error) — we want to retry.
            if repo.is_link_ingested(tr.url):
                summary["skipped_known"] += 1
                cat_stats["skipped"] += 1
                log.debug("scan_github.skip_known", repo=tr.full_name)
                continue
            if dry_run:
                summary["new"] += 1
                cat_stats["new"] += 1
                continue
            result = ingest_repo(tr)
            if result["status"] == "ingested":
                summary["new"] += 1
                cat_stats["new"] += 1
                if result.get("auto_dr") == "ran":
                    summary["auto_dr_fired"] += 1
            elif result["status"] == "extract_failed":
                summary["extract_failed"] += 1

        summary["by_category"][cat] = cat_stats

    log.info("scan_github.done", **{k: v for k, v in summary.items()
                                    if k != "by_category"})
    return summary
