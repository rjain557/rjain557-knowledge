# Shared helpers for rjain557-knowledge hooks.
# Dot-source from each hook: . "$PSScriptRoot/_lib.ps1"

$ErrorActionPreference = 'Stop'

function Get-VaultRoot {
    'C:/Users/Administrator/OneDrive - Technijian, Inc/Documents/obsidian/rjain557-knowledge/rjain557-knowledge'
}

function Get-MemoryRoot {
    Join-Path (Get-VaultRoot) 'claude-memory'
}

function Get-TopicsDir {
    Join-Path (Get-MemoryRoot) 'topics'
}

function Get-LogPath {
    Join-Path (Get-MemoryRoot) '.retrieval-log.jsonl'
}

function Get-IndexPath {
    Join-Path (Get-MemoryRoot) 'index.md'
}

function Get-ChangelogPath {
    Join-Path (Get-MemoryRoot) 'CHANGELOG.md'
}

function Get-HealthPath {
    Join-Path (Get-MemoryRoot) 'HEALTH.md'
}

function Get-PreferencesPath {
    Join-Path (Get-MemoryRoot) 'preferences.md'
}

function Read-StdinJson {
    $raw = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($raw)) { return @{} }
    try { return $raw | ConvertFrom-Json -AsHashtable } catch { return @{} }
}

function Write-ChangelogEntry {
    param([string]$Tag, [string]$Message)
    $today = (Get-Date -Format 'yyyy-MM-dd')
    $line = "- ``[$Tag]`` $Message"
    $changelog = Get-ChangelogPath
    if (-not (Test-Path $changelog)) { return }
    $current = Get-Content $changelog -Raw
    # Insert under today's date heading, or create one
    if ($current -match "## $today") {
        $updated = $current -replace "(## $today\r?\n)", "`$1$line`n"
    } else {
        # Insert after the `---` separator at the top
        $updated = $current -replace "(---\r?\n\r?\n)", "`$1## $today`n`n$line`n`n"
    }
    Set-Content -Path $changelog -Value $updated -Encoding UTF8 -NoNewline
}

function Invoke-VaultGit {
    param([string[]]$Args)
    $vault = Get-VaultRoot
    & git -C $vault @Args 2>&1 | Out-Null
}

function Get-VaultGitClean {
    $vault = Get-VaultRoot
    $status = & git -C $vault status --porcelain 2>$null
    return [string]::IsNullOrWhiteSpace($status)
}

function Commit-Vault {
    param([string]$Tag, [string]$Message)
    $vault = Get-VaultRoot
    & git -C $vault add 'claude-memory' 2>$null | Out-Null
    & git -C $vault diff --cached --quiet 2>$null
    if ($LASTEXITCODE -ne 0) {
        & git -C $vault commit -m "[$Tag] $Message" --no-verify 2>$null | Out-Null
    }
}
