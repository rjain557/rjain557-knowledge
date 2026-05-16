# Cortex / Inbox Brain — Project Guidance

This file is read by Claude Code on every session. It defers to `docs/SPEC.md` for system specification and to the Obsidian vault (see below) for accumulated knowledge.

## What this project is

A self-improving knowledge brain across three AI domains: **agent-orchestration**, **seo-agents**, **tech-support-agents**. Ingests M365 mail + RSS/arXiv/GitHub trending/benchmark feeds, synthesizes patterns into an Obsidian vault and SQL Server 2025, exposes everything to consumer Claude Code repos via MCP, and reviews itself every 7 days. See `docs/SPEC.md` for the full v4 spec.

Implementation is pre-Phase-1 — only the spec exists.

## Key files (always defer to these)

- `docs/SPEC.md` — full system spec; canonical
- `sql/migrations/` — schema source of truth (when added)
- `config/target-domains.yaml` — the three domains (when added)
- `config/tracked-feeds.yaml` — direct feed sources (when added)
- `config/settings.yaml` — reviewer cadence and autonomy bounds (when added)
- `agents/` — subagent prompts (when added)

## Memory + Code Intelligence Stack

This repo has a 4-layer knowledge stack. Read the layer descriptions; respect the boundaries.

### Layer 1 — Obsidian vault (durable human knowledge)

- **Location:** `C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/claude-memory/`
- Index: `claude-memory/index.md`
- Health dashboard: `claude-memory/HEALTH.md`
- Topic pages: `claude-memory/topics/`
- Append-only changelog: `claude-memory/CHANGELOG.md`
- Retrieval log (machine-readable): `claude-memory/.retrieval-log.jsonl`
- Archived pages: `claude-memory/_archive/`
- Vault is a git repo. Every mutation produces a commit with a tag prefix (see CHANGELOG legend).

### Layer 2 — Auto-memory (Claude's working notes)

- **Canonical storage:** `claude-memory/auto-memory/` **inside the Obsidian vault** (OneDrive-synced; **shared with other Claude Code repos** on this account that junction to the same vault path).
- **Harness-visible path:** `C:/Users/Administrator/.claude/projects/d--VSCode-rjain557-knowledge-rjain557-knowledge/memory/` — this is a **directory junction** to the vault location above, so `memory-prefetch.js` reads the same files.
- Index `MEMORY.md` is auto-loaded by `~/.claude/hooks/memory-prefetch.js` on every UserPromptSubmit.
- Use for: feedback (corrections), user preferences, session-spanning project state, references to external systems.
- Do **not** put architectural facts here — those belong in the vault topic pages (`claude-memory/topics/`).
- See `claude-memory/topics/vault_locations.md` for the junction setup details.

### Layer 3 — GitNexus (code structure)

- Installed globally (`gitnexus` CLI in `C:/Users/Administrator/AppData/Roaming/npm/` — once `npm install -g gitnexus` runs on this workstation).
- Hook configured in user-global settings runs on Edit/Write/Bash.
- This repo: index will be built once code lands. Re-indexes on commit/merge via post-tool hook.
- MCP config: `.claude/mcp.json` (when populated).

### Layer 4 — Auto Dream (consolidation, off by default)

- Disabled. Re-enable by flipping `claude-memory/.dream-flag` if Claude grows topics-heavy.

### Monitoring + maintenance

- HEALTH.md is regenerated on SessionEnd by `.claude/hooks/health-check.ps1`.
- Weekly review discipline: run `/review` weekly. Non-negotiable. After 14 days unreviewed, the SessionEnd hook escalates warnings; after 30 days, `/graduate` refuses to give advice until you review.

## Retrieval rules

- Trivial prompts (math, time-of-day) — skip vault retrieval, no log entry.
- Topic / entity prompts — retrieval fires via `.claude/hooks/retrieve.ps1`. The hook updates `access_count` + `last_accessed` in the matched topic's frontmatter and appends a line to `.retrieval-log.jsonl`.
- `claude-memory/preferences.md` is **always** loaded on every retrieval — preferences are universally applicable.

