# Cross-repo access to the Cortex knowledge brain

**Audience:** Claude Code / Codex / any LLM agent working in *another*
Technijian repo (`tech-web-myjian`, `Technijiansa`, etc.) on this account.

You already have read access to Cortex's knowledge brain — it lives
inside the same OneDrive folder this account syncs:

```
C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/
```

This document tells you **what's in there, how to query it, and how to
feed back into it.** Cortex is the wiki maintainer; you are a consumer.

---

## What's in the brain

| Path | What |
|---|---|
| `claude-memory/index.md` | Catalog of every curated topic page with one-line summaries. **Read this first.** |
| `claude-memory/topics/*.md` | Curated, durable knowledge — design decisions, conventions, architectures, references. Hand-shaped. |
| `claude-memory/auto-memory/*.md` | User preferences, feedback, project state, reference URLs. Cross-repo applicable. **Read these once per session** for context. |
| `claude-memory/CHANGELOG.md` | Append-only log of every wiki mutation. |
| `claude-memory/HEALTH.md` | Live dashboard of vault state (size, stale topics, contradictions). |
| `claude-memory/_archive/` | Ephemeral topics that have been retired. Read only if relevant. |
| `Inbox/*.md` | Per-source notes auto-written by Cortex (one per ingested URL — emails, TikTok transcripts, articles). Frontmatter has `source_type`, `domain`, `relevance` scores. |
| `Topics/*.md` | Deep Research articles auto-synthesised by Cortex when a source scores ≥0.5. Each has 18–35 inline citations to authoritative external sources. **These are the gold for "what does Cortex know about X?"** |
| `Meta/lint-YYYY-MM-DD.md` | Daily wiki health report (contradictions, orphans, stale topics). |

---

## How to query

### Quick recipe (file-based, no DB needed)

```bash
# What does the brain know about "agent harnesses"?
ls "claude-memory/topics/" | grep -i harness
ls "Topics/" | grep -i harness

# Full-text search across all curated topics:
grep -ril "agent harness" "claude-memory/topics/" "Topics/"

# What did the brain learn most recently about MCP servers?
ls -t "Topics/" | head -20 | xargs grep -l -i "mcp"
```

### Higher-fidelity recipe (SQL Server access, when available)

Cortex stores embeddings + structured data in `cortex` DB on
`TE-AI-KNOWL` (10.100.254.200, Windows integrated auth). If your repo
runs on the same VLAN:

```python
import pyodbc
cn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=10.100.254.200;"
    "DATABASE=cortex;Trusted_Connection=yes;Encrypt=yes;"
    "TrustServerCertificate=yes;"
)
# Top 5 most-relevant vault notes for an arbitrary query
rows = cn.execute(
    "EXEC dbo.usp_vector_search_notes @query_text=?, @top_k=?",
    "your question here", 5,
).fetchall()
for r in rows:
    print(f"{r.distance:.3f}  {r.vault_path}  — {r.title}")
```

If you're outside the VLAN, fall back to the file-grep recipe above —
it works fine at the current vault size (≈275 notes).

---

## How to use what you find

When you discover a relevant page, **read it in full**. Then use it three
ways:

1. **Cite it in your conversation** with the user — `vault: Topics/foo.md`
2. **Use its claims to decide what to build** — but verify against
   primary sources for non-obvious facts. The Cortex verifier flags
   some claims with ⚠️; respect those.
3. **Don't paraphrase silently** — when borrowing a Cortex topic's
   architecture or rationale, link back to it so the user can navigate.

## How to feed back into the brain

If your work produces a generally-useful insight (a new pattern, a
gotcha, a vendor benchmark), **don't keep it in your repo's docs only.**
Write it back into the Cortex vault so other repos benefit too.

Two paths:

### Path A — auto-memory (cross-repo preferences/references/lessons)

Drop a file into `claude-memory/auto-memory/`:

```markdown
---
name: kebab-case-slug
description: one-line hook
metadata:
  type: feedback | reference | project | user
---

# Title

Why this matters. How to apply. Related: [[other-memory]].
```

Then add a line to `claude-memory/auto-memory/MEMORY.md`:

```
- [Title](file.md) — one-line hook
```

Memory-prefetch hook auto-loads MEMORY.md on every UserPromptSubmit in
every repo on this account, so your insight propagates immediately.

### Path B — durable topic (architecture, deep facts)

Drop a file into `claude-memory/topics/`:

```markdown
---
topic: Human-readable topic name
aliases: [synonym1, synonym2]
volatility: stable | evolving | ephemeral
last_updated: YYYY-MM-DD
confidence: high | medium | low
sources: ["docs/...", "session:...", "https://..."]
access_count: 0
last_accessed: YYYY-MM-DD
---

# Title

## Summary

3-5 sentences.

## Key facts

...

## Decisions & rationale

...

## Related topics

- [[other_topic]]
```

Add a line to `claude-memory/index.md`. Add a CHANGELOG entry with
`[manual]` tag prefix.

---

## Things NOT to do

- **Don't write to `Inbox/` or `Topics/`** — those are Cortex's automated
  layer. Hand-edits there will be overwritten or duplicated. Use
  `claude-memory/topics/` for hand-shaped content.
- **Don't delete `_archive/` contents** — those are intentional
  pruning markers.
- **Don't bypass `dbo.relevance_scores`** when ingesting through
  Cortex's pipeline — let it score so the auto-DR cap stays meaningful.

---

## Cortex's automation layer (FYI, not yours to touch)

Cortex runs on `TE-AI-KNOWL` and currently has 4 n8n workflows running
against it:

| Workflow | Cadence | Effect |
|---|---|---|
| `Cortex - Hourly Mail Poll` | hourly | drains `knowledge@technijian.com` |
| `Cortex - Hourly GitHub Scan` | hourly | discovers top trending repos across 4 categories |
| `Cortex - Daily Repo Review` | daily 03:00 PT | writes `knowledge/*.md` improvement prompts directly to default branches of allowlisted repos |
| `Cortex - Daily Wiki Lint` | daily 02:00 PT | health-checks the wiki for contradictions, orphans, stale topics |

If you ever notice a stale topic page that the lint hasn't yet caught,
you can manually trigger the lint via the operator (Ravi) or by
flagging it in this session.

---

## Quick copy-paste prompt for your repo's CLAUDE.md

To make the brain a first-class context source in this repo, add this
block to your `CLAUDE.md`:

```markdown
## Cortex knowledge brain

Read access to the shared Cortex knowledge brain at
`C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/`.

Before starting non-trivial work in this repo:
1. Read `claude-memory/index.md` to see what topics exist.
2. Grep `claude-memory/topics/` and `Topics/` for terms relevant to the task.
3. Read the matching files in full.
4. Cite them in your responses to the user.

Full conventions: see
`<vault>/Topics/CROSS_REPO_BRAIN_ACCESS.md` (or the same file in
the rjain557-knowledge source repo `docs/`).

Don't write to `Inbox/`, `Topics/`, or `_archive/` — those are auto-
maintained by Cortex. To contribute insights back, add files to
`claude-memory/topics/` (durable) or `claude-memory/auto-memory/`
(cross-repo preferences/feedback/references) and update the index.
```
