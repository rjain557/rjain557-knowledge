---
type: cortex-improvement-prompt
generated_by: cortex-repo-review
repo: rjain557/rjain557-knowledge
domain: agent-orchestration
impact: high
effort: M (<1 week)
generated_at: 2026-05-30T03:01:42.068502-07:00
---

# Replace stateless per-run context assembly with a compiled 'agent contract' artifact

**Impact:** high  ·  **Effort:** M (<1 week)

## Rationale

Vault note [4] ('Your AI agent is rediscovering 85% of its context every run') argues that agents fail not because retrieval is wrong but because the retrieval system can't assemble what the agent needs before it starts acting. The daily repo-review commits show the same pattern: each run re-assembles context from scratch. A pre-compiled 'session contract' YAML (repo summary, active workflows, last-run state, top-5 relevant vault slugs) written at the end of each run and read at the start of the next would cut orientation tokens and reduce drift between runs.

## Cited evidence

- Inbox/2026-05-12-your-ai-agent-is-rediscovering-85-of-its-context-every-run-h.md

## Prompt (paste into Claude Code from repo root)

```
Working directory: repo root.

Context files to read first:
  - CLAUDE.md
  - scripts/ (read every .py and .ps1 file to understand the run lifecycle)
  - src/cortex/ (find the repo-review and deep-research entry points)
  - .env.example (understand available env vars)

Task: Implement a session-contract artifact that persists agent state between runs.

Step 1 – Contract schema
Create src/cortex/session/contract.py with a Pydantic v2 model SessionContract:
  - run_id: str (uuid4)
  - generated_at: datetime (UTC)
  - active_workflows: list[str]  # names of workflows that ran last cycle
  - last_ingested_urls: list[str]  # up to 20 most recent URLs written to vault
  - pending_deep_research_topics: list[str]  # topics queued but not yet researched
  - top_vault_slugs: list[str]  # top 10 slugs by recency
  - error_summary: list[str]  # any errors from last run, one line each

Step 2 – Writer
Add write_contract(contract: SessionContract, path: Path) that serializes to YAML (use PyYAML) and writes atomically.

Step 3 – Reader
Add load_contract(path: Path) -> SessionContract | None that returns None if file missing or unparseable (log warning, don't crash).

Step 4 – Integration
In the main orchestration entry point (find it in scripts/ or src/):
  a) At startup: load .cache/session_contract.yaml, log a one-line summary of last state.
  b) At shutdown (try/finally): build a new SessionContract from this run's data and write it.

Step 5 – CLAUDE.md update
Append a section '## Session Contract' to CLAUDE.md explaining that agents should read .cache/session_contract.yaml at the start of every session to avoid re-discovering context.

Edge cases:
  - First run (no contract file): proceed normally, write contract at end.
  - Contract file corrupted: catch yaml.YAMLError, log, treat as missing.
  - Concurrent runs: write to .cache/session_contract.tmp then os.replace() for atomicity.

Verification:
  1. Run the main orchestration script once; confirm .cache/session_contract.yaml is created.
  2. Run it again; confirm the startup log line shows last run's data.
  3. Manually corrupt the YAML; confirm the script still starts (logs warning, doesn't crash).
  4. Confirm .cache/ is in .gitignore.
```
