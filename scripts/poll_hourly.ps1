# Cortex hourly mail poller — invoked by Windows Task Scheduler.
# Runs `scripts/poll.py --once`, captures all output to a daily log file,
# and exits non-zero on failure (so Task Scheduler marks the run as failed).

$ErrorActionPreference = 'Stop'
$repo = 'D:\VSCode\rjain557-knowledge\rjain557-knowledge'
Set-Location $repo

# Need ffmpeg (system PATH), uv (.local\bin), and the project venv on PATH.
$machinePath = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
$userPath    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
$env:Path = "$machinePath;$userPath;C:\Users\Administrator\.local\bin"
$env:PYTHONIOENCODING = 'utf-8'

# Log dir + daily rotated log file
$logDir = Join-Path $repo 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("poll-{0:yyyy-MM-dd}.log" -f (Get-Date))

$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
"===== $timestamp poll cycle start =====" | Add-Content $logFile

try {
    & .\.venv\Scripts\python.exe scripts\poll.py --once *>&1 | Tee-Object -FilePath $logFile -Append
    $exit = $LASTEXITCODE
    "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') poll cycle done (exit=$exit) =====" | Add-Content $logFile
    exit $exit
} catch {
    "===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') poll cycle FAILED: $_ =====" | Add-Content $logFile
    exit 1
}
