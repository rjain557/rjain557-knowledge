# Inbox Brain — System Specification (v4, SQL Server 2025)

> Working codename: **Cortex**. Rename freely.

A Claude Code project that builds and continuously self-improves a knowledge brain across three AI domains:

1. **`agent-orchestration`** — autonomous agents, harnesses, multi-agent orchestration patterns
2. **`seo-agents`** — AI agents that perform SEO work (especially AEO/GEO)
3. **`tech-support-agents`** — AI agents that diagnose and resolve IT support issues

It ingests from a curated M365 mailbox and a set of direct feeds (arXiv, vendor blogs, GitHub trending, benchmark leaderboards, threat-intel feeds), synthesizes the material into structured notes in an Obsidian vault, mirrors everything into SQL Server 2025 with embeddings, distills reusable **patterns**, exposes the brain to consumer Claude Code repos via MCP, and **reviews itself every 7 days** — auditing what it's collecting, tuning thresholds and feeds, decaying stale patterns, and proposing structural changes for human approval.

Every ingestion follows a Research → Plan → Execute → Verify (GSD) loop. The 7-day self-review follows the same loop applied to the brain itself.

**v4 changes vs v3:**
- New **Reviewer** component (§3.12) runs every 7 days
- New **autonomous changes** + **proposed changes** tables; the brain can self-tune within safe bounds and queue larger changes for human approval
- New **`/Meta/`** vault folder for reviews, proposals, and health snapshots
- **Pattern confidence decay** built in
- New MCP tools: `get_pending_proposals`, `decide_proposal`, `get_last_review`
- Phase 6 (self-review) added before hardening, now Phase 7

---

## 1. Goals & Non-Goals

### Goals
- Keep three domain-specific knowledge bodies current with minimal human effort.
- Treat email as one ingestion path, not the only one.
- Produce **patterns** consumer agents can use at inference time.
- **Continuously self-improve**: every 7 days the brain audits its own ingestion quality, calibration, coverage, costs, and pattern health, then applies safe adjustments autonomously and queues larger changes for human review.
- Verifiable writes: nothing lands in the vault without a verifier pass.
- Single backing store: SQL Server 2025 for state, JSON metadata, embeddings, vector search.
- Consumable: other Claude Code repos query via MCP only.

### Non-Goals (v1)
- Web crawling beyond curated feeds
- Real-time email push (polling fine for v1)
- A UI — Obsidian is the UI
- Multi-user / multi-mailbox
- Fully autonomous schema or domain changes — those always go through the proposals queue

---

## 2. High-Level Architecture

```
┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌─────────────┐
│ M365 Mailbox │  │ ArXiv API    │  │ Vendor RSS     │  │ Benchmark   │
│              │  │              │  │ Blogs          │  │ Leaderboards│
└──────┬───────┘  └──────┬───────┘  └────────┬───────┘  └─────┬───────┘
       │                 │                   │                │
       ▼                 ▼                   ▼                ▼
┌──────────────┐  ┌─────────────────────────────────────────────────┐
│Email Watcher │  │              Feed Watchers                       │
└──────┬───────┘  │  (arxiv, rss, github_trending, benchmark)        │
       │          └────────────────────────┬─────────────────────────┘
       │                                   │
       ▼                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│              Link Extractor + Classifier                          │
└───┬───────┬───────┬───────┬───────┬───────────────────────┬──────┘
    ▼       ▼       ▼       ▼       ▼                       ▼
┌────────┬───────┬───────┬───────┬──────────┐    ┌──────────────────┐
│Article │YouTube│TikTok │GitHub │ ArXiv    │    │  SQL Server 2025 │
│        │       │       │ Repo  │ Paper    │... │                  │
└───┬────┴───┬───┴───┬───┴───┬───┴────┬─────┘    │ - state tables   │
    └────────┴───────┴───────┴────────┘          │ - JSON metadata  │
                       │                         │ - VECTOR embedds │
                       ▼                         │ - DiskANN index  │
        ┌────────────────────────┐               │ - AI_GENERATE_   │
        │ Relevance Filter       │◀──────────────│   EMBEDDINGS     │
        │ (score vs 3 domains)   │ target-       │ - VECTOR_SEARCH  │
        └────────────┬───────────┘ domains.yaml  │ - patterns       │
                     │                           │ - benchmarks     │
                     ▼                           │ - reviews        │
        ┌────────────────────────┐               │ - proposals      │
        │  GSD Pipeline          │               └────────┬─────────┘
        │  Researcher → Plan →   │                        ▲
        │  Execute → Verify      │────────────────────────┘
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────────────────┐      ┌────────────────────────┐
        │  Obsidian Vault        │◀────▶│  Synthesizer           │
        │  /Inbox /Sources       │      │  (cross-source rollups │
        │  /Topics /Authors      │      │   → /Patterns)         │
        │  /Libraries /Frameworks│      └────────────────────────┘
        │  /Benchmarks /Patterns │
        │  /Lessons /Meta        │      ┌────────────────────────┐
        └────────────┬───────────┘◀────▶│  Reviewer (7-day)      │
                     │                  │  - audits everything   │
                     │ MCP              │  - autonomous tuning   │
                     ▼                  │  - human proposals     │
        ┌────────────────────────┐      └────────────────────────┘
        │ Consumer Claude Code   │
        │ repos                  │
        └────────────────────────┘
```

