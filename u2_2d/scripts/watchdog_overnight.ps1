# Overnight watchdog for all the coverage/volume-scan pipelines (u1 and u2).
# Runs every 15 minutes via a scheduled task with a repetition trigger, not
# as one long-lived loop -- a crash inside the watchdog itself then costs at
# most one missed check, not silent monitoring death for the rest of the
# night, which is the failure mode a "while(1){sleep}" script has and a
# repeating trigger does not.
#
# WHY THIS EXISTS: the CPU-training-too-slow problem earlier tonight was
# real progress (nothing crashed, no error anywhere) that was still a
# problem, and it was only caught because the user asked for a status
# update. This watches for exactly that shape of failure -- "running, not
# obviously broken, but not going to finish" -- in addition to actual
# crashes, and writes ONE human-readable status file so the answer to
# "status/eta" the next morning doesn't require re-deriving it from raw logs.
#
# WHAT IT DOES:
#   1. Reads every known log, extracts the latest epoch/coupling progress
#      and a rate (epochs or couplings per hour) from two samples spaced
#      across this and the previous run (state persisted to a small JSON
#      so rates survive across ticks).
#   2. STALL DETECTION: a task in "Running" state whose log has not grown
#      in > 25 minutes is flagged and the task is restarted once (Task
#      Scheduler's own RestartCount/RestartInterval, set on all these tasks
#      already, is the first line of defense for outright process death;
#      this catches a hang Task Scheduler cannot see because the process
#      is still alive, just stuck).
#   3. EXPLICIT-FAILURE DETECTION: a log containing "FAILED, exit" -- every
#      stage in every pipeline script writes this on a real error -- is
#      restarted, up to 3 total attempts tracked in the state file.
#      DELIBERATELY NOT what this used to check: "Ready" + no "PIPELINE
#      DONE" string very nearly caused real damage during testing tonight --
#      v2/cap had ALREADY finished successfully (14/14 both rounds) using
#      an OLDER version of their script that predated the "PIPELINE DONE"
#      line being added, so the watchdog read a genuinely complete run as a
#      silent failure and restarted it, which would have overwritten the
#      finished 14-coupling result with a fresh, in-progress one. Caught by
#      hand before it wrote anything. The fix is to never infer failure
#      from an ABSENT marker -- only ever act on a PRESENT, unambiguous one
#      (an explicit FAILED line, or the stall check below).
#   4. SLOW-RATE FLAGGING ONLY, NOT ACTION: if a training run's projected
#      time-to-completion exceeds 6 hours, that is logged as an ALERT but
#      NOTHING is changed automatically -- device/config edits are exactly
#      the kind of unattended change that should surface for a human
#      decision, not happen silently a second time.
#   5. Writes out\overnight_status.log, OVERWRITTEN each tick (latest
#      snapshot only) plus out\overnight_alerts.log, APPENDED (a
#      permanent record of anything the watchdog ever flagged).

Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$statusFile = "out\overnight_status.log"
$alertFile = "out\overnight_alerts.log"
$stateFile = "out\overnight_watchdog_state.json"

$tasks = @(
    # SUPERSEDED 2026-09-03: the old threshold-crossing t_therm definition
    # was replaced with the exponential relaxation-time fit
    # (28_crossover_scan.py's fit_relaxation_time), and everything under the
    # old out/u2_2d/coverage_scan/ and out/u2_2d/crossover/ was stopped and
    # is being fully re-run under the new definition into a fresh directory.
    # The single orchestrator below replaces all the old per-checkpoint
    # scheduled tasks (u2_cov60_pipeline, u2_cpu_coverage_pipeline,
    # u2_volume_scan_pipeline, u2_default_l64_extra, u2_cov30_l64_extra,
    # u2_coverage_scan_v2/cap) -- those are no longer monitored here.
    #
    # StallMinutes not needed at the default 30: the orchestrator writes its
    # own status line every --poll-seconds (20s) REGARDLESS of individual
    # coupling progress, so its log heartbeats continuously by construction
    # -- this structurally closes the "long legitimate wait looks like a
    # hang" false-stall class that hit the old per-checkpoint scripts twice
    # tonight (they only logged on coupling completion, up to ~35 min apart).
    @{ Name="u2_relaxation_matrix"; Log="out\u2_2d\coverage_scan_relaxation\orchestrator.log" },
    @{ Name="u2_widening_data_gen"; Log="out\u2_2d\data_widening_test\gen.log" },
    @{ Name="u1_wide250_pipeline"; Log="out\u1_2d\wide250_pipeline.log" }
)

