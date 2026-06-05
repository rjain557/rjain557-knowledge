---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-06-05T03:01:49.857565-07:00
---

# Add LLM-compiled wiki synthesis layer (Karpathy pattern) for cross-note knowledge consolidation

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

The vault note 'Part 3: the full stack behind my AI second brain' describes the LLM Wiki pattern where a compilation pass transforms disconnected Markdown notes into a queryable, cross-linked wiki layer — turning the vault from a filing cabinet into an active reasoning surface. The commit history shows a 'synth+lint' feature was added (2026-05-20) but the daily review commits show no evidence of a persistent compiled wiki being maintained or surfaced to consumers. Without a compilation layer, every agent session rediscovers context from scratch, which vault note [3] quantifies as 85% of context budget wasted per run.

## Cited evidence

- Topics/part-3-the-full-stack-behind-my-ai-second-brain-llm-wiki-obs.md
- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context to read first:
1. src/ — scan all Python files, especially any named *synth*, *lint*, *wiki*, or *compile*
2. CLAUDE.md — understand the current agent loop and vault structure
3. knowledge/ — look at 2-3 existing notes to understand the frontmatter schema
4. scripts/ — check for any existing nightly/weekly scheduled scripts

Task: Implement a `scripts/compile_wiki.py` script that runs a nightly LLM compilation pass over the knowledge vault.

Specifically:
1. Scan all Markdown files under `knowledge/` grouped by their `category` or top-level subdirectory (e.g. Topics/, Inbox/, Syntheses/).
2. For each category with >5 notes, call the Anthropic API (use the existing client pattern from src/) with a prompt that asks Claude to:
   - Identify the 3-5 most important recurring concepts across those notes
   - Write a 400-600 word compiled wiki page per concept with cross-links to source notes using `[[wikilink]]` syntax
   - Output valid YAML frontmatter with fields: title, compiled_at (ISO timestamp), source_notes (list of filenames), category
3. Write compiled pages to `knowledge/Wiki/` directory, one file per concept, named `{slug}.md`.
4. If a wiki page for a concept already exists, diff the new content against the old; only overwrite if the new version adds >20% new content (to avoid churn).
5. Append a one-line summary of what was compiled to a `logs/wiki_compile.log` file.

Edge cases:
- Handle rate limits with exponential backoff (max 3 retries)
- Skip notes with frontmatter `draft: true`
- If knowledge/ has fewer than 10 total notes, exit early with a log message
- Do not overwrite any file that was manually edited in the last 24 hours (check mtime)

Verification:
- Run `python scripts/compile_wiki.py --dry-run` and confirm it prints the list of concepts it would create without writing files
- Run once for real and confirm at least one file appears in `knowledge/Wiki/`
- Check that each generated file has valid YAML frontmatter by running `python -c "import frontmatter; frontmatter.load('knowledge/Wiki/<first_file>.md'); print('OK')"`
- Add the script to the existing APScheduler or cron setup so it runs nightly after the main ingestion pass
```
