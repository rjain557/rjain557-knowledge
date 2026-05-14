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

**v4.1 changes vs v4 (2026-05-14):**
- New **Deep Research Pipeline** (§3.13) — STORM-based orchestrator that takes a topic and recursively pulls 20–80 adjacent sources, synthesizes a `/Topics/{slug}.md` article with citation tracking
- Extended **§3.4 extractors** with: faster-whisper, marker-pdf, GROBID, firecrawl/crawl4ai, twscrape, PRAW, HN Algolia, feedparser+podcast pipeline, paperscraper + Semantic Scholar + OpenAlex
- New **discovery layer** (`src/cortex/discovery/`) abstracting Tavily, Exa, Brave, SearXNG, Semantic Scholar, OpenAlex, GitHub Code Search, HN Algolia, Claude `web_search`
- New schema migration `0007_deep_research.sql` (`dbo.deep_research_runs` + `dbo.sources.discovery_path`)
- New MCP tools: `deep_research(topic, domains?)`, `list_research_runs`, `get_research_run`
- New Phase 5.5 between v4's Phase 5 and Phase 6
- New §8 decisions 13–18 (orchestrator pick, cost ceilings, PDF/whisper provider, dedup behavior, STORM-shape compatibility)
- New §10 risks specific to search API costs, recursion, backend deprecation, STORM quality, citation hallucination

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
| Article | trafilatura | playwright → **firecrawl** OR **crawl4ai** | Strip nav/ads; preserve code blocks. Firecrawl/crawl4ai handle JS-heavy + bot-protected sites |
| YouTube | youtube-transcript-api | yt-dlp → **faster-whisper** | Chapters, description, channel. faster-whisper is 5–10× speed of openai-whisper; whisper.cpp for CPU-only |
| TikTok | yt-dlp + cookies (`--cookies-from-browser`) | whisper on audio + **TikTokApi** for metadata | Expect breakage; log + skip |
| **Twitter/X** | **twscrape** (account-based) OR Twitter API v2 (paid) | snscrape (deprecated, last-resort) | Threads expanded; quote-tweets included as related sources |
| **Reddit** | **PRAW** (official) | redditwarp | Comment trees flattened to thread-summary + top comments |
| **HackerNews** | **HN Algolia API** (free, no auth) | n/a | Top comments + parent thread; filter by points threshold |
| **Podcast** | **feedparser** (RSS) → yt-dlp → faster-whisper | n/a | RSS-discovered episodes; Apple Podcasts JSON for metadata |
| **LinkedIn post** | (deferred) | Apify / Phantombuster (paid) | Hard target; defer until forwarded volume justifies |
| GitHub repo | GitHub REST | gh CLI | README + releases + commits + topics + code artifacts |
| PDF | **marker-pdf** (LLM-quality) | pdftotext → **docling** (IBM, academic) → tesseract OCR | marker preserves tables/figures/equations as markdown; docling is best for academic PDFs |
| ArXiv | arXiv API + PDF + **GROBID** (structured) | n/a | Abstract/methods/results split via GROBID; reproducibility score |
| **Academic (multi-source)** | **paperscraper** + **Semantic Scholar API** + **OpenAlex** | n/a | Cross-references arXiv with citation graph; pulls full text from open-access mirrors |

**Code-aware extraction.** For agent-related repos, additionally pull `prompts/**`, `agents/**.py`, `**/system_prompt*.md`, `**/tools.py`, `**/*tool_schema*.json`, example notebooks, configs — tagged `type: code_artifact` for the Patterns layer.

**Tool inventory (v4.1, verified 2026-05-14).** OSS unless noted. Pin versions in `requirements.txt`; reviewer flags any deprecation.

