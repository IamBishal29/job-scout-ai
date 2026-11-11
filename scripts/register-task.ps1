# Register (or update) a daily Windows Task Scheduler task for JobPilot.
# Runs only while you are logged in; no admin rights or stored password needed.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 [-At 08:00]
# Remove: Unregister-ScheduledTask -TaskName JobPilotDaily -Confirm:$false
param(
    [string]$At = "08:00",
    [string]$TaskName = "JobPilotDaily"
)

$ErrorActionPreference = "Stop"
$script = Join-Path $PSScriptRoot "daily.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# StartWhenAvailable: if the PC was off/asleep at $At, run as soon as it is back.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "JobPilot: fetch, score and email new job matches" -Force |
    Out-Null

Write-Host "Registered '$TaskName' daily at $At. Test now with:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
