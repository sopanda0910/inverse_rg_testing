# Volume-scaling extension of the coverage-comparison work: runs the SAME
# cost-efficiency scan (28_crossover_scan.py via 58_training_coverage_scan.py)
# at L=64 for every coverage-ablation checkpoint, so 59's comparison figure
# can show the falloff-vs-coverage story at both volumes, not just L=32.
#
# SCOPED DOWN from 14 to 8 couplings per round (--n-couplings 8): L=64 is
# roughly as expensive per coupling as L=32 (GPU throughput is flat in L,
# CLAUDE.md), so an unscoped 14-coupling pass here would cost as much as
# everything already queued tonight, combined. 8 couplings still traces the
# curve shape; the log-uniform coupling selection in 28_crossover_scan.py
# picks a representative spread either way.
#
# PRIORITY ORDER, not brute concurrency: cov60 and default are the pair the
# actual decision rests on, so they go first. v2/cap are LOWEST priority --
# their coverage ceiling (~107.5) barely differs from default's (~104), so
# they add the least new information of the six, and are explicitly the ones
# to lose if the night runs out of time.
#
# GPU-CONTEXT-AWARE, not a strict "wait for everything else" gate. A logical
# job on this machine shows up as roughly two python.exe processes (a
# launcher + the real worker -- confirmed by memory: the worker holds
# ~1 GiB+, the launcher a few MB), so process-count/2 approximates context
# count. New scans only start once that estimate is below 3, matching
# CLAUDE.md's documented ceiling for this card, and it is CHECKED, not
# assumed -- it does not hardcode "wait for cov60_pipeline.log to say DONE"
# the way earlier scripts did, so it does not idle the GPU if a checkpoint's
# L=32 work happens to finish early.

Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan\volume_scan_pipeline.log"
$py = ".venv\Scripts\python.exe"
"$(Get-Date) pipeline (re)start" *>> $log

function Get-ActiveGpuJobs {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "02_train\.py|28_crossover_scan\.py" }
    if (-not $procs) { return 0 }
    $distinct = $procs | Select-Object -ExpandProperty CommandLine -Unique
    return [Math]::Ceiling($distinct.Count)
}

function Test-TagAlreadyRunning($checkpointPath) {
    # Stop-ScheduledTask does not reliably kill a python.exe it launched --
    # confirmed 2026-09-03: an orphaned cov60 scan process survived two
    # Stop/Start-ScheduledTask cycles on this task and kept producing output
    # the whole time. So "this tag isn't in Test-ScanDone yet" does NOT mean
    # "safe to launch it" -- it might already be running, orphaned or not.
    # Check by checkpoint path (unique per tag) rather than trusting task state.
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "28_crossover_scan\.py" -and $_.CommandLine -match [regex]::Escape($checkpointPath) }
    return [bool]$procs
}

function Wait-ForGpuRoom($budget, $label) {
    # Silent version of this loop was the actual cause of two false-stall
    # restarts tonight (23:15, and the earlier 22:30 one blamed on the
    # training-wait loop instead) -- this loop has no log line at all while
    # waiting, so > 30 minutes of legitimate GPU-room waiting reads as a hang
    # to the watchdog. Heartbeat every poll so it never does again.
    while ((Get-ActiveGpuJobs) -ge $budget) {
        Start-Sleep -Seconds 120
        "$(Get-Date) [$label] still waiting for GPU room (budget $budget contexts, active $(Get-ActiveGpuJobs))" *>> $log
    }
}

function Test-TrainingDone($historyPath, $epochs) {
    if (-not (Test-Path $historyPath)) { return $false }
    try {
        $h = Get-Content $historyPath -Raw | ConvertFrom-Json
        if ($h.Count -eq 0) { return $false }
        return ($h[-1].epoch + 1) -ge $epochs
    } catch { return $false }
}

function Test-ScanDone($path, $n) {
    if (-not (Test-Path $path)) { return $false }
    try { return (Get-Content $path -Raw | ConvertFrom-Json).Count -ge $n }
    catch { return $false }
}

