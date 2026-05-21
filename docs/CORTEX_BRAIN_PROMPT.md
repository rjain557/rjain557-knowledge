# Cortex knowledge brain — drop-in prompt for other repos

**Copy everything below the `---` line into your repo's `CLAUDE.md`** (or save
as a standalone file and `Read` it at the start of each session, or as
`.claude/skills/cortex-brain/SKILL.md` for slash-command use). It's
self-contained: no other Cortex docs need to be read first.

The prompt assumes you're on the same account as the Cortex production
workstation (`TE-AI-KNOWL`), so the OneDrive vault is already syncing to
your machine. No new credentials are needed — file access is sufficient.

---

## Shared knowledge brain (Cortex)

You have read access to a shared, auto-maintained knowledge brain that
sits in OneDrive alongside this repo:

```
C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/
```

It's maintained by **Cortex** — a separate automation system running on
`TE-AI-KNOWL` that ingests email from `knowledge@technijian.com`,
scrapes trending GitHub repos hourly, runs Deep Research synthesis on
high-relevance sources, and nightly lints the wiki for contradictions
and orphans. Treat it as a peer team's curated knowledge base, not as
your own scratch space.

### What's there (Karpathy "LLM Wiki" pattern)

| Path inside vault | Read | Write |
|---|---|---|
| `claude-memory/index.md` | ✅ **start here** — catalog with 1-line summaries | ❌ auto-rebuilt |
| `claude-memory/topics/*.md` | ✅ durable curated knowledge (architecture, conventions, decisions) | ✅ contribute durable insights |
| `claude-memory/auto-memory/MEMORY.md` + `*.md` | ✅ cross-repo preferences, feedback, references | ✅ contribute cross-repo lessons |
| `claude-memory/CHANGELOG.md` | reference (evolution log) | ✅ append `[manual]`-tagged line when writing |
| `claude-memory/HEALTH.md` | reference (vault stats) | ❌ auto-regenerated |
| `Inbox/*.md` (≈200 files) | ✅ for prior-art research | ❌ Cortex-auto-written |
| `Topics/*.md` (≈103 files) | ✅ **gold** — deep-research articles with 20–35 inline citations each | ❌ Cortex auto-DR-written |
| `Meta/lint-YYYY-MM-DD.md` | reference (contradictions, orphans, stale) | ❌ Cortex writes nightly |
| `_archive/` | ✅ if relevant | ❌ pruning markers |

### Session-start ritual (do this once)

1. Read `claude-memory/index.md` and `claude-memory/auto-memory/MEMORY.md`
   to get oriented.
2. Skim the topic titles in `claude-memory/topics/` and `Topics/` — keep
   their names in working memory so you can recognize relevance later.

### Daily self-improvement loop (the important part)

You are not just a passive consumer — **use the brain to actively improve
THIS repo, and keep doing it as the brain grows.** Run this loop once per
day (your operator may schedule it; if not, run it at the start of the
first session each day):

**First run ever (full sweep):**
1. Read `claude-memory/index.md` + skim every title in `Topics/` and
   `claude-memory/topics/`.
2. For each topic that plausibly relates to what THIS repo does, read it
   in full and ask: *"Does this knowledge suggest a concrete improvement
   to this repo — a pattern to adopt, a library to try, a bug class to
   guard against, a better architecture?"*
3. For each real improvement: implement it directly if low-risk, or write
   a short proposal to `knowledge/improvements/NN-{slug}.md` in THIS repo
   and tell the operator.
4. Record what you reviewed (see "tracking" below).

**Every day after (incremental):**
1. Read `claude-memory/CHANGELOG.md` and note entries dated AFTER your
   last check.
