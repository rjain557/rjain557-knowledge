# Workstation Setup — rjain557-knowledge / Cortex

This document is the portable setup guide for the **Cortex / Inbox Brain** stack. Follow it on a new machine to bring up the full memory + code-intelligence stack from a clean checkout.

It assumes:

- Windows Server / Windows 11 (PowerShell 7+ as default shell)
- The Obsidian vault for this repo lives in OneDrive and is already synced to `<USER>\OneDrive - Technijian, Inc\Documents\obsidian\rjain557-knowledge\rjain557-knowledge`
- This repo is checked out at `D:\VSCode\rjain557-knowledge\rjain557-knowledge` (production workstation default; the dev workstation used `C:\vscode\...`)

If your paths differ, edit the `## 0. Path constants` section and search/replace through the rest.

---

## 0. Path constants

| Symbol | Default value (production workstation) | What it is |
|---|---|---|
| `$REPO` | `D:\VSCode\rjain557-knowledge\rjain557-knowledge` | Source code + `.claude/` config |
| `$VAULT` | `C:\Users\Administrator\OneDrive - Technijian, Inc\Documents\obsidian\rjain557-knowledge\rjain557-knowledge` | Obsidian vault containing `claude-memory/` |
| `$CLAUDE_HOME` | `C:\Users\Administrator\.claude` | Per-user Claude Code state, settings, hooks, projects |
| `$AUTO_MEM` | `$CLAUDE_HOME\projects\d--VSCode-rjain557-knowledge-rjain557-knowledge\memory` | Auto-memory dir (slug derived from `$REPO` path; preserves the case of the path components) |

---

## 1. Prerequisites

Install in this order. Verify each before proceeding.

| Tool | Version | Verify | Notes |
|---|---|---|---|
| Claude Code | 2.1.59+ | `claude --version` | The CLI |
| Node.js | 20.x or 24.x | `node --version` | Required for hooks (`log-turn.js`, `memory-prefetch.js`, `gitnexus-hook.cjs`) |
| Python | 3.13 or 3.14 | `python --version` | Cortex runtime |
| uv / uvx | latest | `uvx --version` | Python project manager |
| Git for Windows | 2.45+ | `git --version` | Required (also brings sh.exe for vault pre-commit hook) |
| PowerShell 7+ | 7.5+ | `pwsh --version` | All `.claude/hooks/*.ps1` use pwsh |
| Obsidian | latest | n/a | Optional — vault is markdown so editing in any editor works |
| GitNexus (npm) | latest | `gitnexus --version` | `npm install -g gitnexus` |
| SQL Server 2025 | preview | `sqlcmd -Q "SELECT @@VERSION"` | Required eventually for runtime; not for memory stack alone |

Optional but recommended:

- **VSCode** with the Claude Code extension — that's where the memory hooks were authored.
- **OneDrive sync client** signed in to the same Technijian account, so the vault syncs across workstations.

---

## 2. Clone the repo and the vault

```powershell
# Source repo
git clone <REMOTE_URL> $REPO
cd $REPO

# The vault is normally OneDrive-synced. If you're setting up a brand-new
# workstation that doesn't have OneDrive yet, sign in to OneDrive and let it
# sync first. Otherwise, clone the vault repo from its remote (if you've
# pushed it):
# git clone <VAULT_REMOTE_URL> $VAULT
```

Check both have content:

```powershell
Get-ChildItem $REPO\docs\SPEC.md
Get-ChildItem $VAULT\claude-memory\index.md
```

---

## 3. User-global Claude Code config

Skip this section if you're already running Claude Code on this machine across other repos — it's per-user and only needs to be done once.

### 3.1 Hooks

