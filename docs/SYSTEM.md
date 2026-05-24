# Cortex — As-Built System Specification

> **Status:** living document, reflects what is actually deployed and running.
> `docs/SPEC.md` is the original v4 *design* spec (pre-implementation) and is
> retained for intent/rationale; where the two disagree, **this document wins.**
> Last updated: 2026-05-24.

Cortex ("Inbox Brain") is a self-improving knowledge system running on the
`TE-DC-JIAN` workstation (Windows Server 2025, SQL Server 2025 Enterprise on
`localhost`). It ingests Microsoft 365 mail + web/RSS/arXiv/GitHub/HN feeds,
scores and synthesizes the content into an Obsidian vault and SQL Server, runs
autonomous deep research, reviews public + private repos, and exposes the
accumulated knowledge to consumer Claude Code repos.

---

## 1. Architecture at a glance

```
            ┌───────────────────────── Sources ─────────────────────────┐
            │ M365 mail (knowledge@)   RSS/arXiv/GitHub-trending/HN feeds │
            └───────────────┬───────────────────────────┬───────────────┘
                            │                           │
                  mail/watcher.py              feeds/scan_runner.py
                            │                           │
                            ▼                           ▼
              ┌──────────────────────── Extractors ────────────────────────┐
              │ article pdf arxiv youtube tiktok twitter reddit hackernews  │
              │ github  (+ _media.py faster-whisper transcription)          │
              └───────────────────────────┬─────────────────────────────────┘
                                          ▼
                         relevance/scorer.py  (Gemini Flash-Lite)
                                          ▼
                vault/writer.py  ── writes Obsidian note + dbo.notes row
                                          │   (single transaction)
                          ┌───────────────┼────────────────┐
                          ▼               ▼                ▼
              deep_research/        synthesizer/       lint/wiki_lint.py
              (Claude+web_search)   cross_page.py      (health checks)
                                          │
                                          ▼
                            SQL Server 2025 (VECTOR + JSON)
                                 + Obsidian vault (OneDrive)
                                          │
                                          ▼
                 Consumer repos via CORTEX_BRAIN_PROMPT.md / MCP
```

All long-running execution is fronted by a **FastAPI webhook server**
(`scripts/webhook_server.py`, port 8765) that **n8n** triggers on schedule. A
Windows scheduled task (`Cortex - Webhook Server`) keeps the server up across
reboots.

---

## 2. Ingestion pipeline

### 2.1 Mail
- `mail/watcher.py` — polls the `knowledge@technijian.com` shared mailbox via
  Microsoft Graph (MSAL **certificate** auth, app `Technijian-Agent-Harness`).
  Reads the `Inbox`, processes each message, then **moves it to `Processed`**.
- `mail/link_extractor.py` — pulls URLs from message bodies and **strips brand
  pollution** (INKY security banners, technijian signature URLs) before they
  become sources. (See feedback memory `filter-brand-pollution`.)
- `mail/notify.py` — sends failure alerts to `rjain@technijian.com` via Graph.

### 2.2 Feeds
- `feeds/github_trending.py` + `feeds/scan_runner.py` — hourly GitHub-trending
  scan across four AI categories (development, SEO, tech-support, office-ops);
  top-5 by stars, deduped against `dbo.processed_feed_items`, new repos added.
- Feeds defined in `config/tracked-feeds.yaml`.

### 2.3 Extractors (`src/cortex/extractors/`)
`base.py` defines the contract; one module per source type: `article` (trafilatura
→ playwright fallback), `pdf`, `arxiv` (full-PDF + reproducibility score),
`youtube`, `tiktok`, `twitter`, `reddit`, `hackernews`, `github`. `_media.py`
does local CPU transcription with **faster-whisper** (`base.en`, int8).

### 2.4 Relevance scoring
`relevance/scorer.py` classifies each item 0–1 against the three domains in
`config/target-domains.yaml`. Routed LLM task `relevance_scoring`
(**Gemini 2.5 Flash-Lite**). Scores persisted to `dbo.relevance_scores`.

---

## 3. Agents & LLM task routing

All LLM calls go through **`src/cortex/llm.py`**. Two entry points:
- `complete(...)` — direct Anthropic call (used by web_search loops).
- `complete_task(task, ...)` — routes a **logical task** through
  `config/models.yaml` to the configured provider, with automatic **fallback**
  to a known-good model on provider error.

Providers are either **Anthropic-native** (required for the server-side
`web_search` tool) or **OpenAI-compatible** (one `httpx` POST path covers
Gemini, DeepSeek, OpenAI). Token usage + USD cost are tracked per process.

### 3.1 Model routing (config/models.yaml)