# NOTE: this repo's PowerShell is 5.1, which has no ConvertFrom-Json
# -AsHashtable (that needs 6+) -- convert the parsed PSCustomObject by hand.
$state = @{}
if (Test-Path $stateFile) {
    try {
        $parsed = Get-Content $stateFile -Raw | ConvertFrom-Json
        foreach ($p in $parsed.PSObject.Properties) { $state[$p.Name] = $p.Value }
    } catch { $state = @{} }
}

function Get-LastEpochOrCoupling($logPath) {
    if (-not (Test-Path $logPath)) { return $null }
    # Read the tail only -- these logs can run to tens of MB by morning.
    $bytes = (Get-Item $logPath).Length
    $tail = if ($bytes -gt 200000) {
        $stream = [System.IO.File]::Open($logPath, 'Open', 'Read', 'ReadWrite')
        $stream.Seek(-200000, [System.IO.SeekOrigin]::End) | Out-Null
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::Unicode, $true)
        $txt = $reader.ReadToEnd(); $reader.Close(); $stream.Close(); $txt
    } else {
        Get-Content $logPath -Raw -Encoding Unicode
    }
    $epochMatches = [regex]::Matches($tail, "epoch\s+(\d+)")
    $couplingMatches = [regex]::Matches($tail, "b=\s*([\d.]+).*?\[(\d+)s\]")
    $jobMatches = [regex]::Matches($tail, "done:\s*(\d+)/(\d+)")
    if ($epochMatches.Count -gt 0) {
        return @{ kind = "epoch"; value = [int]$epochMatches[$epochMatches.Count - 1].Groups[1].Value }
    } elseif ($jobMatches.Count -gt 0) {
        $last = $jobMatches[$jobMatches.Count - 1]
        return @{ kind = "jobs done (of $($last.Groups[2].Value))"; value = [int]$last.Groups[1].Value }
    } elseif ($couplingMatches.Count -gt 0) {
        return @{ kind = "coupling"; value = $couplingMatches.Count }
    }
    return $null
}

$now = Get-Date
$statusLines = @("watchdog tick: $now")
$newState = @{}

