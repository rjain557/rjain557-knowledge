"""Use Claude Sonnet 4.6 to produce structured improvement prompts for a repo,
informed by what Cortex's vault already knows about that domain.

Output shape: list[ImprovementPrompt] where each is a self-contained
markdown file the dev can run as a single Claude Code / Codex prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from cortex.llm import complete
from cortex.repo_review.lister import RepoContext
from cortex.repo_review.vault_search import find_relevant_notes
from cortex.utils.timezone import now_pacific

log = structlog.get_logger(__name__)


_SYSTEM = """You are a senior staff engineer doing a code review for one
repository inside Technijian's mono-org. Your job is to recommend 3-5
concrete, high-leverage improvements the team can act on right now.

You will be given:
  1. Repo metadata, README, last 30 commits, top-level file tree, and a
     few key config files.
  2. Up to 10 notes from Technijian's internal knowledge brain that the
     vector store flagged as potentially relevant (forwarded AI/SEO/
     tech-support articles + deep-research syntheses).

For each improvement you propose, output a JSON object with this shape:
{
  "title": "short imperative",
  "rationale": "1-3 sentences: what's currently sub-optimal, what would be better, why now",
  "impact": "low | medium | high",
  "effort": "S (<1 day) | M (<1 week) | L (>1 week)",
  "cited_notes": ["vault_path or title of vault note that informed this"],
  "prompt": "the COMPLETE, paste-into-Claude-Code prompt the dev will run. Include: working directory, files to read first, the change to make, edge cases to consider, how to verify. Keep it focused on ONE atomic improvement."
}

Quality rules:
  - Only propose improvements that are TRACEABLE to either (a) something
    you actually see in the repo context or (b) a vault note. No vague
    'add more tests' boilerplate.
  - When you cite a vault note, the rationale must reference what that
    note specifically says.
  - The prompt field is the ENTIRE thing a dev would copy into Claude
    Code from the repo root. Include explicit file paths.
  - Prefer improvements that align with the repo's stated domain
    (agent-orchestration / seo-agents / tech-support-agents / office-ops).
  - If you can't find 3 high-quality improvements, return fewer. Don't
    pad.

Return STRICT JSON: { "summary": "1-line repo summary", "improvements": [...] }
NO markdown fences, NO prose outside the JSON.
"""


@dataclass
class ImprovementPrompt:
    title: str
    rationale: str
    impact: str
    effort: str
    cited_notes: list[str]
    prompt: str


@dataclass
class RepoAnalysis:
    repo: str
    summary: str
    improvements: list[ImprovementPrompt]
    raw_response: str
    vault_hits: list[dict]


def analyze_repo(ctx: RepoContext, *, domain: str,
                 model: str = "claude-sonnet-4-6",
                 max_prompts: int = 5) -> RepoAnalysis:
    log.info("analyzer.start", repo=ctx.full_name, domain=domain, model=model)

    # Build query text for vault search — summary of what this repo seems to be
    query_text = (
        f"{ctx.full_name} ({ctx.language}). {ctx.description}\n\n"
        f"README excerpt:\n{ctx.readme[:5000]}\n\n"
        f"Recent commits:\n" +
        "\n".join(f"- {c['date']} {c['message']}" for c in ctx.recent_commits[:10])
    )
    vault_hits = find_relevant_notes(query_text, top_k=10, domain=domain)

    vault_block = ""
    if vault_hits:
        vault_block = "\n\n## Relevant vault notes (Cortex knowledge brain):\n\n"
        for i, v in enumerate(vault_hits, 1):
            vault_block += (
                f"### [{i}] {v['title']} ({v['note_type']} / {v.get('domain','?')})\n"
                f"_path: {v['vault_path']}, distance: {v['distance']:.3f}_\n\n"
                f"{v['preview']}\n\n"
            )

    files_block = "\n".join(f"- {f}" for f in ctx.top_files[:30])
    samples_block = ""
    for path, body in ctx.sample_files.items():
        samples_block += f"\n\n### {path}\n```\n{body[:2000]}\n```\n"

    commits_block = "\n".join(
        f"- {c['date']} [{c['sha']}] {c['author']}: {c['message']}"
        for c in ctx.recent_commits
    )

    user_msg = f"""# Repository: {ctx.full_name}

**Primary domain:** {domain}
**Language:** {ctx.language}
**Default branch:** {ctx.default_branch}
**Description:** {ctx.description}

## README
{ctx.readme[:8000]}

## Top-level files
{files_block}

## Sample config files
{samples_block or '(none readable)'}

## Recent commits (last 30)
{commits_block}

{vault_block}

---

Return up to {max_prompts} improvements in the JSON shape above.
"""

    raw = complete(
        system=_SYSTEM,
        prompt=user_msg,
        model=model,
        max_tokens=8000,
        temperature=0.2,
    )

    try:
        data = _parse_json(raw)
    except Exception as exc:
        log.warning("analyzer.parse_failed", error=str(exc), raw_head=raw[:300])
        return RepoAnalysis(repo=ctx.full_name, summary="(parse failed)",
                            improvements=[], raw_response=raw,
                            vault_hits=vault_hits)

    improvements = []
    for item in data.get("improvements", [])[:max_prompts]:
        try:
            improvements.append(ImprovementPrompt(
                title=str(item.get("title", "Untitled"))[:200],
                rationale=str(item.get("rationale", ""))[:2000],
                impact=str(item.get("impact", "medium")),
                effort=str(item.get("effort", "M")),
                cited_notes=[str(c) for c in (item.get("cited_notes") or [])][:8],
                prompt=str(item.get("prompt", ""))[:8000],
            ))
        except Exception:
            continue

    log.info("analyzer.done", repo=ctx.full_name,
             improvements=len(improvements),
             vault_hits=len(vault_hits))

    return RepoAnalysis(
        repo=ctx.full_name,
        summary=str(data.get("summary", ""))[:500],
        improvements=improvements,
        raw_response=raw,
        vault_hits=vault_hits,
    )


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```[a-z]*\n?|```\s*$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)
