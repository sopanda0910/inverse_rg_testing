Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan\cpu_pipeline.log"
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) pipeline (re)start" *>> $log

# MOVED TO GPU 2026-09-02, ~21:30. CPU training measured at ~6.4 min/epoch for
# cov15 (18 epochs in 115 min) -- at that rate 120 epochs is ~13h, and cov30
# (88 rungs, even more) would add another ~16h+ behind it. That is far slower
# than this comparison is worth; cov15/cov30.yaml now set device: cuda. v2/cap
# finished their scans by the time this was caught, so the GPU has room
# (cov60 alone, 1 context) for these too -- 2-3 concurrent contexts, still
# inside the documented 3-context ceiling. The partial CPU run is NOT wasted:
# train.resume: true + the epoch-18 snapshot (snapshot_every: 10, so the
# checkpoint is current to about epoch 10-18) let training pick up close to
# where the CPU run left off, on the faster device.
#
# "Already trained" is checked by EPOCH COUNT in history.json, not by the
# checkpoint file's mere existence -- Test-Path alone was wrong here once
# already: it treated a checkpoint that was merely mid-training (periodic
# saves during CPU training) as "done" and would have skipped finishing it.
function Test-TrainingDone($historyPath, $epochs) {
    if (-not (Test-Path $historyPath)) { return $false }
    try {
        $h = Get-Content $historyPath -Raw | ConvertFrom-Json
        if ($h.Count -eq 0) { return $false }
        return ($h[-1].epoch + 1) -ge $epochs
    } catch { return $false }
}

if (-not (Test-TrainingDone "out\u2_2d\checkpoints\det_score_net_cov15.history.json" 120)) {
    "$(Get-Date) training cov15 (GPU, resuming from the CPU-trained snapshot)" *>> $log
    & $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\cov15.yaml" *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov15 training FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) cov15 already trained -- skipping" *>> $log
}

if (-not (Test-TrainingDone "out\u2_2d\checkpoints\det_score_net_cov30.history.json" 120)) {
    "$(Get-Date) training cov30 (GPU)" *>> $log
    & $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\cov30.yaml" *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov30 training FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) cov30 already trained -- skipping" *>> $log
}

"$(Get-Date) both checkpoints trained -- waiting for the GPU-bound scan queue (v2/cap/cov60) before scanning" *>> $log

# The scan step (28_crossover_scan.py: diffusion lift + batched HMC) is GPU-
# bound, unlike training here -- so queue behind whatever is already using the
# card rather than adding a 4th/5th concurrent CUDA context.
while (-not (Select-String -Path "out\u2_2d\coverage_scan\cov60_pipeline.log" -Pattern "PIPELINE DONE" -Quiet -ErrorAction SilentlyContinue)) {
    Start-Sleep -Seconds 120
    "$(Get-Date) still waiting on cov60_pipeline to finish" *>> $log
}
function Test-Done($path, $n) {
    if (-not (Test-Path $path)) { return $false }
    try { return (Get-Content $path -Raw | ConvertFrom-Json).Count -ge $n }
    catch { return $false }
}

if (-not (Test-Done "out\u2_2d\coverage_scan\cov15\crossover_topo.json" 14)) {
    "$(Get-Date) GPU queue clear -- scanning cov15" *>> $log
    & $py "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints cov15 *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov15 scan FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) cov15 scan already complete -- skipping" *>> $log
}

if (-not (Test-Done "out\u2_2d\coverage_scan\cov30\crossover_topo.json" 14)) {
    "$(Get-Date) scanning cov30" *>> $log
    & $py "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints cov30 *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov30 scan FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) cov30 scan already complete -- skipping" *>> $log
}

"$(Get-Date) regenerating comparison figure" *>> $log
& $py "u2_2d\scripts\59_coverage_comparison_figure.py" *>> $log
"$(Get-Date) PIPELINE DONE" *>> $log