| Task | Model | Why |
|---|---|---|
| `relevance_scoring` | **Gemini 2.5 Flash-Lite** | High-volume 0–1 classification; non-reasoning, clean JSON, cheapest reliable. |
| `dr_verifier` | **Gemini 2.5 Flash-Lite** | Fact-check DR articles; lowest hallucination / most source-faithful. |
| `cross_page_synth` | **Gemini 2.5 Flash-Lite** | Short relation classification. |
| `lint_contradiction` | **Gemini 2.5 Flash-Lite** | Semantic NLI between two notes. |
| `repo_review` | **Claude Sonnet 4.6** | Code understanding + fuzzy improvement judgment. |
| `topic_refresh` | **Claude Sonnet 4.6** | Needs Anthropic `web_search`. |
| `deep_research_auto` | **Claude Sonnet 4.6** | Needs `web_search`; ~4× cheaper than Opus. |
| `deep_research_manual` | **Claude Opus 4.7** | User-initiated, highest quality. |

Every cheap task **falls back to Claude Haiku 4.5** so an unattended cycle
survives a provider outage. Model routing is a **manual_only** category: the
weekly refresh job proposes changes but never auto-applies them.

**Provider notes (verified 2026-05-24):** Gemini OK (no VPN); Anthropic OK;
DeepSeek funded+OK but its V4 models are *reasoning* models (poor fit for short
classification — they truncate JSON under tight token budgets); GLM/Zhipu is
US-IP-blocked and excluded.

### 3.2 Deep research (`deep_research/`)
`orchestrator.py` runs Claude with the `web_search_20250305` tool in an
agent loop (handles `pause_turn`), producing a cited topic article.
`verifier.py` fact-checks the article. `auto.py` auto-triggers research after
ingestion for sufficiently-relevant sources (min score 0.3, ≤25/day).

### 3.3 Synthesizer & lint
`synthesizer/cross_page.py` — Karpathy "LLM-wiki" cross-page synthesis: finds
similar topics via VECTOR_SEARCH and appends `## Update` sections.
`lint/wiki_lint.py` — orphans, near-duplicates, contradiction checks, stale
topics → writes `Meta/lint-YYYY-MM-DD.md`.

### 3.4 Repo review (`repo_review/`)
`lister.py` (GitHub metadata/README/commits/tree) → `vault_search.py`
(`usp_vector_search_notes`) → `analyzer.py` (Sonnet, structured improvement
prompts) → `prompt_writer.py` (`knowledge/*.md`) → `pr_writer.py` (commits to
the repo). Allowlist: `config/reviewed-repos.yaml` (incl. Cortex itself —
dogfooding).

---

## 4. Harnesses (how code runs)

| Harness | What | Where |
|---|---|---|
| **Webhook server** | FastAPI on :8765; endpoints `/health`, `/poll`, `/github-scan`, `/repo-review`, `/lint`, `/refresh-topics`, `/model-refresh`. `X-Webhook-Secret` auth. | `scripts/webhook_server.py` |
| **n8n** | Schedule triggers POST the webhook endpoints; emails on failure. Server at `n8n.ai.technijian.com` (`10.100.254.225`). | `scripts/setup_n8n_workflow.py` |
| **Windows scheduled task** | `Cortex - Webhook Server` (S4U, AtStartup) keeps the server alive. | Task Scheduler |
| **CLI scripts** | One-shot/manual runs (see §6). | `scripts/*.py` |

---

## 5. Skills & hooks (`.claude/`)

**Slash-command skills (`.claude/commands/`):** `review`, `consolidate`,
`contradictions`, `graduate`, `impact`, `sync`, `vault-status`, `volatility`.

**Hooks (`.claude/hooks/`, PowerShell):** `retrieve.ps1` (vault retrieval on
prompt), `consolidate.ps1` (topic updates on Stop), `health-check.ps1`
(regenerate HEALTH.md on SessionEnd), `impact-check.ps1` (GitNexus impact on
Edit/Write), `preference-extract.ps1`, `reindex.ps1`, plus `_lib.ps1`.

---

## 6. Workflows & cadences

| Workflow (n8n) | Endpoint | Cadence |
|---|---|---|
| Cortex - Hourly Mail Poll | `/poll` | every 1h |
| Cortex - Hourly GitHub Scan | `/github-scan` | every 1h |
| Cortex - Daily Wiki Lint | `/lint` | daily 02:00 PT |
| Cortex - Daily Repo Review | `/repo-review` | daily 03:00 PT |
| Cortex - Weekly Topic Refresh | `/refresh-topics` | Mon 04:00 PT |
| Cortex - Weekly Model Refresh | `/model-refresh` | Mon 05:00 PT |

**Model-refresh** (`model_refresh/runner.py`): (1) pings every routed model for
liveness; (2) uses Claude + web_search to find newer/cheaper models per task;
writes a proposal to `Meta/Proposals/pending/` + a `dbo.proposed_changes` row.
Never auto-applies.

**CLI equivalents:** `poll.py`, `scan_github.py`, `lint_wiki.py`,
`review_repos.py`, `refresh_topics.py`, `model_refresh.py`, `deep_research.py`,
`expand_topics.py`, `ingest_once.py`, `reextract.py`, `cleanup_signatures.py`.

All human-facing timestamps are **America/Los_Angeles** (`utils/timezone.py`).

---

## 7. Memory (4-layer stack)