2. List `Topics/` and `claude-memory/topics/` sorted by modified time
   (`ls -t`) and look at anything newer than your last-check timestamp —
   including files with a fresh `## Update (YYYY-MM-DD)` section appended
   (Cortex's synthesizer adds those when new sources refine a topic).
3. For each genuinely-new or newly-updated item relevant to this repo,
   run the same "does this suggest an improvement?" evaluation.
4. If yes → implement (low-risk) or propose (anything bigger). If nothing
   new is relevant, do nothing and just update the timestamp. Most days
   will be a no-op — that's fine and expected.

**Tracking what you've already seen** — keep a tiny state file in THIS
repo so you don't re-review unchanged knowledge:

```
.cortex-brain/last-check.txt        # ISO date of the last review
.cortex-brain/reviewed.log          # append-only: "YYYY-MM-DD reviewed <topic> -> <action>"
```

Recipe to find "what's new since last check":

```bash
VAULT="C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge"
LAST=$(cat .cortex-brain/last-check.txt 2>/dev/null || echo "1970-01-01")

# New CHANGELOG entries since last check (entries are dated ## YYYY-MM-DD blocks)
awk -v d="$LAST" '/^## [0-9]{4}-/{cur=substr($2,1,10)} cur>d' "$VAULT/claude-memory/CHANGELOG.md"

# Topic files modified since last check (covers new topics AND synthesizer ## Update appends)
find "$VAULT/Topics" "$VAULT/claude-memory/topics" -name '*.md' -newermt "$LAST" -print

# After reviewing, stamp the date:
date +%Y-%m-%d > .cortex-brain/last-check.txt
```

The brain updates continuously (hourly mail + GitHub ingestion, nightly
synthesis + lint), so checking daily means this repo keeps benefiting
from everything the wider Technijian knowledge stream learns — without
you re-reading the whole vault every time.

**Improvement discipline:**
- Only act on improvements that are TRACEABLE to a specific brain note —
  cite the `vault: path` in your commit message / proposal.
- Respect lint signals (`⚠️ CONTRADICTION`, `🛑 Verification Notes`) —
  don't act on a flagged-questionable claim without verifying it.
- Prefer small, reversible changes. For anything risky, propose rather
  than implement, and let the operator decide.

### How to query

**Default — grep over markdown** (always works, no setup):

```bash
# Filenames matching a keyword
ls "<vault>/claude-memory/topics/" "<vault>/Topics/" | grep -i <keyword>

# Full-text across all curated + deep-research notes
grep -ril "<phrase>" "<vault>/claude-memory/topics/" "<vault>/Topics/"

# Sort topics by recency
ls -t "<vault>/Topics/" | head -20
```

At the current vault size (~300 notes) grep is fast and high-recall.
You don't need anything else.

**Optional — SQL VECTOR_SEARCH** for true semantic similarity. Only
worth setting up if an agent in your repo is doing pipeline integration
or hitting cases where grep misses paraphrases. Requires being on the
Technijian internal VLAN (10.100.254.0/24), ODBC Driver 18, and
Windows-integrated auth:

```python
import pyodbc
cn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=10.100.254.200;"
    "DATABASE=cortex;Trusted_Connection=yes;Encrypt=yes;"
    "TrustServerCertificate=yes;"
)
rows = cn.execute(
    "EXEC dbo.usp_vector_search_notes @query_text=?, @top_k=?",
    "your natural-language question", 5,
).fetchall()
for r in rows:
    print(f"{r.distance:.3f}  {r.vault_path}  — {r.title}")
```

### How to use what you find

- **Read matching files in full** before citing — the previews are short.
- **Cite by path** in your responses to the user, e.g.
  `vault: Topics/why-agent-harnesses-fail.md`.
- **Respect the lint signals**: any topic file containing a `⚠️
  CONTRADICTION:` block or `## 🛑 Verification Notes (failed)` section
  should be treated with skepticism — verify the specific claim against
  primary sources before depending on it.
- **Don't paraphrase silently** — when reusing a Cortex topic's
  architecture or rationale, link back so the user can navigate.

### How to contribute back

If your work in this repo produces a **generally-useful insight** (a
new pattern, a gotcha, a vendor benchmark, a tenant-wide preference),
don't keep it siloed. Two paths:

**Path A — cross-repo lesson, preference, or reference** → drop a file
into `claude-memory/auto-memory/`:

```markdown
---
name: kebab-case-slug
description: one-line hook
metadata:
  type: feedback | reference | project | user
---

# Title

Why this matters (with the *why* spelled out — past incidents, user
quotes, etc.). How to apply. Related: [[other-memory-slug]].
```

Then add a line to `claude-memory/auto-memory/MEMORY.md`:

```
- [Title](file.md) — one-line hook
```

The memory-prefetch hook auto-loads `MEMORY.md` on every UserPromptSubmit
in **every repo on this account**, so the insight propagates to all
agents immediately.

**Path B — durable architecture, decision, or domain knowledge** → drop
a file into `claude-memory/topics/`:

```markdown
---
topic: Human-readable name
aliases: [synonym1, synonym2]
volatility: stable | evolving | ephemeral
last_updated: YYYY-MM-DD
confidence: high | medium | low
sources: ["docs/...", "https://...", "session:..."]
access_count: 0
last_accessed: YYYY-MM-DD
---

# Title

## Summary
3–5 sentences.

## Key facts
...

## Decisions & rationale
...

## Related topics
- [[other_topic]]
```

Then add a line to `claude-memory/index.md` and a tagged entry to
`claude-memory/CHANGELOG.md`:

```
- `[manual]` Added topic `your-topic` covering X. <one-line why>.
```

### Things NOT to do

- **Don't write to `Inbox/`, `Topics/`, or `_archive/`.** Those are
  Cortex's automated layer — hand edits get overwritten or duplicated
  by the next ingest / lint pass. Use `claude-memory/topics/` for
  hand-shaped content.
- **Don't bypass Cortex's pipeline to seed mail/links.** Forward the
  email to `knowledge@technijian.com` and the hourly poller picks it
  up. Hand-inserting rows into `dbo.processed_emails` confuses the
  daily-cap accounting.
- **Don't mass-delete topic pages** even if they look stale. The lint
  pass flags candidates; an actual archive decision is in
  `claude-memory/_archive/` workflow with a `[archive]` CHANGELOG tag.

### Cortex's automation surface (FYI — not your concern, just context)

| Workflow | Cadence | Effect |
|---|---|---|
| `Cortex - Hourly Mail Poll` | hourly | drains `knowledge@technijian.com` |
| `Cortex - Hourly GitHub Scan` | hourly | discovers top trending repos in 4 categories |
| `Cortex - Daily Repo Review` | 03:00 PT | writes `knowledge/*.md` improvement prompts directly to default branches of allowlisted repos |
| `Cortex - Daily Wiki Lint` | 02:00 PT | flags contradictions, orphans, near-duplicates, stale topics |

All run via n8n at `https://n8n.ai.technijian.com`. If you ever need to
trigger an out-of-band scan or notice the brain hasn't updated, escalate
to the operator (Ravi) — don't try to invoke the pipeline yourself.

---

That's it. Cite the vault as a peer source, contribute back when you
learn something cross-cutting, and stay out of the Cortex-owned
directories. The brain compounds with every repo that uses it this way.