| Tool | License | Why chosen | Alternative |
|---|---|---|---|
| trafilatura | Apache-2.0 | best general-purpose article extractor | newspaper4k |
| playwright | Apache-2.0 | JS rendering when trafilatura fails | selenium |
| firecrawl-py | MIT (SaaS+self-host) | clean markdown from bot-protected sites | crawl4ai (full OSS) |
| crawl4ai | Apache-2.0 | LLM-friendly OSS scraper | firecrawl |
| yt-dlp | Unlicense | covers ~1700 sites incl. YouTube/TikTok | youtube-dl (stale) |
| youtube-transcript-api | MIT | free, no API key | n/a |
| faster-whisper | MIT | 5–10× speed via CTranslate2 | whisper.cpp (CPU), Groq Whisper (cheapest API) |
| TikTokApi | MIT | unofficial Python SDK | n/a |
| twscrape | MIT | account-based X scraping | snscrape (deprecated) |
| PRAW | BSD-2 | official Reddit wrapper | redditwarp |
| feedparser | BSD-2 | RSS / Atom for podcasts + blogs | n/a |
| marker-pdf | GPL-3 | LLM-quality PDF → markdown | docling, pymupdf4llm |
| docling | MIT | IBM's; strongest on academic | marker, GROBID |
| GROBID | Apache-2.0 | structured PDF (sections/refs/figures) | docling |
| paperscraper | Apache-2.0 | multi-source academic (arXiv, biorxiv, chemrxiv, pubmed) | scholarly |
| Semantic Scholar API | free | citation graph + recommendations | OpenAlex |
| OpenAlex | free, CC0 | full Crossref alt; no rate limit | Semantic Scholar |
| HN Algolia API | free | best HN search | hn-search |

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

### 3.13 Deep Research Pipeline (`src/cortex/deep_research/`) ★ v4.1

A dedicated agent pipeline that takes a single high-relevance source (or an explicit topic) and recursively expands it into the full source landscape — pulling adjacent papers, repos, threads, videos, podcasts — then synthesizes a structured topic article. Output lands in `/Topics/{slug}.md` (the article) and `/Patterns/{Domain}/{name}.md` (any patterns that emerge from the multi-source synthesis).

**Why this is separate from the regular ingestion pipeline.** The regular pipeline (§3.1–§3.6) extracts a single forwarded link and writes one source note. Deep Research starts from a topic question and goes wide: 20–80 sources per run, multi-perspective question fanout, citation tracing. Cost profile is 100–1000× a single ingestion. Needs explicit budget cap and rate limiting.

**Triggers:**

| Trigger | Notes |
|---|---|
| Manual | `/deep-research <topic>` slash command, or MCP `deep_research(topic, domains?)` from any consumer repo |
| Auto (post-ingestion) | An ingested source scores ≥0.9 relevance for any domain AND the per-domain config has `auto_expand_threshold: 0.9` set. Rate-limited to ≤3 auto-runs per day. |
| Auto (gap-filling) | Reviewer's coverage-gap finding (§3.12) flags a recurring low-quality topic. Reviewer creates a proposal for human approval; on approval, deep research fires. |

**Pipeline phases (mirrors GSD):**

1. **Outline** — given the topic, an LLM call generates an outline of N sub-questions (default N=8). STORM-style multi-perspective: each sub-question represents a different angle (technical / historical / contested / practical / adjacent-fields).
2. **Search** — for each sub-question, hit the discovery layer (see below). Tavily is the primary; Exa is the semantic-similarity fallback for "find more like this"; Semantic Scholar / OpenAlex for academic; GitHub / Sourcegraph for code; HN Algolia / Reddit for discussion.
3. **Extract** — each discovered URL goes through the §3.4 extractor pipeline. Results write to `dbo.sources` with `discovery_path` (which sub-question + which search engine surfaced it).
4. **Score** — each extracted source gets a per-domain relevance score (§3.5). Sources below threshold for every domain are kept but flagged as `peripheral`.
5. **Synthesize** — STORM (or GPT-Researcher fallback) generates the structured article from the extracted sources, tracking citations per claim.
6. **Verify** — verifier subagent checks that every claim in the article cites at least one source (no hallucinated facts), checks for near-duplicate content already in the vault via `VECTOR_SEARCH`, and rejects if either fails. On reject: queue for human review at `/Inbox/_review/`.
7. **Pattern extraction** — if 3+ sources corroborate a reusable pattern, write it to `/Patterns/{Domain}/{name}.md` and `dbo.patterns` (re-uses the §3.10 synthesizer logic).
8. **Persist** — write `/Topics/{slug}.md` (article) + `dbo.deep_research_runs` row with cost, source count, and citation graph.