The Obsidian vault is the human-facing canonical store. SQL Server is the machine-facing access layer. The Reviewer is the meta-cognition layer that watches both and keeps the system from drifting.

---

## 3. Components

### 3.1 Email Watcher (`src/cortex/mail/`)
Microsoft Graph polling for a target folder. Captures sender/subject/body/date/message-id, passes to link extractor, dedups via `dbo.processed_emails`.

### 3.2 Feed Watchers (`src/cortex/feeds/`)

Configured in `config/tracked-feeds.yaml`, persisted in `dbo.feed_sources`.

| Feed type | Notes |
|---|---|
| `arxiv` | arXiv API by category + keyword filter; dedup by arXiv ID; abstract pre-scoring before PDF extraction |
| `rss` | Generic RSS/Atom (vendor blogs, threat-intel like CISA KEV / MSRC, SEO news) |
| `github_trending` | Scrape trending pages by topic/language; new repos auto-added to `dbo.tracked_libraries` |
| `benchmark_leaderboard` | Per-benchmark scraper; snapshots in `dbo.benchmark_snapshots`; diffs trigger `/Benchmarks/` notes |

Feed items dedup via `dbo.processed_feed_items` by stable item ID. New items go through the same extractor → relevance → GSD pipeline as email links.

### 3.3 Link Extractor & Classifier (`src/cortex/mail/link_extractor.py`)
Parses HTML, filters trackers/unsubscribe/signature URLs, classifies by URL pattern (`arxiv.org/abs/` → arXiv, `youtube.com|youtu.be` → YouTube, `github.com/{o}/{r}` → repo, `.pdf` → PDF, else article), dedups via `dbo.processed_links`.

### 3.4 Content Extractors (`src/cortex/extractors/`)

All return a normalized `ExtractedContent` persisted to `dbo.sources` with metadata in a `JSON` column:

```python
{
  "source_url": str,
  "source_type": "article" | "youtube" | "tiktok" | "repo" | "pdf" | "arxiv",
  "canonical_url": str,
  "title": str,
  "author": str | None,
  "published_at": datetime | None,
  "body_markdown": str,
  "transcript": str | None,
  "metadata": dict,
  "raw_blob_path": str | None,
  "code_artifacts": list | None
}
```

| Extractor | Primary | Fallback | Notes |
|---|---|---|---|
| Article | trafilatura | playwright | Strip nav/ads; preserve code blocks |
| YouTube | youtube-transcript-api | yt-dlp → whisper | Chapters, description, channel |
| TikTok | yt-dlp + cookies | whisper on audio | Expect breakage; log + skip |
| GitHub repo | GitHub REST | gh CLI | README + releases + commits + topics + code artifacts |
| PDF | pdftotext | tesseract OCR | Use `pdf-reading` skill |
| ArXiv | arXiv API + PDF | n/a | Abstract/methods/results split; reproducibility score |

**Code-aware extraction.** For agent-related repos, additionally pull `prompts/**`, `agents/**.py`, `**/system_prompt*.md`, `**/tools.py`, `**/*tool_schema*.json`, example notebooks, configs — tagged `type: code_artifact` for the Patterns layer.

### 3.5 Relevance Filter (`src/cortex/relevance/`)
Scores each piece against each of the three domains. Writes to `dbo.relevance_scores`. Items below threshold for every domain → `/Inbox` only. Above-threshold lessons → `/Lessons/{domain}/{slug}.md`. Candidate pattern stubs → queued for the Synthesizer.

