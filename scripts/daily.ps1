# JobPilot daily run: fetch -> score -> digest. Called by Windows Task Scheduler.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\daily.ps1 [-Limit 20] [-DryRun] [-Config path]
param(
    [int]$Limit = 20,
    [switch]$DryRun,
    [string]$Config = "config.toml"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot          # scripts\.. = repo root
Set-Location $repo                                # config.toml, .env and data\ are relative

$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Virtual env not found at $python. Run setup from README.md first."
    exit 2
}

$logDir = Join-Path $repo "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("daily-{0:yyyy-MM-dd}.log" -f (Get-Date))

$cliArgs = @("-m", "jobpilot", "--config", $Config, "daily", "--limit", $Limit)
if ($DryRun) { $cliArgs += "--dry-run" }

$env:PYTHONIOENCODING = "utf-8"                   # job titles contain non-ASCII characters
"`n#### $(Get-Date -Format s) jobpilot daily" | Add-Content -Path $log -Encoding utf8
& $python @cliArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
exit $LASTEXITCODE                                # Task Scheduler shows this as "Last Run Result"