**Discovery layer (Tier 2):**

| Capability | Tool | Auth | Notes |
|---|---|---|---|
| Web search built for AI | **Tavily** | API key (paid; free tier) | Primary general-purpose. Has a one-call "research" endpoint that returns a synthesized report — useful as a fast path. |
| Semantic similarity | **Exa** | API key (paid; free tier) | "Find pages like this URL" — best for finding adjacent sources |
| Free meta-search | **SearXNG** | self-host | Aggregates Google/Bing/DuckDuckGo; fallback when API budgets exhausted |
| Independent web index | **Brave Search API** | API key (free tier) | Independent of Google; complements Tavily |
| Anthropic-built | **Claude `web_search` tool** | API (per-call cost) | Built into the Claude API; zero infra; high quality |
| Academic | **Semantic Scholar API**, **OpenAlex** | free | Citation graph + recommendations |
| Code | **GitHub Code Search API**, **Sourcegraph** | API key (GitHub PAT) | Beyond `github_trending` feed |
| Real-time | **HN Algolia API**, **Bluesky firehose**, **Mastodon API** | free / OAuth | News-cycle topics |
| Video | **YouTube Data API v3** | API key (free quota) | Channel + topic search beyond trending |

Pick exactly one as the **primary general-purpose search** (default: **Tavily**) and one as the **semantic similarity** engine (default: **Exa**). Self-host **SearXNG** as cost-overflow fallback. Academic is always Semantic Scholar + OpenAlex (both free, complementary).

**Orchestrator (Tier 3 — pick one):**