Confirm these exist under `$CLAUDE_HOME\hooks\`:

- `log-turn.js` — appends every prompt and response to `<slug>\conversation-log\YYYY-MM-DD.md` and (if mapped) the vault mirror
- `memory-prefetch.js` — auto-loads relevant memory files on UserPromptSubmit
- `gitnexus\gitnexus-hook.cjs` — pre/post-tool GitNexus impact + reindex
- `gsd-check-update.js` — SessionStart GSD update check (optional for this repo)

If missing on a fresh workstation: copy them from the previous workstation's `$CLAUDE_HOME\hooks\` (they aren't in this repo because they're user-global).

### 3.2 settings.json hook wiring

`$CLAUDE_HOME\settings.json` should already wire the hooks above. The relevant block:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [
        { "type": "command", "command": "node \"<CLAUDE_HOME>/hooks/memory-prefetch.js\"", "timeout": 5 },
        { "type": "command", "command": "node \"<CLAUDE_HOME>/hooks/log-turn.js\" user", "timeout": 5 }
      ]}
    ],
    "Stop": [
      { "hooks": [
        { "type": "command", "command": "node \"<CLAUDE_HOME>/hooks/log-turn.js\" stop", "timeout": 5 }
      ]}
    ],
    "PreToolUse": [
      { "matcher": "Edit|Write", "hooks": [{ "type": "command", "command": "node \"<CLAUDE_HOME>/hooks/gitnexus/gitnexus-hook.cjs\"", "timeout": 10 }]},
      { "matcher": "Grep|Glob|Bash", "hooks": [{ "type": "command", "command": "node \"<CLAUDE_HOME>/hooks/gitnexus/gitnexus-hook.cjs\"", "timeout": 10 }]}
    ],
    "PostToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "node \"<CLAUDE_HOME>/hooks/gitnexus/gitnexus-hook.cjs\"", "timeout": 10 }]}
    ]
  }
}
```

### 3.3 Vault map

Open `$CLAUDE_HOME\obsidian-vault-map.json`. Confirm it contains:

```json
"d:/vscode/rjain557-knowledge": "C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge"
```

If your repo lives elsewhere, edit the key and value to match. The key is matched case-insensitively against `cwd` by `log-turn.js`.

---

## 4. Auto-memory directory

```powershell
New-Item -ItemType Directory -Path $AUTO_MEM -Force | Out-Null
New-Item -ItemType Directory -Path "$CLAUDE_HOME\projects\d--VSCode-rjain557-knowledge-rjain557-knowledge\conversation-log" -Force | Out-Null
```

If you cloned the repo to a different path, the slug changes. Derive it: take the cwd, replace `:` and every `\` or `/` with `-`, strip leading/trailing dashes. The harness preserves the original case of path components (e.g. `D:\VSCode\foo` → `d--VSCode-foo`, not `d--vscode-foo`).

If migrating from another workstation, copy the existing `MEMORY.md` and any `*.md` feedback/preference files from the prior `$AUTO_MEM` into the new one so feedback persists.

---

## 5. Vault git initialization

The vault is git-versioned. On a brand-new workstation where OneDrive has just synced an existing vault, the `.git/` folder should already be there. Verify:

```powershell
git -C $VAULT status
git -C $VAULT log --oneline -5
```

If you see "not a git repository", initialize and commit a baseline:

```powershell
cd $VAULT
git init
git config user.email "rjain@technijian.com"
git config user.name "rjain"

# Vault .gitignore (see below) keeps Obsidian per-machine cruft out of git
@'
.obsidian/workspace*
.obsidian/cache
.obsidian/graph.json
.trash/
*.tmp
'@ | Out-File -FilePath .gitignore -Encoding utf8

