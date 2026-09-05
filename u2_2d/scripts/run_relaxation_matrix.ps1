Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan_relaxation\orchestrator.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\coverage_scan_relaxation" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) orchestrator (re)start" *>> $log
# Trimmed to 2 (from 3) 2026-09-03: with u1's wide2000 training also holding a
# GPU context, 3 matrix jobs + 1 training job = 4 concurrent CUDA contexts
# triggered a driver reset (nvlddmkm event 153) at 19:26:36, killing every
# running job simultaneously with no clean error trace. 2 + 1 = 3 matches the
# documented stable ceiling.
& $py "u2_2d\scripts\60_run_full_relaxation_matrix.py" --budget 2 --poll-seconds 20 *>> $log
"$(Get-Date) orchestrator exited $LASTEXITCODE" *>> $log
if ($LASTEXITCODE -eq 0) {
    "PIPELINE DONE $(Get-Date)" *>> $log
} else {
    # Missing until 2026-09-03: this wrapper never wrote the literal
    # "FAILED" string watchdog_overnight.ps1's $explicitFail detector looks
    # for, and the stall detector only fires while the task state is
    # "Running" -- but a crashed orchestrator leaves the task "Ready", so
    # neither ever caught it. The orchestrator DIED SILENTLY once and the
    # watchdog reported it as merely "Ready, log age Nm" tick after tick with
    # no alert, discovered only by a direct status check. This line closes
    # that gap the same way every other wrapper script in this project does.
    "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log
}

# Auto-chain 2026-09-03: whether the matrix finished clean or failed, don't
# leave the GPU idle overnight -- resume u1's wide2000 training (paused
# earlier tonight to give the matrix the full card). Runs either way: a
# stalled/failed matrix leaving the GPU idle until morning would waste more
# compute than the failure itself.
# Guarded 2026-09-05: wide2000's train->ladder->validate chain already
# completed once (out/u1_2d/wide2000_train.log ends "PIPELINE DONE"). Without
# this check, re-running this orchestrator for a DIFFERENT checkpoint (e.g.
# the "wide" u2 scan) would blindly re-trigger u1's already-finished pipeline,
# wasting GPU time re-doing a completed ladder+validate for no reason.
$wide2000Log = "out\u1_2d\wide2000_train.log"
$alreadyDone = (Test-Path $wide2000Log) -and ((Get-Content $wide2000Log -Raw -Encoding Unicode) -match "PIPELINE DONE")
if ($alreadyDone) {
    "$(Get-Date) u1_wide2000_train already completed -- not re-triggering" *>> $log
} else {
    "$(Get-Date) resuming u1_wide2000_train" *>> $log
    Start-ScheduledTask -TaskName "u1_wide2000_train"
}
