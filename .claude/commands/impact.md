---
description: Run GitNexus impact analysis on a target file/symbol before editing
arg_hint: <file-path-or-symbol>
---

Run GitNexus impact analysis on `$1`.

1. If `.gitnexus/` does not exist in this repo (Phase 1 — code not yet written), explain that the repo has no code to analyze and exit.
2. Otherwise call the GitNexus MCP `gitnexus_impact` tool with `target=$1`.
3. Render the result:
   - Direct callers
   - Transitive callers (depth 2)
   - Risk classification: LOW | MEDIUM | HIGH | CRITICAL
4. If risk is HIGH or CRITICAL, warn the user and recommend:
   - Read each direct caller before editing
   - Run the test suite that covers the callers
   - Consider an alternative approach (eg. add a new function rather than mutate the old one)
