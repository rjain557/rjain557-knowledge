---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-02T03:02:04.796423-07:00
---

# Implement LLM-wiki cross-page synthesis as a scheduled nightly job (Karpathy pattern already referenced in commits but verify completeness)

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Commit 2026-05-20 references 'Karpathy LLM-Wiki pattern (cross-page synth + nightly lint)' but vault note [4] ('The AI Second Brain Stack: LLM Wiki, Obsidian, and Agent-Orchestrated PKM') explains the full pattern requires a compilation step that produces a single coherent wiki page per topic from all source notes — not just linking them. If the current implementation only lints and links without producing compiled topic summaries, the vault remains a retrieval surface rather than a reasoning surface. Verifying and completing this compilation step would make the daily repo-review prompts significantly more grounded.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Topics/get-rid-of-obsidian-fyp-claudecode-aiagents-kycoai.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - src/  (find the synth/lint module introduced in commit 2026-05-20 — search for 'synth', 'lint', 'wiki')
  - knowledge/Topics/  (list directory — do not read all files, just understand naming convention)
  - knowledge/  (look for any existing compiled wiki pages, e.g. knowledge/wiki/ or knowledge/compiled/)
  - CLAUDE.md

Goal: Verify whether the Karpathy LLM-wiki compilation step actually produces per-topic compiled pages, and if not, implement it.

Audit first:
  1. Open the synth module. Does it produce a compiled output file per topic (e.g., knowledge/wiki/<topic>.md) that synthesizes ALL notes tagged with that topic into a single coherent narrative?
  2. Or does it only add backlinks / frontmatter tags?
  If it already produces compiled pages, output a short audit report and stop.

If compilation is missing, implement src/synth/wiki_compiler.py:
  `compile_topic(topic: str, source_notes: list[Path], out_dir: Path, llm_client) -> Path`:
    a. Read all source_notes bodies (strip frontmatter).
    b. Build a prompt:
       'You are a technical wiki editor. Given the following {N} notes all tagged [{topic}], write a single coherent 600-900 word wiki article. Use ## subheadings. Cite source note slugs inline as [slug]. Do not repeat information. Prioritize the most recent notes when there is conflict.'
       Append each note body with a slug header.
    c. Call the LLM (use the existing multi-provider router introduced 2026-05-24 — find it in src/).
    d. Write output to out_dir/<topic-slug>.md with frontmatter:
       ---
       title: <topic>
       compiled_at: <ISO UTC>
       source_count: <N>
       tags: [wiki, <topic>]
       ---
    e. Return the output path.

  `compile_all_topics(vault_dir: Path, out_dir: Path, llm_client, min_sources: int = 3) -> None`:
    a. Scan vault_dir for all unique tags across all notes.
    b. For each tag with >= min_sources notes, call compile_topic.
    c. Skip tags that already have a compiled page newer than the newest source note (incremental).

Schedule:
  Add a nightly job (03:00 America/Los_Angeles) in the APScheduler setup that calls compile_all_topics.

Edge cases:
  - LLM call may fail for a topic; catch and log, continue to next topic.
  - Compiled pages must not be fed back into the compiler as source notes (exclude out_dir from source scan).
  - If a topic has >20 source notes, chunk them: compile in groups of 10, then compile the compiled summaries.

Verification:
  1. Run `python -m src.synth.wiki_compiler` with --dry-run flag that prints which topics would be compiled.
  2. Run for one topic with 3+ notes and inspect the output .md file.
  3. Confirm the compiled page has correct frontmatter and inline slug citations.
  4. Confirm the scheduler job appears in logs.
```