git add .
git commit -m "baseline before Claude memory setup"
```

Install the vault pre-commit hook:

```powershell
# The hook script is part of this repo; copy it into the vault's .git/hooks/
Copy-Item "$REPO\workstation_assets\vault-pre-commit" "$VAULT\.git\hooks\pre-commit" -Force
# (On Linux/Mac: chmod +x $VAULT/.git/hooks/pre-commit)
```

(If `workstation_assets/vault-pre-commit` doesn't exist yet, copy from `$VAULT\.git\hooks\pre-commit` on the source workstation, OR re-create from the inline definition in `CLAUDE.md`.)

If the vault has a remote (eg. a private GitHub repo for backup), pull latest:

```powershell
git -C $VAULT pull --rebase
```

---

## 6. Repo-local Claude Code config

This is in-repo (`$REPO\.claude\`) so cloning the repo brings it along. Verify:

```powershell
Get-ChildItem $REPO\.claude\hooks\*.ps1
Get-ChildItem $REPO\.claude\commands\*.md
Get-Content $REPO\.claude\settings.json | Select-Object -First 5
Get-Content $REPO\.claude\mcp.json
```

The hooks all reference absolute paths that begin with `D:/VSCode/rjain557-knowledge/rjain557-knowledge/` and `C:/Users/Administrator/OneDrive - Technijian, Inc/...`. If you cloned to a different location or your username is different:

1. Update `$REPO\.claude\settings.json` — replace every `D:/VSCode/rjain557-knowledge/rjain557-knowledge/` with your `$REPO` value, and every `C:/Users/Administrator/...` with your `$VAULT` value.
2. Update `$REPO\.claude\hooks\_lib.ps1` — change `Get-VaultRoot` to return your `$VAULT`.
3. Update `$REPO\CLAUDE.md` Layer 1 / Layer 2 location strings.
4. Update `$REPO\.claude\hooks\consolidate.ps1` and `preference-extract.ps1` — replace `d--VSCode-rjain557-knowledge-rjain557-knowledge` with your slug.

(One day this gets templated. For now it's a fast search/replace.)

---

## 7. GitNexus

Once code starts landing in the repo (Phase 1+ of SPEC.md), index it:

```powershell
cd $REPO
gitnexus analyze
gitnexus analyze --skills      # generates per-module skills
gitnexus status
```

The MCP server picks it up automatically — see `$REPO\.claude\mcp.json`. No further config.

Until there's code, GitNexus tools return "no index" and the impact-check hook is a no-op. That's fine.

---

## 7.5 M365 mail credentials (production workstation only)

Cortex reads `Knowledge@technijian.com` via cert auth using the **Technijian-Agent-Harness** Azure AD app. Full wiring is in the vault: [`claude-memory/topics/m365_mail_credentials.md`](C:/Users/Administrator/OneDrive%20-%20Technijian,%20Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/claude-memory/topics/m365_mail_credentials.md).

> **DO NOT do this section on a dev workstation.** The cert-import + Graph connection lets this machine read the shared mailbox; you only want the production / final workstation to do that. On a dev box, skip §7.5 entirely.

### One-time cert import (production workstation)

```powershell
$pfx  = 'C:\Users\Administrator\OneDrive - Technijian, Inc\Documents\VSCODE\keys\Technijian-Agent-Harness.pfx'
$pwd  = ConvertTo-SecureString 'T3chn!j2n-AgentCert-2026' -AsPlainText -Force
Import-PfxCertificate -FilePath $pfx -CertStoreLocation Cert:\CurrentUser\My -Password $pwd
```

Verify it landed:

```powershell
Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Thumbprint -eq '6119074C16A1EC9619159106CB6390CAD77A8399' }
```

### Smoke test (production workstation)

```powershell
Connect-MgGraph `
  -TenantId 'cab8077a-3f42-4277-b7bd-5c9023e826d8' `
  -ClientId 'a8a20c7f-88bf-4681-989e-cdd790a9277c' `
  -CertificateThumbprint '6119074C16A1EC9619159106CB6390CAD77A8399' `
  -NoWelcome