## Write rules

- Topic pages stay in `claude-memory/topics/` — one topic per file.
- Never write transcripts. Distill to the durable shape first.
- Never write outside `claude-memory/` for memory purposes.
- Every mutation appends to CHANGELOG and gets a git commit with the appropriate tag prefix.

## Volatility semantics

Every topic has a `volatility:` frontmatter field. Three tiers, three review cadences:

- **stable** — architectural decisions, domain invariants, immutable facts. Yearly review. Conservative consolidation: strong preference for preserving existing content.
- **evolving** — default. Active development state, current approaches, ongoing concerns. Quarterly review. Normal consolidation.
- **ephemeral** — flaky tests, library workarounds, "current state of X" snapshots. Aggressive review. Auto-archive after 60 days with no `access` and no `last_updated`. Liberal consolidation.

## Contradiction handling (consolidate hook)

Before updating a topic, the consolidate hook compares new info against existing `## Key facts` and `## Decisions & rationale` sections, then classifies:

- **Compatible** — new info extends existing without conflict. Normal update.
- **Clarifying** — new info refines existing. Update in place; note the refinement in CHANGELOG.
- **Contradicting** — new info conflicts. Do **not** overwrite. Append to `## Open questions` ("CONTRADICTION detected on [date]: existing says X, new says Y. Resolve."), preserve both versions, lower `confidence` by one step, append `[contradiction]` to CHANGELOG.
- **Replacing** — only when the user explicitly says the old info was wrong. Overwrite, append `[replaced]` to CHANGELOG.

`stable` topics use a stricter contradiction threshold; `ephemeral` topics overwrite freely (state changes are normal).

## GitNexus rules

- MUST run `gitnexus_impact` before editing any file with downstream callers.
- MUST warn the user on HIGH or CRITICAL impact before proceeding.
- The pre-tool hook handles this for Edit/Write — don't bypass it.

## Vault git policy

Every mutation to `claude-memory/` is committed with a tag prefix:

- `[bootstrap]` — initial setup
- `[consolidate]` — topic update from Stop hook
- `[reorg]` — reorganization fix
- `[health]` — HEALTH.md update
- `[manual]` — direct human edit
- `[contradiction]` — conflict detected, written to topic's Open questions
- `[replaced]` — explicit overwrite
- `[archive]` — page moved to `_archive/`

## Project-specific conventions (from SPEC.md §9)

- Vault writes go through `src/cortex/vault/writer.py` — also mirrors row to `dbo.notes` in same transaction.
- All SQL via `src/cortex/db/repositories.py` — no raw `pyodbc` elsewhere.
- All Claude calls via `src/cortex/llm.py` with usage tracking.
- Embeddings server-side via `AI_GENERATE_EMBEDDINGS` — never in Python.
- Patterns are the primary artifact for consumer repos.
- Every autonomous change MUST insert a `dbo.autonomous_changes` row with before/after state.
- Every proposal MUST create both a `/Meta/Proposals/pending/` note AND a `dbo.proposed_changes` row.
- The Reviewer NEVER changes schema, domain profiles, or vault structure autonomously — proposal-only.

## When adding things

- New extractor → `add-extractor` skill (when added)
- New feed → `add-feed` skill (when added)
- New domain → `add-domain` skill (also re-scores recent content)
- Investigating a review → `review-the-brain` skill

## Pointers

- Vault index: [`claude-memory/index.md`](C:/Users/Administrator/OneDrive%20-%20Technijian,%20Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/claude-memory/index.md)
- Health: [`claude-memory/HEALTH.md`](C:/Users/Administrator/OneDrive%20-%20Technijian,%20Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/claude-memory/HEALTH.md)
- Workstation setup guide: `workstation.md` at repo root
