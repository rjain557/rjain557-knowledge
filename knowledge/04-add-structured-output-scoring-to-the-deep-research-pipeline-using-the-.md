---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: medium
effort: M (<1 week)
generated_at: 2026-06-05T03:01:49.857565-07:00
---

# Add structured output scoring to the deep-research pipeline using the Haiku verifier

**Impact:** medium  ·  **Effort:** M (<1 week)

## Rationale

The commit history shows a 'Haiku verifier' was added (2026-05-16) alongside auto-Deep-Research, and the Langfuse vault note describes a complete scoring and evaluation pipeline. Currently there is no evidence that the verifier's judgments are persisted or aggregated — meaning the system cannot learn which research runs produce high-quality output or tune prompts over time. The vault note on Langfuse specifically covers the 'Scoring and Experiments' layer that closes this loop.

## Cited evidence

- Inbox/2026-05-23-build-a-complete-langfuse-observability-and-evaluation-pipel.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context to read first:
1. src/ — find the deep research pipeline file(s) and the Haiku verifier call site specifically
2. sql/ — find the table where deep research results are stored
3. CLAUDE.md — understand what the verifier is currently checking

Task: Persist Haiku verifier scores to SQL Server and expose a weekly score-trend report.

Steps:
1. In `sql/`, create a migration file `add_dr_scores.sql` that adds a `dr_scores` table:
   ```sql
   CREATE TABLE dr_scores (
     id INT IDENTITY PRIMARY KEY,
     run_id NVARCHAR(200) NOT NULL,        -- e.g. slug + date
     source_url NVARCHAR(2000),
     topic NVARCHAR(500),
     verifier_model NVARCHAR(100),
     score_factual_accuracy FLOAT,         -- 0.0-1.0
     score_coverage FLOAT,
     score_coherence FLOAT,
     score_overall FLOAT,
     verifier_reasoning NVARCHAR(MAX),
     scored_at DATETIME2 DEFAULT GETUTCDATE()
   );
   ```
2. Update the Haiku verifier call site in src/ to:
   a. Ask the verifier to return a JSON object with keys: `factual_accuracy`, `coverage`, `coherence`, `overall` (each 0.0-1.0) and `reasoning` (string). Use `response_format` or prompt the model to output only valid JSON.
   b. Parse the JSON response.
   c. Insert a row into `dr_scores` via the existing pyodbc connection pattern.
3. Create `scripts/dr_score_report.py` that:
   a. Queries `dr_scores` for the last 7 days
   b. Prints a markdown table: date | topic | overall_score | factual | coverage | coherence
   c. Flags any run with `score_overall < 0.6` with a ⚠️ prefix
   d. Writes the report to `logs/dr_score_report_{date}.md`
4. Add the report script to the weekly scheduled task (check scripts/ for the existing scheduler entry point).

Edge cases:
- If the verifier returns malformed JSON, log the raw response and insert a row with all scores as NULL rather than crashing the pipeline
- The verifier prompt must explicitly instruct the model to output ONLY the JSON object with no surrounding prose
- Score values outside [0.0, 1.0] should be clamped before insertion

Verification:
1. Trigger one deep research run manually and confirm a row appears in `dr_scores`
2. Run `python scripts/dr_score_report.py` and confirm a markdown file is created in logs/
3. Manually insert a row with `score_overall = 0.5` and confirm it appears with ⚠️ in the report
4. Test the malformed-JSON path by temporarily making the verifier return 'INVALID' and confirm the pipeline continues
```