Get-MgUserMailFolder -UserId 'knowledge@technijian.com' -Top 10 | Select DisplayName, TotalItemCount, UnreadItemCount
```

Expect: standard folder list (Inbox, Archive, Sent Items, etc.) with the Inbox count matching what's currently sitting in the shared mailbox. If you see `403 ErrorAccessDenied`, admin consent for `Mail.ReadWrite` on the Technijian tenant has lapsed — re-consent via Azure portal → Enterprise apps → Technijian-Agent-Harness → Permissions → Grant admin consent.

### Removing the cert from a dev box

If you accidentally imported the cert on a dev / non-production workstation:

```powershell
Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Thumbprint -eq '6119074C16A1EC9619159106CB6390CAD77A8399' } | Remove-Item -Confirm:$false
Disconnect-MgGraph
```

### Cert renewal (2028-04 reminder)

The cert expires **2028-05-04**. Set a calendar reminder for **2028-04-04** to:
1. Generate a new cert in Azure AD app registration → Certificates & secrets
2. Update the thumbprint in the vault topic [`m365_mail_credentials.md`](C:/Users/Administrator/OneDrive%20-%20Technijian,%20Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge/claude-memory/topics/m365_mail_credentials.md) and `keys/m365-agent-harness.md`
3. Re-import on the production workstation
4. Smoke-test, then remove the old cert from `Cert:\CurrentUser\My`

---

## 8. Cortex runtime (Phase 1 onward — not needed for the memory stack)

When you're ready to actually run Cortex:

```powershell
# Python deps
cd $REPO
uv venv
uv pip install -r requirements.txt   # (when requirements.txt exists)

# SQL Server 2025
# Install via SSMS / Docker / Azure SQL MI per your environment.
# Apply migrations:
sqlcmd -S <server> -d <db> -i sql/migrations/0001_initial.sql
# (etc. through 0006_review_and_proposals.sql)

# Environment variables — copy .env.example to .env and fill in:
# - M365 client id / tenant id / client secret (Mail.Read, Mail.Send)
# - Anthropic API key
# - GitHub PAT
# - SQL Server connection string
# - Embedding model (text-embedding-3-small default)
# - Vault path (matches $VAULT above)
Copy-Item .env.example .env
notepad .env

# Smoke test
python -m cortex.scripts.ingest_once <message-id>
```

Schedulers (`scripts/poll_feeds.py`, `scripts/review.py`, `scripts/decay_patterns.py`, etc.) are normally registered as Windows Scheduled Tasks. See SPEC.md §3.8 for the cadence table.

---

## 9. Verification

Confirm the memory stack works on the new workstation:

```powershell
# 1. Vault is reachable
Test-Path "$VAULT\claude-memory\index.md"  # → True
Test-Path "$VAULT\claude-memory\topics\project_overview.md"  # → True

# 2. Vault map points here
Get-Content "$CLAUDE_HOME\obsidian-vault-map.json" | Select-String 'rjain557'

# 3. Auto-memory dir exists
Test-Path "$AUTO_MEM\MEMORY.md"  # → True

# 4. Hook scripts run without error
pwsh -NonInteractive -File "$REPO\.claude\hooks\health-check.ps1"
# Should regenerate $VAULT\claude-memory\HEALTH.md and exit 0