foreach ($t in $tasks) {
    $name = $t.Name
    $logPath = $t.Log
    $taskObj = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $taskObj) {
        $statusLines += "$name : NOT REGISTERED"
        continue
    }
    $taskState = $taskObj.State
    $logExists = Test-Path $logPath
    $lastWrite = if ($logExists) { (Get-Item $logPath).LastWriteTime } else { $null }
    $ageMin = if ($lastWrite) { [Math]::Round(($now - $lastWrite).TotalMinutes, 1) } else { $null }
    $prog = if ($logExists) { Get-LastEpochOrCoupling $logPath } else { $null }

    # Rate from the persisted previous sample, if there is one.
    $rateStr = ""
    $key = $name
    if ($prog -and $state.ContainsKey($key)) {
        $prev = $state[$key]
        try {
            $prevTime = [datetime]$prev.time
            $dtHours = ($now - $prevTime).TotalHours
            if ($dtHours -gt 0.05 -and $prev.kind -eq $prog.kind -and $prog.value -ge $prev.value) {
                $rate = ($prog.value - $prev.value) / $dtHours
                $rateStr = " rate=$([Math]::Round($rate,2))/h"
                if ($prog.kind -eq "epoch" -and $rate -gt 0) {
                    $remaining = 120 - $prog.value
                    $etaH = [Math]::Round($remaining / $rate, 1)
                    $rateStr += " eta=~${etaH}h"
                    if ($etaH -gt 6) {
                        $msg = "$now ALERT [$name] projected ${etaH}h remaining (rate $([Math]::Round($rate,2)) epoch/h) -- NO ACTION TAKEN, flagging only"
                        $msg *>> $alertFile
                        $statusLines += "  !! $msg"
                    }
                }
            }
        } catch {}
    }
    if ($prog) {
        $newState[$key] = @{ time = $now.ToString("o"); kind = $prog.kind; value = $prog.value }
    } elseif ($state.ContainsKey($key)) {
        $newState[$key] = $state[$key]
    }

    $progStr = if ($prog) { "$($prog.kind)=$($prog.value)$rateStr" } else { "no progress markers yet" }
    $statusLines += "$name : $taskState  (log age ${ageMin}m)  $progStr"

    # Restart counters, bounded at 3 per task for the life of the state file.
    $restartKey = "${name}_restarts"
    $restarts = if ($state.ContainsKey($restartKey)) { [int]$state[$restartKey] } else { 0 }
    $newState[$restartKey] = $restarts

    # STALL: still Running, but no log growth in a long time -- these logs
    # print at least once per coupling (~3-6 min) or per epoch (well under
    # a minute on GPU), so 30 quiet minutes while "Running" is genuinely
    # anomalous, not just a slow-but-fine period.
    $stallThreshold = if ($t.ContainsKey("StallMinutes")) { $t.StallMinutes } else { 30 }
    $stalled = ($taskState -eq "Running") -and $ageMin -and ($ageMin -gt $stallThreshold)
    # EXPLICIT failure: the pipeline scripts print this exact string and
    # exit 1 on a real error. Never inferred from an absent marker -- see
    # the header note on why that was wrong. Also never inferred from a
    # STALE failure line either: a multi-stage pipeline (train -> scan ->
    # figure) can fail once, get manually or auto restarted, and succeed --
    # the old "FAILED" line is still sitting in the (appended) log forever
    # after that. Only counts if it is the MOST RECENT of {FAILED, a
    # completion/skip marker} in the file, i.e. nothing later says it
    # recovered.
    $explicitFail = $false
    if ($logExists) {
        $allLines = Get-Content $logPath -Encoding Unicode
        $lastFail = -1; $lastOk = -1
        for ($i = 0; $i -lt $allLines.Count; $i++) {
            if ($allLines[$i] -match "FAILED, exit") { $lastFail = $i }
            if ($allLines[$i] -match "PIPELINE DONE|already complete|already trained") { $lastOk = $i }
        }
        $explicitFail = ($lastFail -ge 0) -and ($lastFail -gt $lastOk)
    }

    if (($stalled -or $explicitFail) -and $restarts -lt 3) {
        $reason = if ($stalled) { "STALLED (no log growth in ${ageMin}m while Running)" } else { "explicit FAILED line in log" }
        $msg = "$now ALERT [$name] $reason -- restarting (attempt $($restarts+1)/3)"
        $msg *>> $alertFile
        $statusLines += "  !! $msg"
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
        Start-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        $newState[$restartKey] = $restarts + 1
    } elseif (($stalled -or $explicitFail) -and $restarts -ge 3) {
        $msg = "$now ALERT [$name] still unhealthy after 3 restart attempts -- giving up, needs a human"
        if (-not (Select-String -Path $alertFile -Pattern "\[$name\] still unhealthy" -Quiet -ErrorAction SilentlyContinue)) {
            $msg *>> $alertFile
        }
        $statusLines += "  !! $msg"
    }
}

$gpuJobs = (Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "02_train\.py|28_crossover_scan\.py|06_generalization_study\.py|01_generate_data\.py" } |
    Select-Object -ExpandProperty CommandLine -Unique).Count
$statusLines += "active GPU/CPU-bound jobs (distinct command lines): $gpuJobs"

# VALUE-level sanity check, not just process-liveness -- a task can be
# "Running" and heartbeating happily while writing physically impossible
# results (found for real 2026-09-03: a fitted tau of ~3980 trajectories
# against a 400-trajectory budget, caught only by a manual spot-check, not
# by anything automated). Runs every tick; only NEW anomalies alert, via its
# own seen-issues state file, so this does not spam the same finding every
# 15 minutes forever.
try {
    $sanityOut = & ".venv\Scripts\python.exe" "u2_2d\scripts\62_sanity_check_relaxation_results.py" 2>&1
    if ($LASTEXITCODE -eq 1) {
        $msg = "$now SANITY ALERT -- new anomaly in relaxation-matrix output:`n$($sanityOut -join "`n")"
        $msg *>> $alertFile
        $statusLines += "  !! $msg"
    }
} catch {}

$statusLines -join "`n" | Set-Content -Path $statusFile -Encoding utf8
$newState | ConvertTo-Json -Depth 5 | Set-Content -Path $stateFile -Encoding utf8
