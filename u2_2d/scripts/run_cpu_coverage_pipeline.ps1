Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan\cpu_pipeline.log"
$py = ".venv\Scripts\python.exe"
"$(Get-Date) pipeline (re)start" *>> $log

# Training runs on CPU immediately (device: cpu in both configs) -- cheap
# enough (71/88 rungs vs the deployed net's ~9-114) that it does not need to
# wait its turn behind the GPU-bound scans already queued (v2, cap, cov60).
$ckpt15 = "out\u2_2d\checkpoints\det_score_net_cov15.pt"
if (Test-Path $ckpt15) {
    "$(Get-Date) $ckpt15 already exists -- skipping" *>> $log
} else {
    "$(Get-Date) training cov15 (CPU)" *>> $log
    # train.resume: true in cov15.yaml resumes from the last snapshot
    # (snapshot_every: 10) on a Task-Scheduler restart.
    & $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\cov15.yaml" *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov15 training FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
}

$ckpt30 = "out\u2_2d\checkpoints\det_score_net_cov30.pt"
if (Test-Path $ckpt30) {
    "$(Get-Date) $ckpt30 already exists -- skipping" *>> $log
} else {
    "$(Get-Date) training cov30 (CPU)" *>> $log
    & $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\cov30.yaml" *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov30 training FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
}

"$(Get-Date) both CPU checkpoints trained -- waiting for the GPU-bound scan queue (v2/cap/cov60) before scanning" *>> $log

# The scan step (28_crossover_scan.py: diffusion lift + batched HMC) is GPU-
# bound, unlike training here -- so queue behind whatever is already using the
# card rather than adding a 4th/5th concurrent CUDA context.
while (-not (Select-String -Path "out\u2_2d\coverage_scan\cov60_pipeline.log" -Pattern "PIPELINE DONE" -Quiet -ErrorAction SilentlyContinue)) {
    Start-Sleep -Seconds 120
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