1. **Obsidian vault** (durable human knowledge) — OneDrive-synced git repo at
   `…/obsidian/rjain557-knowledge/…/claude-memory/`. Topic pages, CHANGELOG,
   HEALTH.md, retrieval log. Volatility tiers (stable/evolving/ephemeral) drive
   review cadence and consolidation/contradiction handling.
2. **Auto-memory** (Claude working notes) — `claude-memory/auto-memory/` inside
   the vault, surfaced to the harness via a **directory junction** at
   `~/.claude/projects/…/memory/`. Indexed by `MEMORY.md`. Shared across repos.
3. **GitNexus** (code structure) — impact analysis on Edit/Write.
4. **Auto Dream** (consolidation) — disabled by default.

Vault writes go through `vault/writer.py`, which **mirrors the row to
`dbo.notes` in the same transaction**. OneDrive handles vault propagation — the
pipeline does **not** auto-commit Inbox/Topics notes.

---

## 8. Database (SQL Server 2025, db `cortex`)

- **Connection:** `db/connection.py` — thread-local pyodbc, ODBC Driver 18,
  Windows-integrated auth. NVARCHAR (`SQL_WCHAR`) decoded **utf-16le** (UTF-8
  corrupts em-dashes — do not regress).
- **Access layer:** `db/repositories.py` (no raw pyodbc elsewhere).
- **Migrations (8):** `0001_initial` … `0007_deep_research` (+`0003b` activate
  external model), tracked in `dbo.schema_migrations`.
- **Tables (18):** `notes`, `sources`, `authors`, `processed_emails`,
  `processed_links`, `processed_feed_items`, `feed_sources`, `relevance_scores`,
  `patterns`, `deep_research_runs`, `synthesis_runs`, `system_reviews`,
  `proposed_changes`, `autonomous_changes`, `benchmark_snapshots`,
  `tracked_libraries`, `gsd_runs`, `schema_migrations`.
- **Stored procs (7):** `usp_upsert_note`, `usp_search_brain`,
  `usp_score_authors`, `usp_decay_patterns`, `usp_embed_note`,
  `usp_embed_pending_notes`, `usp_vector_search_notes`.
- **Vectors:** `notes.embedding` + `patterns.embedding` are `VECTOR(1536)`.
  Embeddings are generated **server-side** via OpenAI `text-embedding-3-small`
  through `AI_GENERATE_EMBEDDINGS` (DATABASE SCOPED CREDENTIAL named after the
  endpoint URL). `AI_GENERATE_EMBEDDINGS` **cannot** be inlined inside
  `VECTOR_DISTANCE` — always `DECLARE @v VECTOR(1536)` first.
- **Vector index:** DiskANN not created (preview needs single-INT clustered PK;
  we use BIGINT IDENTITY). `VECTOR_SEARCH` scans — fine at current scale.

---

## 9. Configuration (`config/`)

| File | Purpose |
|---|---|
| `settings.yaml` | Mail/extraction/synthesizer/reviewer/deep-research/database knobs. |
| `target-domains.yaml` | The three AI domains + relevance thresholds. |
| `tracked-feeds.yaml` | RSS/arXiv/GitHub-trending/HN feed sources. |
| `reviewed-repos.yaml` | Private-repo allowlist for daily repo review. |
| `refresh-topics.yaml` | Curated evergreen themes for weekly refresh. |
| `models.yaml` | **Central LLM task→model routing**, pricing snapshot, provider registry, 7-day-refresh policy. |

Non-secret runtime config is in `.env`.

---

## 10. Secrets

**No API keys live in this repo.** `.env` is gitignored (never committed) and
holds only non-secret config. All credentials are loaded at runtime from the
**OneDrive key vault** (`…/VSCODE/keys/*.md`) by
`config.py:_load_vault_secrets()` — anthropic, openai, gemini, deepseek,
github, and the M365 cert PFX password. An explicit env var overrides the vault
(for CI). The M365 PFX itself is also vault-resident.

---

## 11. Consumer-repo access

- `docs/CORTEX_BRAIN_PROMPT.md` — drop-in prompt giving any Claude Code repo a
  daily self-improvement loop against the vault (grep recipes + optional SQL),
  tracked via `.cortex-brain/last-check.txt`. Consumer repos need **OneDrive
  access, not SQL**.
- `docs/CROSS_REPO_BRAIN_ACCESS.md` — cross-repo access details.

---

## 12. Repo structure

```
src/cortex/        config.py, llm.py, and packages:
  db/ mail/ feeds/ extractors/ relevance/ vault/
  deep_research/ synthesizer/ lint/ topic_refresh/
  repo_review/ model_refresh/ utils/
scripts/           CLI entrypoints + webhook_server.py + n8n setup
sql/               init/ migrations/ procs/
config/            *.yaml (see §9)
docs/              SPEC.md (design), SYSTEM.md (this), CORTEX_BRAIN_PROMPT.md,
                   CROSS_REPO_BRAIN_ACCESS.md
.claude/           commands/ (skills), hooks/, mcp.json, settings
```
