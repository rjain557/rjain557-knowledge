# Stop hook helper: detect preference-shaped statements in the recent turn and
# offer to save them to preferences.md. This hook only flags candidates — it does
# not auto-write preferences (preferences should feel intentional).

. "$PSScriptRoot/_lib.ps1"

try {
    $payload = Read-StdinJson
    $cwd = $payload.cwd
    if ($cwd -and ($cwd -notlike '*rjain557-knowledge*')) { exit 0 }

    $sessionLogDir = "C:/Users/rjain/.claude/projects/c--vscode-rjain557-knowledge-rjain557-knowledge/conversation-log"
    $today = (Get-Date -Format 'yyyy-MM-dd')
    $logFile = Join-Path $sessionLogDir "$today.md"
    if (-not (Test-Path $logFile)) { exit 0 }

    $tail = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
    if (-not $tail) { exit 0 }
    if ($tail.Length -gt 4000) { $tail = $tail.Substring($tail.Length - 4000) }

    $patterns = @(
        '\bI prefer\b',
        '\bI like\b.*\bbetter\b',
        "\bdon’?t (do|use|write|run|call) ",
        '\balways (do|use|write|run|call) ',
        '\bnever (do|use|write|run|call) ',
        '\bfrom now on\b',
        '\bgoing forward\b',
        '\bplease (do|use|write|run|call) '
    )
    $matched = $false
    foreach ($p in $patterns) {
        if ($tail -imatch $p) { $matched = $true; break }
    }
    if (-not $matched) { exit 0 }

    Write-Output ('<preference-candidate>The recent exchange contains preference-shaped language. ' +
                  'If you intended to set a durable preference, run /preferences-save to add it to ' +
                  'claude-memory/preferences.md.</preference-candidate>')
    exit 0
} catch {
    exit 0
}