# tag -> (checkpoint path, history path, epochs)
# NOTE 2026-09-03: "default" and "cov30" were pulled OUT of this queue and are
# run by standalone one-off tasks (u2_default_l64_extra, u2_cov30_l64_extra)
# instead, so this script and those two run concurrently as 3 separate GPU
# contexts rather than this queue doing them one at a time after cov60. If
# they were left in here too, this loop would eventually reach them, see
# their scan not yet done, and launch a SECOND competing process against the
# same output files -- a real race, not a hypothetical one, since the extra
# tasks write to the exact same out-dir/tag this queue would use.
$order = @(
    @{ tag="cov60"; hist="out\u2_2d\checkpoints\det_score_net_cov60.history.json"; epochs=120; ckpt="out/u2_2d/checkpoints/det_score_net_cov60.pt" },
    @{ tag="cov15"; hist="out\u2_2d\checkpoints\det_score_net_cov15.history.json"; epochs=120; ckpt="out/u2_2d/checkpoints/det_score_net_cov15.pt" },
    @{ tag="v2"; hist=$null; epochs=0; ckpt="out/u2_2d/checkpoints/det_score_net_v2.pt" },
    @{ tag="cap"; hist=$null; epochs=0; ckpt="out/u2_2d/checkpoints/det_score_net_cap.pt" }
)

foreach ($item in $order) {
    $tag = $item.tag
    if ($item.hist -and -not (Test-TrainingDone $item.hist $item.epochs)) {
        "$(Get-Date) [$tag] training not finished yet -- waiting" *>> $log
        # Heartbeat every poll (not just once): a silent multi-hour wait loop
        # looks identical to a hang to the watchdog's 30-min log-growth check,
        # and it restarted this script once for exactly that reason tonight --
        # harmless (idempotent gates) but wastes one of the 3 restart attempts.
        while (-not (Test-TrainingDone $item.hist $item.epochs)) {
            Start-Sleep -Seconds 120
            "$(Get-Date) [$tag] still waiting for training" *>> $log
        }
    }
    if (Test-ScanDone "out\u2_2d\coverage_scan\$tag\crossover_L64_topo.json" 8) {
        "$(Get-Date) [$tag] L=64 scan already complete -- skipping" *>> $log
        continue
    }
    "$(Get-Date) [$tag] waiting for GPU room (budget 3 contexts)" *>> $log
    Wait-ForGpuRoom 3 $tag
    # Re-check after waiting, not just before: another process (an extra
    # one-off parallel job, or another restarted instance of this same
    # script, possibly an ORPHANED one Stop-ScheduledTask failed to actually
    # kill -- observed 2026-09-03) may have finished this tag's scan, or
    # still be actively running it, during the wait.
    if (Test-ScanDone "out\u2_2d\coverage_scan\$tag\crossover_L64_topo.json" 8) {
        "$(Get-Date) [$tag] L=64 scan completed while waiting for GPU room -- skipping" *>> $log
        continue
    }
    if (Test-TagAlreadyRunning $item.ckpt) {
        "$(Get-Date) [$tag] a scan for this checkpoint is ALREADY RUNNING (likely orphaned from an earlier restart) -- waiting for it instead of launching a duplicate" *>> $log
        while (Test-TagAlreadyRunning $item.ckpt) {
            Start-Sleep -Seconds 120
            "$(Get-Date) [$tag] still waiting on the already-running scan" *>> $log
        }
        if (Test-ScanDone "out\u2_2d\coverage_scan\$tag\crossover_L64_topo.json" 8) {
            "$(Get-Date) [$tag] the already-running scan finished -- skipping" *>> $log
            continue
        }
    }
    "$(Get-Date) [$tag] starting L=64 scan (8 couplings, both rounds)" *>> $log
    & $py "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints $tag --fine-size 64 --n-couplings 8 *>> $log
    if ($LASTEXITCODE -ne 0) {
        "$(Get-Date) [$tag] L=64 scan FAILED, exit $LASTEXITCODE -- continuing to the next checkpoint rather than blocking the whole queue on one failure" *>> $log
    } else {
        "$(Get-Date) [$tag] L=64 scan done" *>> $log
    }
}

"$(Get-Date) all checkpoints attempted -- regenerating comparison figures (L=32 and L=64)" *>> $log
& $py "u2_2d\scripts\59_coverage_comparison_figure.py" --out "out\u2_2d\figures\fig59_coverage_comparison.png" *>> $log
& $py "u2_2d\scripts\59_coverage_comparison_figure.py" --fine-size 64 --out "out\u2_2d\figures\fig59_coverage_comparison_L64.png" *>> $log
"$(Get-Date) PIPELINE DONE" *>> $log
