# PreToolUse hook for Edit/Write: defer to global GitNexus impact check.
# This hook is a thin wrapper — the heavy lifting happens in the global
# gitnexus-hook.cjs. It exists so the repo can opt into the check explicitly
# and document the intent.

. "$PSScriptRoot/_lib.ps1"

try {
    # If GitNexus is not yet indexed for this repo, just no-op.
    $repoRoot = 'D:/VSCode/rjain557-knowledge/rjain557-knowledge'
    $gn = Join-Path $repoRoot '.gitnexus'
    if (-not (Test-Path $gn)) { exit 0 }

    # Otherwise the global hook handles the actual impact check.
    # Local hook is currently a no-op stub; flesh out only if global is bypassed.
    exit 0
} catch {
    exit 0
}