### 3.6 GSD Pipeline (`src/cortex/gsd/`, subagent prompts in `agents/`)

Researcher → Planner → Executor → Verifier subagents, artifacts persist in `dbo.gsd_runs`. Verifier uses `VECTOR_SEARCH` for near-dupe detection.

### 3.7 MCP Vault Server (`src/cortex/mcp_server/`)

FastMCP server. All search via `VECTOR_SEARCH` + JSON predicates. Tools:

```
search_brain(query, limit=10, domains=None, types=None)
get_lessons_for(domain)
get_patterns(domain, query=None, pattern_type=None, limit=5)
find_related(note_path, limit=5)
get_framework_status(name)
get_benchmark_trends(benchmark_name, days=90)
get_library_status(repo)
get_author_profile(name)
list_recent(days=7, domains=None, types=None)
get_source(url)

# Meta tools (v4):
get_last_review()
get_pending_proposals(category=None)
decide_proposal(proposal_id, decision, notes=None)   # approve | reject | defer
get_system_health(days=30)
```

### 3.8 Schedulers (`src/cortex/schedulers/`)

| Job | Cadence | What |
|---|---|---|
| Library update check | daily | Items with `last_checked` ≥ `check_interval_days` ago |
| Author crawl | weekly | Authors with `quality_score ≥ threshold` |
| Feed poller | every 15 min | Feeds with `last_polled` older than `poll_interval_hours` |
| Benchmark snapshotter | weekly | All `benchmark_leaderboard` feeds |
| Synthesizer | daily check | Threshold-triggered + weekly scheduled per domain |
| **Reviewer** | **every 7 days** | **§3.12** |
| Pattern decay | daily | Decay confidence on patterns with no new corroboration |

### 3.9 Vault Watcher (`src/cortex/vault/watcher.py`)
`watchdog` process keeping SQL in sync with hand edits to vault markdown.

### 3.10 Synthesizer (`src/cortex/synthesizer/`)

Periodic cross-source GSD runs that produce **patterns**. Triggers: threshold (N new sources for `domain × pattern_type`), scheduled (weekly per domain), manual. Requires ≥3 corroborating sources before promoting to a pattern. Writes `/Patterns/{Domain}/{name}.md` and `dbo.patterns` rows.

### 3.11 Per-domain ingestion specifics

