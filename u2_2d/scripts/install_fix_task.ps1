# Register (or re-register) the detached scheduled task for the U(2) fix queue.
#
# Use the cmdlets, not `schtasks /TR`. The repo path contains a space
# ("Lattice QCD") and schtasks splits its /TR string on it, storing
# Execute = "C:\Users\...\Desktop\Lattice" -- which then fails at run time with
# 0x80070002 (ERROR_FILE_NOT_FOUND) and an empty log. Register-ScheduledTask
# takes Execute, Argument and WorkingDirectory as separate values, so there is
# nothing to split.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d\scripts\install_fix_task.ps1
#   schtasks /Run /TN U2FixQueue          (start it)
#   schtasks /End /TN U2FixQueue          (stop it)
#
# Battery settings are set explicitly: this is a laptop, and the Task Scheduler
# default is to refuse to start on battery and to kill a running task when the
# machine unplugs -- which shows up as a task stuck in "Queued".

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$script = Join-Path $repo "u2_2d\scripts\run_fixes.ps1"

if (-not (Test-Path $script)) { Write-Host "FATAL: no $script"; exit 1 }

$action = New-ScheduledTaskAction -Execute $ps `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $script + '"') `
    -WorkingDirectory $repo

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::FromHours(72)) `
    -StartWhenAvailable

Unregister-ScheduledTask -TaskName "U2FixQueue" -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName "U2FixQueue" -Action $action -Settings $settings `
    -Description "U(2) publication-gap fix queue" | Out-Null

$t = Get-ScheduledTask -TaskName "U2FixQueue"
Write-Host "registered U2FixQueue"
$t.Actions | Format-List Execute, Arguments, WorkingDirectory | Out-String | Write-Host
$t.Settings | Select-Object DisallowStartIfOnBatteries, StopIfGoingOnBatteries,
    ExecutionTimeLimit | Format-List | Out-String | Write-Host
