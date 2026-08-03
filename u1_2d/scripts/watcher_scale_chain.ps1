# Crash watcher for the scale chain. Polls every 2 minutes:
#   * chain finished (CHAIN_DONE)      -> remove startup entry, exit
#   * chain failed   (CHAIN_FAILED)    -> real stage error: do NOT relaunch, exit
#   * chain process gone (crash/kill)  -> relaunch (sentinels resume progress);
#       at 6 threads (safe mode) if any critical system event (kernel-power 41,
#       bugcheck 1001, unexpected shutdown 6008) appeared since lookback,
#       else at the standard 8 threads
#   * relaunch cap 5 (a crashloop means something a watcher should not fight)
# A Startup-folder entry re-arms this watcher after a reboot; the watcher
# deletes that entry when the chain completes. No priority elevation, no
# EcoQoS changes -- relaunching is the only intervention.

$repo = "C:\Users\ompan\OneDrive\Desktop\Lattice QCD Research\dev\InverseRG"
$log = Join-Path $repo "out\u1_2d\ess_chain\scale_chain.log"
$wlog = Join-Path $repo "out\u1_2d\ess_chain\watcher.log"
$startupEntry = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup\InverseRG_scale_watcher.cmd"
$lookback = (Get-Date).AddHours(-1)
$relaunches = 0

function WLog($m) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Add-Content -Path $wlog -Encoding utf8
}

# Duplicate guard via pidfile -- command-line matching is unusable here (any
# shell command merely MENTIONING this script's name would count as a twin).
$pidfile = Join-Path $repo "out\u1_2d\ess_chain\watcher.pid"
if (Test-Path $pidfile) {
    $old = 0
    try { $old = [int](Get-Content $pidfile -ErrorAction Stop) } catch {}
    $oldProc = if ($old) { Get-Process -Id $old -ErrorAction SilentlyContinue } else { $null }
    if ($oldProc -and $oldProc.ProcessName -match 'powershell') {
        WLog "another watcher (pid $old) is running; exiting pid $PID"
        exit
    }
}
Set-Content -Path $pidfile -Value $PID -Encoding ascii

WLog "watcher started (pid $PID, lookback $lookback)"

while ($true) {
    $content = ""
    try { $content = Get-Content $log -Raw -ErrorAction Stop } catch {}
    if ($content -match "CHAIN_DONE") {
        WLog "CHAIN_DONE seen; removing startup entry and exiting"
        try { Remove-Item $startupEntry -Force -ErrorAction Stop } catch {}
        break
    }
    if ($content -match "CHAIN_FAILED") {
        WLog "CHAIN_FAILED seen (real stage error, rc != 0); not relaunching -- inspect scale_chain.log"
        break
    }

    $alive = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match 'run_scale_chain' }
    if (-not $alive) {
        $bad = @()
        try {
            $bad = Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1001,6008; StartTime=$lookback} -ErrorAction Stop
        } catch {}
        if ($relaunches -ge 5) { WLog "relaunch cap (5) reached; exiting -- inspect logs"; break }
        $relaunches++
        if ($bad) {
            WLog "chain process gone AND $($bad.Count) critical system event(s) since $lookback -> SAFE relaunch #$relaunches (6 threads)"
            Start-Process -FilePath (Join-Path $repo "u1_2d\scripts\launch_scale_chain_safe.cmd") -WindowStyle Hidden
        } else {
            WLog "chain process gone (no critical events) -> relaunch #$relaunches (8 threads)"
            Start-Process -FilePath (Join-Path $repo "u1_2d\scripts\launch_scale_chain.cmd") -WindowStyle Hidden
        }
        Start-Sleep -Seconds 60
    }
    Start-Sleep -Seconds 120
}

try { Remove-Item $pidfile -Force -ErrorAction Stop } catch {}
WLog "watcher exited (pid $PID)"
