<#
.SYNOPSIS
    Keep this machine awake for the duration of a long run.

.DESCRIPTION
    Calls SetThreadExecutionState with ES_CONTINUOUS, which tells Windows that
    the calling THREAD needs the system to stay up. The flag lives exactly as
    long as this process does, so closing the window or Ctrl-C-ing it restores
    normal power behaviour immediately -- there is no global setting to undo and
    no administrator rights involved (unlike powercfg /requestsoverride).

    This is deliberately not a key-pressing loop: synthetic input steals focus,
    lands keystrokes in whatever window happens to be active, and does nothing
    about a scheduled sleep the OS has already decided on.

.PARAMETER SystemOnly
    Keep the system awake but let the display sleep. Preferred for headless
    overnight runs; the default also holds the display on, which is what you
    want when you are watching progress.

.PARAMETER LogPath
    Heartbeat file, so a detached run can be checked without attaching to it.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File u2_2d/scripts/keep_awake.ps1
    powershell -ExecutionPolicy Bypass -File u2_2d/scripts/keep_awake.ps1 -SystemOnly
#>
[CmdletBinding()]
param(
    [switch]$SystemOnly,
    [string]$LogPath = "out/u2_2d/keep_awake.log",
    [int]$HeartbeatSeconds = 300
)

Add-Type -Name PowerState -Namespace Win32Native -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

$ES_CONTINUOUS       = [uint32]"0x80000000"
$ES_SYSTEM_REQUIRED  = [uint32]"0x00000001"
$ES_DISPLAY_REQUIRED = [uint32]"0x00000002"

$flags = $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED
if (-not $SystemOnly) { $flags = $flags -bor $ES_DISPLAY_REQUIRED }

$previous = [Win32Native.PowerState]::SetThreadExecutionState($flags)
if ($previous -eq 0) {
    Write-Error "SetThreadExecutionState failed (error $([System.Runtime.InteropServices.Marshal]::GetLastWin32Error()))"
    exit 1
}

$logDir = Split-Path -Parent $LogPath
if ($logDir -and -not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

$mode = if ($SystemOnly) { "system" } else { "system + display" }
$start = Get-Date
$banner = "[$($start.ToString('yyyy-MM-dd HH:mm:ss'))] keep_awake started (pid $PID, holding: $mode)"
Write-Host $banner
Write-Host "Stop it with Ctrl-C or by killing pid $PID; the hold is released automatically."
Add-Content -Path $LogPath -Value $banner -Encoding utf8

try {
    while ($true) {
        Start-Sleep -Seconds $HeartbeatSeconds
        # Re-assert rather than trust the first call: a driver or another process
        # clearing its own ES_CONTINUOUS has been seen to drop the hold.
        [void][Win32Native.PowerState]::SetThreadExecutionState($flags)
        $elapsed = (Get-Date) - $start
        Add-Content -Path $LogPath -Encoding utf8 -Value (
            "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] awake, elapsed " +
            "{0:hh\:mm\:ss}" -f $elapsed)
    }
}
finally {
    [void][Win32Native.PowerState]::SetThreadExecutionState($ES_CONTINUOUS)
    $msg = "[$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))] keep_awake released the hold"
    Write-Host $msg
    Add-Content -Path $LogPath -Value $msg -Encoding utf8
}