| Project | License | Approach | When to pick |
|---|---|---|---|
| **STORM** ([stanford-oval/storm](https://github.com/stanford-oval/storm)) | MIT | Multi-perspective Q&A → Wikipedia-style article | **Default.** Output shape (structured, multi-perspective, citation-tracked) maps cleanly onto Cortex's `/Topics/` artifacts |
| **GPT-Researcher** ([assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher)) | Apache-2.0 | Plan → search → scrape → summarize → report | Backup when STORM proves too academic-shaped (esp. for `tech-support-agents` domain) |
| **smolagents Open Deep Research** | Apache-2.0 | Agent with web search + browser + Python interpreter | Lightweight; matches Cortex's GSD style; consider for v5 |
| **OpenAI Deep Research API** | paid | Hosted; o3 + tool use | Drop-in if zero-infra is the priority; expensive |
| **Tavily Research API** | paid | Hosted; one endpoint returns the report | Cheapest hosted option; trades depth for speed |
| **Perplexity API** (`sonar-deep-research`) | paid | Hosted; fastest | Seconds vs minutes; trades thoroughness for latency |

**Default stack (locked 2026-05-14):** STORM + Tavily + Exa + SearXNG (overflow) + faster-whisper + marker-pdf + firecrawl. All extractors per §3.4 v4.1 table.

**Cost model.** Each deep research run costs roughly:
- 8 Tavily searches × $0.01 = $0.08
- 30 Exa lookups × $0.005 = $0.15
- 40 article extractions (mostly free; firecrawl ~$0.003/page = $0.12 worst case)
- 10 PDFs through marker (CPU-heavy; free, ~5min compute)
- 3 video transcriptions × 30min × Groq Whisper ($0.04/hr) = $0.06
- LLM (STORM) ~80K input tokens + 20K output → ~$0.5 (Sonnet) or ~$0.2 (Haiku for outline + Sonnet for synthesis)
- **Per-run estimate: $1–$2.** Cap at `deep_research.cost_cap_usd` (default $2). Halt mid-run if cost exceeded; persist what was extracted.

**Rate limiting.** `deep_research.max_runs_per_day` (default 3 auto + unlimited manual). Reviewer escalates to a proposal if auto-runs consistently hit the cap.

**Dedup.** Before writing `/Topics/{slug}.md`, check via `VECTOR_SEARCH` against existing `/Topics/`. If similarity > 0.9, merge into the existing topic (append a `## v2 (yyyy-mm-dd)` section with new findings) rather than creating a duplicate.

**Output schema.** A deep-research topic note frontmatter:

```yaml
type: topic
domain: agent-orchestration
generated_by: deep_research
research_run_id: 142
sources_consulted: 47
sources_cited: 31
search_engines_used: [tavily, exa, semantic_scholar, github_search]
cost_usd: 1.42
duration_minutes: 6.2
citation_graph: { ... }   # per-claim → source map
```

The body is a STORM-style structured article: introduction → outlined sections → references. Every paragraph cites at least one source from `sources_cited`.

**Schema additions (`0007_deep_research.sql`):**

```sql
CREATE TABLE dbo.deep_research_runs (
    run_id           BIGINT IDENTITY PRIMARY KEY,
    topic            NVARCHAR(500) NOT NULL,
    triggered_by     NVARCHAR(50)  NOT NULL,           -- manual | auto_post_ingest | reviewer_gap
    triggered_source_id BIGINT     NULL REFERENCES dbo.sources(source_id),
    domains          JSON          NOT NULL,
    started_at       DATETIME2     NOT NULL,
    finished_at      DATETIME2     NULL,
    sources_consulted INT          NOT NULL DEFAULT 0,
    sources_cited    INT           NOT NULL DEFAULT 0,
    search_engines_used JSON       NULL,
    cost_usd         DECIMAL(8,4)  NULL,
    output_topic_path NVARCHAR(1000) NULL,
    output_pattern_ids JSON        NULL,
    status           NVARCHAR(50)  NOT NULL DEFAULT 'running',
    failure_reason   NVARCHAR(MAX) NULL
);

ALTER TABLE dbo.sources ADD discovery_path JSON NULL;   -- {sub_question, engine, query} for deep-research-discovered sources
```

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

# ★ NEW v4.1: deep research pipeline
deep_research:
  enabled: true
  primary_search: tavily                   # tavily | exa | brave | searxng | claude_web_search
  semantic_search: exa                     # exa | tavily
  academic_sources: [semantic_scholar, openalex]
  code_search: [github, sourcegraph]
  realtime_sources: [hn_algolia]
  orchestrator: storm                      # storm | gpt_researcher | smolagents | tavily_research_api | perplexity | openai_deep_research
  outline_questions: 8                     # N sub-questions per topic; STORM default
  cost_cap_usd: 2.0                        # halt mid-run if exceeded
  max_runs_per_day_auto: 3                 # rate limit on auto-triggered runs (manual unlimited)
  auto_expand_threshold: 0.9               # ingested source above this score auto-triggers deep research
  dedup_similarity_threshold: 0.9          # if new topic > this similarity to existing, merge instead of create
  llm_model_outline: claude-haiku-4-5      # cheap for outline generation
  llm_model_synthesis: claude-sonnet-4-6   # synthesis quality matters
  whisper_provider: groq                   # groq | local_faster_whisper | openai
  pdf_extractor: marker                    # marker | docling | pdftotext
  scraper_overflow: searxng                # fallback when paid search budgets exhausted

# ★ NEW v4.1: extractor tools (override defaults from §3.4)
extractors_v41:
  article_fallback: firecrawl              # firecrawl | crawl4ai | playwright
  twitter_backend: twscrape                # twscrape | api_v2
  reddit_backend: praw
  pdf_primary: marker
  pdf_academic: docling
  pdf_structured: grobid                   # for arXiv pipeline
  podcast_transcription: faster_whisper
  whisper_compute_type: int8               # int8 | float16 | float32 (faster-whisper only)
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
│   │   ├── 0006_review_and_proposals.sql      ★
│   │   └── 0007_deep_research.sql              ★★ v4.1
│   └── procs/
│       ├── usp_search_brain.sql
│       ├── usp_get_patterns.sql
│       ├── usp_upsert_note.sql
│       ├── usp_upsert_pattern.sql
│       ├── usp_score_authors.sql
│       ├── usp_decay_patterns.sql              ★
│       └── usp_dedup_topic.sql                 ★★ v4.1 — vector-search-based topic dedup
├── src/cortex/
│   ├── ... (all v3 modules)
│   ├── reviewer/                                ★
│   │   ├── reviewer.py
│   │   ├── metrics.py
│   │   ├── findings.py
│   │   ├── autonomous.py
│   │   └── proposals.py
│   ├── extractors/                              ★★ v4.1 additions
│   │   ├── article.py            # trafilatura + playwright + firecrawl/crawl4ai fallback
│   │   ├── youtube.py            # youtube-transcript-api → yt-dlp + faster-whisper
│   │   ├── tiktok.py             # yt-dlp + TikTokApi
│   │   ├── twitter.py            # twscrape (account-based)
│   │   ├── reddit.py             # PRAW
│   │   ├── hackernews.py         # HN Algolia
│   │   ├── podcast.py            # feedparser + yt-dlp + faster-whisper
│   │   ├── pdf.py                # marker → docling → pdftotext → tesseract
│   │   ├── arxiv.py              # arXiv API + GROBID
│   │   ├── academic.py           # paperscraper + Semantic Scholar + OpenAlex
│   │   └── repo.py               # GitHub REST + gh CLI + code-aware harvest
│   ├── discovery/                               ★★ v4.1
│   │   ├── tavily.py             # primary general search
│   │   ├── exa.py                # semantic similarity
│   │   ├── searxng.py            # OSS overflow
│   │   ├── brave.py              # independent index
│   │   ├── semantic_scholar.py
│   │   ├── openalex.py
│   │   ├── github_search.py      # code search
│   │   ├── hn_algolia.py
│   │   └── claude_web_search.py  # Anthropic-built search tool
│   └── deep_research/                           ★★ v4.1
│       ├── orchestrator.py       # main pipeline (STORM by default)
│       ├── outline.py            # multi-perspective question fanout
│       ├── search_dispatcher.py  # routes sub-questions to discovery layer
│       ├── extract_dispatcher.py # routes URLs to §3.4 extractors
│       ├── storm_adapter.py      # STORM integration
│       ├── gpt_researcher_adapter.py  # GPT-Researcher fallback
│       ├── synthesizer.py        # article generation with citation tracking
│       ├── verifier.py           # claim → source verification
│       ├── dedup.py              # vector-search-based topic merge
│       └── cost_tracker.py       # halt mid-run if cost cap exceeded
├── agents/
│   ├── researcher.md
│   ├── planner.md
│   ├── executor.md
│   ├── verifier.md
│   ├── synthesizer.md
│   ├── reviewer.md                              ★
│   └── deep_researcher.md                       ★★ v4.1
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
    ├── review-the-brain/SKILL.md                ★
    ├── deep-research/SKILL.md                   ★★ v4.1 — manual /deep-research trigger
    └── tune-discovery/SKILL.md                  ★★ v4.1 — switch search backends, calibrate
```

Plus `scripts/deep_research.py` (one-shot CLI runner) added alongside the v4 scripts.

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

### Phase 5.5 — Deep Research Pipeline ★★ v4.1
- `0007_deep_research.sql` applied (`dbo.deep_research_runs` + `dbo.sources.discovery_path`)
- All v4.1 extractors landed (`src/cortex/extractors/{twitter,reddit,hackernews,podcast,academic}.py`); v4 article/youtube/tiktok/pdf/arxiv extractors swap in firecrawl/faster-whisper/marker/GROBID per `extractors_v41` config
- Discovery layer wired (`src/cortex/discovery/{tavily,exa,searxng,brave,semantic_scholar,openalex,github_search,hn_algolia,claude_web_search}.py`)
- STORM adapter (`src/cortex/deep_research/storm_adapter.py`) as primary orchestrator; GPT-Researcher adapter as fallback
- New MCP tools: `deep_research(topic, domains?)`, `list_research_runs(days=30)`, `get_research_run(run_id)`
- `/deep-research <topic>` slash command (manual trigger)
- Auto-trigger on `relevance ≥ 0.9` + `auto_expand_threshold` config (rate-limited to 3/day)
- Cost tracking + halt mid-run if `cost_cap_usd` exceeded
- Vector-search-based topic dedup (`usp_dedup_topic.sql`); merge into existing topic if similarity > 0.9
- **Acceptance:** `/deep-research "agent reflection patterns"` produces `/Topics/agent-reflection-patterns.md` with ≥20 sources cited, ≥1 pattern extracted to `/Patterns/AgentOrchestration/`, total cost ≤ $2, citation graph in `dbo.deep_research_runs`. Verifier rejects on hallucinated claims (no citation). Re-running same topic merges instead of duplicates.

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
13. **Deep research orchestrator** ★ v4.1 — STORM is the default; switch to GPT-Researcher if STORM proves too academic-shaped for `tech-support-agents`. Tavily-Research-API or Perplexity considered for low-latency hosted fallback. Decide after Phase 5.5 acceptance.
14. **Search backend cost ceiling** ★ v4.1 — Tavily + Exa together can run ~$50–200/mo at default cost cap × 3 auto-runs/day. Set hard monthly cap in `settings.yaml > deep_research.monthly_cost_cap_usd` (default $200). SearXNG fallback when exceeded.
15. **PDF extractor pick** ★ v4.1 — `marker-pdf` is GPL-3 (license-incompatible with proprietary distribution), but Cortex is internal — fine. If Cortex is ever open-sourced under MIT/Apache, swap to `docling` (MIT) as primary.
16. **Whisper provider** ★ v4.1 — Groq (`whisper-large-v3-turbo` at ~$0.04/hr) is cheapest API; `faster-whisper` local on the production workstation if it has GPU; `whisper.cpp` CPU-only fallback. Decide based on production hardware.
17. **Auto-expand threshold** ★ v4.1 — `auto_expand_threshold: 0.9` is conservative (rare trigger). Lower to 0.85 if first month shows almost no auto-expansion; raise to 0.95 if it's firing too often.
18. **STORM article shape vs Cortex `/Topics/` shape** ★ v4.1 — STORM produces Wikipedia-style articles; verify the format works inside the existing topic-page schema (frontmatter + sections). May need a STORM post-processor to coerce output.

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
| **★ v4.1 — Search API costs balloon** | Hard `cost_cap_usd` per run + monthly cap + auto-fallback to SearXNG when paid budgets exhausted; reviewer flags Tavily/Exa/Firecrawl spend spikes weekly |
| **★ v4.1 — Deep research loops/recursion** | Outline phase caps sub-questions at N=8; max URLs per sub-question = 10; total source ceiling per run = 80; verifier kills runs producing >100 sources |
| **★ v4.1 — Search backend deprecation / API change** | Backends are abstracted behind `src/cortex/discovery/<name>.py` interface; reviewer flags >5% failure rate per backend; user can switch primary in `settings.yaml > deep_research.primary_search` |
| **★ v4.1 — STORM article quality varies by domain** | Per-domain orchestrator override in `target-domains.yaml`; `tech-support-agents` may switch to GPT-Researcher if reviewer flags low pattern-yield from STORM runs |
| **★ v4.1 — marker-pdf is GPL-3 (license risk)** | Documented in §8 decision 15; if Cortex ever open-sources, swap to docling (MIT) — interface is the same |
| **★ v4.1 — Whisper transcription quality on heavy accents / domain jargon** | Use Groq Whisper-large-v3-turbo by default (best small-model accuracy); local faster-whisper as fallback; reviewer flags transcripts with high-uncertainty segments for human review |
| **★ v4.1 — Citation hallucination in STORM output** | Verifier phase requires every claim in the article to cite at least one source from `sources_cited`; reject + rerun on failure; track per-run hallucination rate as reviewer metric |
| **★ v4.1 — Topic dedup false-positives merge unrelated topics** | `dedup_similarity_threshold: 0.9` is conservative; manual override via `/topic-split <slug>` slash command; reviewer surfaces merges with similarity 0.85–0.95 for human spot-check |

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
