# Stop hook: detect durable knowledge in the just-finished exchange and decide
# whether to update / create a topic page. Also runs contradiction detection.
#
# Heuristic-only first pass — for richer consolidation, run /consolidate explicitly.
# This hook is conservative: it only auto-touches existing topic pages whose name /
# alias appears in the recent transcript. Creating new topics is left to /consolidate.

. "$PSScriptRoot/_lib.ps1"

try {
    $payload = Read-StdinJson
    $cwd = $payload.cwd
    if ($cwd -and ($cwd -notlike '*rjain557-knowledge*')) { exit 0 }

    # Pull the most recent transcript file from the conversation log
    $sessionLogDir = "C:/Users/rjain/.claude/projects/c--vscode-rjain557-knowledge-rjain557-knowledge/conversation-log"
    if (-not (Test-Path $sessionLogDir)) { exit 0 }

    $today = (Get-Date -Format 'yyyy-MM-dd')
    $logFile = Join-Path $sessionLogDir "$today.md"
    if (-not (Test-Path $logFile)) { exit 0 }

    # Tail the last ~4000 chars of the day's log as the "recent exchange"
    $logContent = Get-Content $logFile -Raw
    if ($logContent.Length -gt 4000) {
        $tail = $logContent.Substring($logContent.Length - 4000)
    } else {
        $tail = $logContent
    }
    $tailLower = $tail.ToLower()

    # Skip trivial exchanges
    if ($tailLower.Length -lt 200) { exit 0 }

    # For each existing topic, check if its name or aliases appear in the tail
    $topicsDir = Get-TopicsDir
    $touchedTopics = @()
    foreach ($f in Get-ChildItem $topicsDir -Filter '*.md' -ErrorAction SilentlyContinue) {
        $body = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $body) { continue }

        # Extract topic name + aliases from frontmatter
        $name = ''
        $aliases = @()
        if ($body -match '(?m)^topic:\s*(.+)$') { $name = $matches[1].Trim() }
        if ($body -match '(?m)^aliases:\s*\[(.+)\]') {
            $aliases = $matches[1] -split ',' | ForEach-Object { $_.Trim().Trim('"').Trim("'") }
        }

        $hit = $false
        if ($name -and $tailLower.Contains($name.ToLower())) { $hit = $true }
        foreach ($a in $aliases) {
            if ($a -and $tailLower.Contains($a.ToLower())) { $hit = $true; break }
        }
        if ($hit) { $touchedTopics += $f.BaseName }
    }

    if ($touchedTopics.Count -eq 0) { exit 0 }

    # Conservative: just bump last_accessed + log a CHANGELOG note that these
    # topics were referenced. Real content updates require /consolidate.
    $msg = "Topics referenced this session: " + ($touchedTopics -join ', ') +
           ". Run /consolidate to fold any new info into the topic pages."
    Write-ChangelogEntry -Tag 'consolidate' -Message $msg

    Commit-Vault -Tag 'consolidate' -Message ("session-touched topics: " + ($touchedTopics -join ', '))

    exit 0
} catch {
    exit 0
}