**agent-orchestration**: arXiv keyword filters, reproducibility scoring, watched authors (Anthropic, Simon Willison, Hamel Husain, Eugene Yan, Andrew Ng's The Batch), GitHub trending watch on `llm-agent`/`ai-agents`/`autonomous-agents`, benchmarks: SWE-bench, GAIA, OSWorld, AgentBench, WebArena.

**seo-agents**: Focus on AEO/GEO, SEO-tool AI features (Surfer, Clearscope, Frase, Ahrefs, Semrush), LLM citation pattern research, SERP-format research.

**tech-support-agents**: Direct CISA KEV / MSRC ingestion, AI-for-ITops tooling (Copilot for Security, M365 Copilot, AIOps), diagnostic patterns as primary artifact.

### 3.12 Reviewer (`src/cortex/reviewer/`) — 7-day self-review

A Claude Code subagent pipeline (mirroring GSD) that runs every 7 days and audits the entire system. Configurable cadence via `settings.yaml`; manual trigger via `python scripts/review.py`.

**Phases of a review run:**

**Research** — gather metrics across categories:

| Category | Metrics gathered |
|---|---|
| Ingestion volume | per source_type and per feed: items/day, week-over-week delta |
| Ingestion quality | mean/median relevance score per feed × domain; % of items below threshold for every domain (noise rate) |
| Extractor health | failure rates per extractor type; common failure modes |
| Relevance calibration | score distribution per domain; correlation between score and downstream pattern contribution |
| Pattern health | count per domain × type; confidence distribution; staleness (days since last corroboration); MCP retrieval hits per pattern |
| Author quality | EWMA-derived scores; new authors auto-discovered from high-relevance content |
| Library/framework health | tracked repos with no activity in 90 days; new candidates from GitHub trending |
| Vault hygiene | orphan notes (no inbound links), unfilled stub notes, near-duplicate clusters via `VECTOR_SEARCH` |
| Coverage gaps | for each domain, what topics keep appearing in low-quality sources but lack good coverage (Claude reasons about this) |
| Costs | Claude tokens, embedding tokens, Whisper minutes, total $ by category, week-over-week |
| System failures | failed GSD runs, verifier rejection rate, retry rate per phase |

**Plan** — categorize findings into three buckets:

1. **Autonomous adjustments** (safe, reversible, narrowly bounded):
   - Adjust per-domain relevance threshold within ±0.1 of current
   - Decay pattern confidence per the decay formula
   - Update author `quality_score` (already automatic via `usp_score_authors`; review validates the EWMA)
   - Mark low-yield feeds as `under_review` (still active, but flagged)
   - Garbage-collect `/Inbox` items past `inbox_retention_days`
   - Re-embed patterns whose body changed materially since last embedding
   - Increase/decrease `max_per_poll` for arXiv within bounds
   - Promote a tracked author when `hit_count` and `quality_score` both pass thresholds

2. **Human-approval proposals** (written to `/Meta/Proposals/pending/` and `dbo.proposed_changes`):
   - Deactivate or remove a feed
   - Add a new feed, author, or tracked library suggested by gap analysis
   - Change a domain's interests / anti-patterns
   - Change relevance threshold by more than ±0.1
   - Restructure vault folders
   - Schema migration suggestions
   - Significant cost-cutting actions (downgrading Whisper model, switching embedding model)

3. **Informational findings** — included in the report, no action.

**Execute** —
- Apply each autonomous adjustment; record before/after state in `dbo.autonomous_changes`
- Write each proposal as a structured markdown note in `/Meta/Proposals/pending/{date}-{slug}.md` AND a row in `dbo.proposed_changes`
- Write the full review report to `/Meta/Reviews/{YYYY-MM-DD}.md` and `dbo.system_reviews`
- Update `dbo.system_reviews(finished_at, autonomous_changes_applied, proposals_created)`

**Verify** —
- Sanity-check every autonomous change is reversible and has an audit row
- Cross-check proposals for conflicts (no two proposals advocating opposite changes)
- Check the report cites real metric values from the gathered data (no fabricated numbers)
- If verification fails: roll back autonomous changes and flag the review as `failed` for human attention

**Proposal approval workflow:**

The human reviews `/Meta/Proposals/pending/{slug}.md` files in Obsidian. To approve, they edit the frontmatter:

```yaml
status: approved          # was: pending
decided_at: 2026-05-20
notes: "Yes, drop this feed"
```

A daily `scripts/apply_proposals.py` job picks up files with `status: approved`, applies the structured action (which is encoded in the note's frontmatter as YAML), records the result in `dbo.proposed_changes`, and moves the file to `/Meta/Proposals/approved/`. Rejections move to `/Meta/Proposals/rejected/`.

Alternatively, via MCP: `decide_proposal(proposal_id, "approve", "Yes, drop this feed")` from any consumer repo (or another Claude Code session).

**Pattern confidence decay** is a separate small job (not part of the review itself) that runs daily:

```sql
UPDATE dbo.patterns
SET confidence = confidence * @decay_rate,
    updated_at = SYSUTCDATETIME()
WHERE updated_at < DATEADD(month, -3, GETUTCDATE())
  AND confidence > 0.1;
```

The review reports on patterns with `confidence < 0.3` and recommends archival as a proposal.

---

## 4. Data Model

### 4.1 Obsidian Vault Layout

```
Vault/
├── Inbox/                          # raw extracts; _review/ for verifier failures
├── Sources/                        # one note per ingested source
│   ├── Articles/  Videos/  Repos/  Papers/  Posts/  PDFs/
├── Topics/                         # synthesized topic notes
├── Authors/                        # author profile + content index
├── Libraries/                      # tracked repos
├── Frameworks/                     # tracked agent frameworks (richer notes)
│   └── {name}/{_index.md, prompts/, tools/}
├── Benchmarks/                     # leaderboard trend notes
├── Patterns/                       # distilled reusable patterns
│   ├── AgentOrchestration/  SEO/  Diagnostics/
├── Lessons/                        # per-domain actionable extracts
│   ├── agent-orchestration/  seo-agents/  tech-support-agents/
├── Meta/                           # ★ self-review artifacts
│   ├── Reviews/                    # /Meta/Reviews/{YYYY-MM-DD}.md
│   ├── Proposals/
│   │   ├── pending/
│   │   ├── approved/
│   │   └── rejected/
│   └── Health/                     # /Meta/Health/{YYYY-MM-DD}-metrics.md
└── _meta/                          # vault config, not the review meta
```

### 4.2 Frontmatter Schema

```yaml
type: source | topic | author | library | framework | benchmark | pattern | lesson | review | proposal | health
source_type: article | youtube | tiktok | repo | pdf | arxiv | code_artifact
source_url: ...
title: "..."
author: "..."
captured_at: 2026-05-13T08:14:00Z
domain: agent-orchestration | seo-agents | tech-support-agents
relevance: { agent-orchestration: 0.82, seo-agents: 0.05, tech-support-agents: 0.0 }
tags: [...]
status: raw | curated | archived

# Pattern-only:
pattern_type: orchestration | planning | memory | tool-use | reflection | ...
confidence: 0.0-1.0
source_ids: [123, 456, 789]

# Proposal-only:
proposal_id: 42
category: feed_change | domain_profile | threshold | tracking_addition | schema | other
proposed_action: { type: "...", payload: { ... } }
status: pending | approved | rejected | applied
decided_at: 2026-05-20
notes: "..."
```

### 4.3 SQL Server 2025 Schema (additions for v4)

Includes everything from v3 plus the meta tables below. The `0006_review_and_proposals.sql` migration adds:

```sql
-- ============================================================
-- Self-review and self-improvement
-- ============================================================

CREATE TABLE dbo.system_reviews (
    review_id                  BIGINT IDENTITY PRIMARY KEY,
    started_at                 DATETIME2     NOT NULL,
    finished_at                DATETIME2     NULL,
    period_days                INT           NOT NULL DEFAULT 7,
    triggered_by               NVARCHAR(50)  NOT NULL DEFAULT 'scheduled', -- scheduled | manual
    metrics_snapshot           JSON          NOT NULL,
    findings                   JSON          NULL,
    autonomous_changes_applied INT           NOT NULL DEFAULT 0,
    proposals_created          INT           NOT NULL DEFAULT 0,
    status                     NVARCHAR(50)  NOT NULL DEFAULT 'running', -- running | passed | failed
    report_path                NVARCHAR(1000)NULL
);
CREATE INDEX IX_reviews_started ON dbo.system_reviews(started_at DESC);

CREATE TABLE dbo.proposed_changes (
    proposal_id     BIGINT IDENTITY PRIMARY KEY,
    review_id       BIGINT        NULL REFERENCES dbo.system_reviews(review_id),
    proposed_at     DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    category        NVARCHAR(100) NOT NULL,
        -- feed_change | domain_profile | threshold | tracking_addition | schema | cost | other
    title           NVARCHAR(500) NOT NULL,
    description     NVARCHAR(MAX) NOT NULL,
    rationale       NVARCHAR(MAX) NULL,
    impact          NVARCHAR(MAX) NULL,
    proposed_action JSON          NOT NULL,                -- structured action payload
    vault_path      NVARCHAR(1000)NULL,                    -- /Meta/Proposals/pending/{slug}.md
    status          NVARCHAR(50)  NOT NULL DEFAULT 'pending',
        -- pending | approved | rejected | applied | superseded
    decided_at      DATETIME2     NULL,
    decided_by      NVARCHAR(200) NULL,
    decision_notes  NVARCHAR(MAX) NULL,
    applied_at      DATETIME2     NULL,
    application_result JSON       NULL
);
CREATE INDEX IX_proposals_status ON dbo.proposed_changes(status, proposed_at);

CREATE TABLE dbo.autonomous_changes (
    change_id   BIGINT IDENTITY PRIMARY KEY,
    review_id   BIGINT        NULL REFERENCES dbo.system_reviews(review_id),
    applied_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    category    NVARCHAR(100) NOT NULL,
    description NVARCHAR(MAX) NOT NULL,
    target_table NVARCHAR(200)NULL,
    target_id    NVARCHAR(200)NULL,
    before_state JSON         NULL,
    after_state  JSON         NULL,
    reversible   BIT          NOT NULL DEFAULT 1,
    reverted_at  DATETIME2    NULL
);
CREATE INDEX IX_auto_changes_applied ON dbo.autonomous_changes(applied_at DESC);

-- Materialized rollup view used by the Reviewer's metric gathering
CREATE OR ALTER VIEW dbo.v_ingestion_quality_7d AS
SELECT
    s.source_type,
    s.feed_id,
    f.name AS feed_name,
    rs.domain,
    COUNT(*) AS items,
    AVG(rs.score) AS mean_score,
    SUM(CASE WHEN rs.score < 0.3 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS noise_rate
FROM dbo.sources s
LEFT JOIN dbo.feed_sources f ON f.feed_id = s.feed_id
LEFT JOIN dbo.relevance_scores rs ON rs.source_id = s.source_id
WHERE s.captured_at >= DATEADD(day, -7, GETUTCDATE())
GROUP BY s.source_type, s.feed_id, f.name, rs.domain;
```

(All v3 tables — `processed_emails`, `processed_links`, `processed_feed_items`, `feed_sources`, `sources`, `notes`, `patterns`, `authors`, `tracked_libraries`, `benchmark_snapshots`, `relevance_scores`, `gsd_runs`, `synthesis_runs` — remain unchanged.)

### 4.4 Embedding generation

Same as v3 — server-side via `AI_GENERATE_EMBEDDINGS` against the registered `EmbeddingModel`.

---

## 5. Configuration

### `.env.example`
(Unchanged from v3 — M365, Anthropic, GitHub, SQL Server, embedding model, vault path, etc.)

### `config/target-domains.yaml`
(Unchanged from v3 — three domains with profiles.)

### `config/tracked-feeds.yaml`
(Unchanged from v3 — arXiv, Anthropic/OpenAI/LangChain blogs, GitHub trending, SWE-bench/GAIA, CISA KEV, MSRC, Search Engine Journal, etc.)

### `config/tracked-libraries.yaml`, `config/tracked-authors.yaml`
(Unchanged from v3.)

### `config/settings.yaml` (additions for v4)
```yaml
mail:
  folder: Brain
  on_processed: label
  label_name: Processed

extraction:
  tiktok_enabled: true
  whisper_model: base
  max_video_duration_seconds: 7200
  arxiv_extract_full_pdf: true
  arxiv_reproducibility_score: true

gsd:
  verifier_retry: 1
  on_verifier_fail: review_folder
  duplicate_threshold: 0.92

synthesizer:
  new_sources_threshold: 10
  scheduled_cadence_days: 7
  min_sources_for_pattern: 3

vault:
  inbox_retention_days: 30
  stub_creation: true

database:
  connection_pool_size: 5
  command_timeout_seconds: 60
  use_vector_index_preview: true

# ★ NEW: self-review
reviewer:
  cadence_days: 7
  autonomous_threshold_adjust_max: 0.1     # max ±delta on relevance thresholds per review
  autonomous_arxiv_max_per_poll_bounds: [5, 40]
  noise_rate_warn: 0.6                     # feed flagged if >60% of items are below all-domain thresholds
  noise_rate_propose_drop: 0.85            # auto-proposal to drop feed if >85% noise for 3 reviews running
  stale_pattern_threshold_days: 90
  pattern_decay_rate: 0.97                 # multiplied per daily decay run on stale patterns
  pattern_archive_confidence: 0.2          # below this, propose archival
  cost_alert_threshold_pct: 1.25           # alert if weekly cost > 125% of prior 4-week median
  manual_only_categories:                  # never autonomous, always proposal
    - schema
    - domain_profile
    - vault_structure
```

---

## 6. Repo Structure (additions for v4)

```
cortex/
├── sql/
│   ├── migrations/
│   │   ├── 0001_initial.sql
│   │   ├── 0002_vector_index.sql
│   │   ├── 0003_external_model.sql
│   │   ├── 0004_feeds_and_benchmarks.sql
│   │   ├── 0005_patterns.sql
│   │   └── 0006_review_and_proposals.sql      ★
│   └── procs/
│       ├── usp_search_brain.sql
│       ├── usp_get_patterns.sql
│       ├── usp_upsert_note.sql
│       ├── usp_upsert_pattern.sql
│       ├── usp_score_authors.sql
│       └── usp_decay_patterns.sql              ★
├── src/cortex/
│   ├── ... (all v3 modules)
│   └── reviewer/                                ★
│       ├── reviewer.py
│       ├── metrics.py
│       ├── findings.py
│       ├── autonomous.py
│       └── proposals.py
├── agents/
│   ├── researcher.md
│   ├── planner.md
│   ├── executor.md
│   ├── verifier.md
│   ├── synthesizer.md
│   └── reviewer.md                              ★
├── scripts/
│   ├── ingest_once.py
│   ├── poll_feeds.py
│   ├── check_libraries.py
│   ├── crawl_authors.py
│   ├── snapshot_benchmarks.py
│   ├── synthesize.py
│   ├── decay_patterns.py                        ★
│   ├── review.py                                ★
│   ├── apply_proposals.py                       ★
│   ├── reprocess.py
│   └── serve_mcp.py
└── skills/
    ├── add-extractor/SKILL.md
    ├── add-feed/SKILL.md
    ├── add-domain/SKILL.md
    ├── debug-pipeline/SKILL.md
    ├── inspect-vault/SKILL.md
    ├── inspect-brain-db/SKILL.md
    └── review-the-brain/SKILL.md                ★
```

---

## 7. Implementation Phases

### Phase 1 — Plumbing
M365 + SQL Server provisioning + article extractor + naive vault write to `/Inbox/`. **Acceptance:** one-link email produces a vault note + `dbo.notes` row.

### Phase 2 — Full Extractors + Embeddings
All extractors including code-aware repo extraction + arXiv. Server-side embedding via `AI_GENERATE_EMBEDDINGS`. **Acceptance:** mixed-link email → typed notes with embeddings; nearest-neighbor query returns sensible results.

### Phase 3 — Target Domains + Relevance + GSD
Three-domain relevance + Researcher/Planner/Executor/Verifier subagents + per-domain `/Lessons/` + `/Frameworks/`. **Acceptance:** ingested item → source + per-domain lessons + author note, verifier passes.

### Phase 4 — Feed Ingestion + Schedulers
Feed Watchers (arXiv, RSS, GitHub trending, benchmarks) + schedulers + vault watcher. **Acceptance:** new arXiv paper ingested within one poll cycle; new CISA KEV entry produces a note within 6h; new trending agent repo auto-added.

### Phase 5 — Patterns + Synthesizer + MCP
Synthesizer with threshold + scheduled triggers + `/Patterns/` + `dbo.patterns` + full MCP tool set. **Acceptance:** consumer repo calls `get_patterns("agent-orchestration", "reflection")` and receives ≥1 well-formed pattern with examples.

### Phase 6 — Self-Review ★
- `0006_review_and_proposals.sql` applied
- Pattern decay daily job (`scripts/decay_patterns.py`)
- Reviewer subagent pipeline (`scripts/review.py`) — runs every 7 days
- Proposal-application workflow (`scripts/apply_proposals.py`)
- Meta vault folder: `/Meta/Reviews/`, `/Meta/Proposals/{pending,approved,rejected}/`, `/Meta/Health/`
- New MCP tools: `get_last_review`, `get_pending_proposals`, `decide_proposal`, `get_system_health`
- **Acceptance:** after two weeks of real ingestion, a scheduled review produces a `/Meta/Reviews/{date}.md` with metrics, ≥1 autonomous adjustment recorded in `dbo.autonomous_changes`, and ≥0 proposals in `/Meta/Proposals/pending/`. Approving a proposal via frontmatter edit results in the action being applied within 24h.

### Phase 7 — Hardening
Webhook-based M365 subscriptions, cost monitoring dashboards, vault GC, Change Event Streaming on `dbo.patterns` for near-real-time consumer updates, reproducibility scoring tuning, review-of-the-reviewer (does the system actually improve over time?).

---

## 8. Open Decisions

1. **Embedding model & dim** — default `text-embedding-3-small` (1536); swap for local Ollama or different OpenAI model as needed.
2. **SQL Server hosting** — local Docker, on-prem, or Azure SQL MI on SQL Server 2025 update policy.
3. **Preview features** — `VECTOR_SEARCH` + `CREATE VECTOR INDEX` are preview; fine for personal use, flag for regulated environments.
4. **arXiv volume** — tune `max_per_poll` and reproducibility filter to control inflow.
5. **GitHub trending scraping** — no official API; brittle; plan for breakage.
6. **Pattern confidence calibration** — tune `pattern_archive_confidence` after the first 2-3 reviews.
7. **Vault location** — git repo recommended for versioning.
8. **Run environment** — laptop, always-on box, or container; DB must be reachable.
9. **Cost ceiling** — daily $ cap across Claude + Whisper + embedding model.
10. **PII / private content** — what is allowed from emails?
11. **Reviewer autonomy bounds** — the defaults in `settings.yaml` are conservative; tune based on trust developed over the first few reviews.
12. **Conflict handling** — what to do if two consecutive reviews propose opposite changes? Default: mark earlier proposal `superseded`, log for human attention.

---

## 9. CLAUDE.md (project guidance, condensed)

```markdown
# Cortex — Knowledge Brain

Builds and self-improves a knowledge brain across three domains: agent-orchestration,
seo-agents, tech-support-agents. Ingests from M365 mail + direct feeds. Synthesizes
reusable patterns. Reviews itself every 7 days. Exposes everything to consumer
Claude Code repos via MCP.

## Key files
- SPEC.md — full system spec; always defer to this
- sql/migrations/ — schema source of truth
- config/target-domains.yaml — the three domains
- config/tracked-feeds.yaml — direct feed sources
- config/settings.yaml — reviewer cadence and autonomy bounds
- agents/ — subagent prompts

## Conventions
- Vault writes go through src/cortex/vault/writer.py; ALSO writes mirrored row to dbo.notes in same transaction
- All SQL via src/cortex/db/repositories.py — no raw pyodbc elsewhere
- All Claude calls via src/cortex/llm.py with usage tracking
- Embeddings generated server-side via AI_GENERATE_EMBEDDINGS — never in Python
- Patterns are the primary artifact for consumer repos
- Every autonomous change MUST insert a dbo.autonomous_changes row with before/after state
- Every proposal MUST create both a /Meta/Proposals/pending/ note AND a dbo.proposed_changes row
- The Reviewer NEVER changes schema, domain profiles, or vault structure autonomously — those are proposal-only

## When adding things
- New extractor → `add-extractor` skill
- New feed → `add-feed` skill
- New domain → `add-domain` skill (also re-scores recent content)
- Investigating a review → `review-the-brain` skill

## Testing
`pytest tests/` — DB tests use per-test transactions that roll back. Reviewer tests use a fixture brain state.
```

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| TikTok scraping breaks | Isolated extractor; log + skip |
| arXiv volume overwhelms pipeline | `max_per_poll`, abstract pre-filter, reproducibility scoring |
| GitHub trending scraper breaks | Retry + fallback to GitHub API search; flag if no results 2x running |
| Claude hallucination in synthesis | Verifier requires every example to trace to a source; pattern confidence reflects corroboration |
| Vault grows unbounded | `/Inbox` GC + thresholds + author auto-prune + Reviewer proposes archival |
| M365 token expiry | Refresh rotation + alert |
| Re-ingestion via different shortener | Canonicalize URLs |
| Wikilink rot | Stub-creation + Reviewer flags orphans |
| Cost spikes | Daily cap + per-source budget + Reviewer cost alerting |
| Embedding dim change | Migration re-embeds all notes + patterns; `VECTOR(dim)` enforces consistency |
| Preview-feature regressions | Pin SQL Server build; regression tests |
| Mirror inconsistency (file/row) | Vault writer wraps in transactional pattern |
| Pattern drift | Decay + Reviewer corroboration check + archival proposals |
| Threat-intel feed bursts | Rate-limit per domain; batch to digest if >N items/hour |
| **Reviewer makes bad autonomous changes** | **Strict bounds in settings.yaml + every change has reversible audit row + a `revert_change(change_id)` script** |
| **Reviewer self-aggrandizes (proposes changes that benefit itself)** | **Manual-only categories list; verifier phase cross-checks proposals; periodic human spot-check of `/Meta/Reviews/` is the safeguard** |
| **Proposal backlog accumulates** | **Reviewer reports pending proposal count; if >N for 2 reviews, top-level finding flags human attention** |
| **Conflicting proposals across reviews** | **Mark earlier proposal `superseded` with rationale; log for human attention** |

---

## 11. Definition of Done (v1)

The system is "done" for v1 when:
- Forward an email with mixed links → within one poll cycle, typed notes appear in vault and `dbo.notes` with embeddings, per-domain relevance, lessons.
- New arXiv paper matching `arxiv-agents` filters captured and scored within one poll cycle.
- New CISA KEV entry produces a note in `/Lessons/tech-support-agents/` within 6h.
- New trending agent framework repo auto-appears in `/Frameworks/` and `dbo.tracked_libraries`.
- Weekly synthesizer run on a domain produces or updates ≥1 `/Patterns/` entry.
- Consumer repo `get_patterns("tech-support-agents", "diagnostic")` returns relevant patterns with examples; `search_brain(...)` returns ranked notes.
- **After two weeks of operation, the 7-day Reviewer produces a `/Meta/Reviews/{date}.md` with real metrics, applies ≥1 autonomous adjustment with audit row, queues ≥0 proposals; approving a proposal via frontmatter edit results in the action being applied within 24h.**
- A week of normal use costs less than your configured daily cap × 7.
