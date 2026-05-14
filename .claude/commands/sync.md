---
description: Push the vault repo upstream (if a remote is configured), and pull/push the source repo
---

Two repos to sync.

### Vault repo (claude-memory)

1. `git -C "<vault>" status --short` — show pending changes.
2. If clean, skip. If dirty, commit with `[manual]` tag and a one-line message asking the user for the message.
3. Check if a remote is configured (`git -C "<vault>" remote -v`). If no remote, just notify and skip — the vault is local-only by default.
4. If a remote exists, push with `git -C "<vault>" push`.

### Source repo (rjain557-knowledge)

1. `git status --short` — show pending changes.
2. If dirty, ask the user before committing (don't auto-commit code changes).
3. Pull with rebase: `git pull --rebase`.
4. Show last 3 commits.

Always show: vault HEAD commit and source repo HEAD commit at the end so the user can record them.
