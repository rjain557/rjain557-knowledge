# PostToolUse hook for Bash: when a git commit/merge happens in this repo,
# trigger a GitNexus re-index. Defers to the global gitnexus-hook.cjs which
# already implements freshness checks. This script is a marker so the repo
# can opt into deeper / per-repo logic later.

. "$PSScriptRoot/_lib.ps1"

try {
    $payload = Read-StdinJson
    $command = $payload.tool_input.command
    if (-not $command) { exit 0 }
    if ($command -notmatch '\bgit\b\s+(commit|merge|pull|rebase)') { exit 0 }

    $repoRoot = 'c:/vscode/rjain557-knowledge/rjain557-knowledge'
    $gn = Join-Path $repoRoot '.gitnexus'

    # If the repo has been GitNexus-indexed, rely on the global hook to re-index.
    # If not (Phase 1 — no code yet), nothing to do.
    if (-not (Test-Path $gn)) { exit 0 }

    # Fire-and-forget hint to the user
    Write-Output '<gitnexus-hint>Repo touched git; GitNexus will re-index on next read.</gitnexus-hint>'
    exit 0
} catch {
    exit 0
}