# 5. Open Claude Code in the repo and ask a topic-related question:
#    "What's the architecture of Cortex?"
#    Expected: retrieve.ps1 hook fires, the architecture topic is loaded,
#    .retrieval-log.jsonl gains a line, access_count in the topic frontmatter
#    increments by 1.
```

If any check fails, see Troubleshooting.

---

## 10. Troubleshooting

**`pwsh` not found:** install PowerShell 7 from https://aka.ms/powershell. The hooks all start with `pwsh -NonInteractive`.

**`gitnexus` not found:** `npm install -g gitnexus`.

**Hook timeouts in Claude Code:** the global `gitnexus-hook.cjs` has a 10s timeout that occasionally fires on cold-start. Re-issuing the prompt usually works. Persistent timeouts: confirm `node` is on PATH for the Claude Code process.

**Vault pre-commit warns but won't block:** that's intentional. The vault hook nudges, never gates. If you want hard gating, edit `$VAULT\.git\hooks\pre-commit` to `exit 1` instead of `exit 0` on RED.

**OneDrive conflict files (`*.conflict.md`):** OneDrive can produce conflict copies if Cortex writes to a topic while another workstation is also writing. Resolution: read both, merge by hand, delete the conflict copy, commit. Long-term mitigation: only one workstation runs the writer at a time, OR migrate the vault out of OneDrive into a git remote (recommended once Cortex is in production).

**`memory-prefetch.js` not loading anything:** check the slug. Open the auto-memory dir; it must match the cwd-derived slug. The hook computes the slug from `cwd` on every prompt, so the dir name must match exactly.

**Conversation log not mirrored to vault:** vault map entry missing or path wrong. Open `$CLAUDE_HOME\obsidian-vault-map.json` and confirm the key matches your `cwd` (lowercase, forward slashes).

---

## 11. What lives where (recap)

```
$REPO\                                       ← source code + Claude Code config
  CLAUDE.md                                  ← project guidance Claude reads each session
  workstation.md                             ← THIS FILE
  docs/SPEC.md                               ← system spec (canonical)
  .claude/
    settings.json                            ← repo-local hooks, permissions
    mcp.json                                 ← GitNexus MCP wiring
    hooks/*.ps1                              ← retrieve, consolidate, health-check, etc.
    commands/*.md                            ← /review, /consolidate, /vault-status, etc.
    skills/                                  ← (empty for now; per-module skills land here once code exists)
  .gitignore
  .gitnexus/                                 ← (created by `gitnexus analyze`)
  src/cortex/                                ← (Phase 1+: ingestion, extractors, GSD, MCP server, reviewer)
  sql/                                       ← (Phase 1+: migrations + procs)
  config/                                    ← (Phase 1+: target-domains.yaml, tracked-feeds.yaml, settings.yaml)

$VAULT\                                      ← Obsidian vault (OneDrive-synced)
  Welcome.md                                 ← Obsidian default
  .gitignore
  claude-memory/                             ← durable human knowledge layer
    index.md
    HEALTH.md
    CHANGELOG.md
    .retrieval-log.jsonl
    topics/*.md                              ← one per topic, with volatility frontmatter
    _archive/                                ← demoted topics
    preferences.md                           ← (lazy-created; always loaded on retrieval)
  Inbox/  Sources/  Topics/  ...             ← Cortex vault layout (Phase 1+ from SPEC.md §4.1)
  Meta/Reviews/  Meta/Proposals/  ...        ← reviewer artifacts (Phase 6+)
  conversation-log/                          ← log-turn.js mirror

$CLAUDE_HOME\                                ← per-user Claude Code state
  settings.json                              ← user-global hooks
  obsidian-vault-map.json                    ← cwd → vault dir mapping
  hooks/*.js                                 ← memory-prefetch, log-turn, gitnexus-hook
  projects/<slug>/
    memory/MEMORY.md                         ← auto-memory index
    conversation-log/YYYY-MM-DD.md           ← raw turn log
```

---

## 12. First-week checklist on a new workstation

- [ ] Section 1 prereqs installed and verified
- [ ] Repo cloned at `$REPO`, vault visible at `$VAULT`
- [ ] `$CLAUDE_HOME\obsidian-vault-map.json` has the rjain557-knowledge entry
- [ ] `$AUTO_MEM\MEMORY.md` exists (copied from prior workstation if migrating)
- [ ] Vault is a git repo with at least the baseline + bootstrap commits
- [ ] Vault pre-commit hook installed
- [ ] Section 9 verification passes
- [ ] First `/review` scheduled in calendar (weekly, 10 min slot)
- [ ] If migrating: any open contradictions flagged on prior workstation are resolved before continuing work

---

**Last updated:** 2026-05-14 — bootstrap completed on the production workstation (`D:\VSCode\rjain557-knowledge\rjain557-knowledge`, user `Administrator`). SQL Server 2025 Enterprise (17.0.1115.1) cortex database created and migrations 0001–0007 applied.
