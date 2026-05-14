# UserPromptSubmit hook: retrieve relevant vault topics + always load preferences.
#
# Triggers retrieval on topic / entity matches in the prompt. Skips on trivial /
# off-topic prompts. Updates frontmatter access_count + last_accessed and appends
# a JSONL line to .retrieval-log.jsonl. Always loads preferences.md (universal).

. "$PSScriptRoot/_lib.ps1"

try {
    $payload = Read-StdinJson
    $cwd = $payload.cwd
    $prompt = ($payload.prompt | ForEach-Object { $_.ToString().ToLower() })
    if ([string]::IsNullOrWhiteSpace($prompt)) { exit 0 }

    # Only run when invoked from the rjain557-knowledge repo
    if ($cwd -and ($cwd -notlike '*rjain557-knowledge*')) { exit 0 }

    $topicsDir = Get-TopicsDir
    if (-not (Test-Path $topicsDir)) { exit 0 }

    $stopWords = @('the','and','for','are','but','not','you','all','can','had',
                   'her','was','one','our','out','has','have','been','from',
                   'this','that','with','they','will','what','when','make',
                   'like','just','also','into','them','then','than','some',
                   'could','would','should','about','which','their','there',
                   'these','those','being','does','doing','done','please',
                   'update','create','send','check','review','look','need',
                   'want','help','show','tell','find','get','use','how')

    $keywords = $prompt -replace '[^a-z0-9@.\-_]', ' ' -split '\s+' |
                Where-Object { $_.Length -ge 3 -and ($stopWords -notcontains $_) } |
                Select-Object -Unique
    if ($keywords.Count -eq 0) { exit 0 }

    # Load preferences if present (always)
    $prefsPath = Get-PreferencesPath
    $prefsContent = ''
    if (Test-Path $prefsPath) {
        $prefsContent = Get-Content $prefsPath -Raw
    }

    # Score topics by keyword hits in topic name + aliases + summary
    $topicFiles = Get-ChildItem $topicsDir -Filter '*.md' -ErrorAction SilentlyContinue
    $scored = @()
    foreach ($f in $topicFiles) {
        $body = (Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue).ToLower()
        if (-not $body) { continue }
        $score = 0
        foreach ($kw in $keywords) {
            $matches = ([regex]::Matches($body, [regex]::Escape($kw))).Count
            $score += $matches
        }
        if ($score -gt 0) {
            $scored += [pscustomobject]@{ Path = $f.FullName; Name = $f.BaseName; Score = $score }
        }
    }

    $top = $scored | Sort-Object Score -Descending | Select-Object -First 4
    if ($top.Count -eq 0 -and -not $prefsContent) { exit 0 }

    # Bump frontmatter counters + log retrieval
    $today = (Get-Date -Format 'yyyy-MM-dd')
    $logPath = Get-LogPath
    foreach ($t in $top) {
        $body = Get-Content $t.Path -Raw
        $body = [regex]::Replace($body, '(?m)^access_count:\s*(\d+)', {
            param($m); $n = [int]$m.Groups[1].Value + 1; "access_count: $n"
        })
        $body = $body -replace '(?m)^last_accessed:\s*\S+', "last_accessed: $today"
        Set-Content -Path $t.Path -Value $body -Encoding UTF8 -NoNewline

        $logLine = @{
            ts = (Get-Date -Format 'o')
            topic = $t.Name
            score = $t.Score
            keywords = $keywords
        } | ConvertTo-Json -Compress
        Add-Content -Path $logPath -Value $logLine -Encoding UTF8
    }

    # Emit context for Claude to read
    $sb = New-Object System.Text.StringBuilder
    $null = $sb.AppendLine('<vault-retrieval>')
    if ($prefsContent) {
        $null = $sb.AppendLine('## Preferences (always loaded)')
        $null = $sb.AppendLine($prefsContent)
        $null = $sb.AppendLine('---')
    }
    foreach ($t in $top) {
        $null = $sb.AppendLine("## Topic: $($t.Name) (score=$($t.Score))")
        $null = $sb.AppendLine((Get-Content $t.Path -Raw))
        $null = $sb.AppendLine('---')
    }
    $null = $sb.AppendLine('</vault-retrieval>')

    # Write to stdout — Claude Code injects this as context
    Write-Output $sb.ToString()
    exit 0
} catch {
    # Never block on hook failure
    exit 0
}
