Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan\cov60_pipeline.log"
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) pipeline (re)start" *>> $log

function Test-Done($path, $n) {
    if (-not (Test-Path $path)) { return $false }
    try {
        $count = (Get-Content $path -Raw | ConvertFrom-Json).Count
        return $count -ge $n
    } catch { return $false }
}

# Wait for the v2/cap coverage scans (2 CUDA contexts already in flight) to
# finish both rounds before starting a 3rd/4th context -- CLAUDE.md: this
# card holds 3 CUDA contexts of this workload, not 4.
"$(Get-Date) waiting for v2/cap coverage scans to finish" *>> $log
while (-not ((Test-Done "out\u2_2d\coverage_scan\v2\crossover_topo.json" 14) -and
             (Test-Done "out\u2_2d\coverage_scan\cap\crossover_topo.json" 14))) {
    Start-Sleep -Seconds 120
}
"$(Get-Date) v2/cap done -- training cov60" *>> $log

# Checked by EPOCH COUNT in history.json, not by the checkpoint file's mere
# existence -- a checkpoint can exist mid-training (periodic saves), and
# Test-Path alone treated that as "done" once already (cov15's CPU run).
function Test-TrainingDone($historyPath, $epochs) {
    if (-not (Test-Path $historyPath)) { return $false }
    try {
        $h = Get-Content $historyPath -Raw | ConvertFrom-Json
        if ($h.Count -eq 0) { return $false }
        return ($h[-1].epoch + 1) -ge $epochs
    } catch { return $false }
}

if (Test-TrainingDone "out\u2_2d\checkpoints\det_score_net_cov60.history.json" 120) {
    "$(Get-Date) cov60 already trained -- skipping training" *>> $log
} else {
    # train.resume: true is set in cov60.yaml -- a Task-Scheduler restart
    # after a crash resumes from the last snapshot (snapshot_every: 10)
    # instead of retraining from epoch 0.
    & $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\cov60.yaml" *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov60 training FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
}
"$(Get-Date) cov60 trained -- running its coverage scan" *>> $log

if (-not (Test-Done "out\u2_2d\coverage_scan\cov60\crossover_topo.json" 14)) {
    & $py "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints cov60 *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) cov60 coverage scan FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) cov60 coverage scan already complete -- skipping" *>> $log
}
"$(Get-Date) cov60 coverage scan done -- regenerating comparison figures" *>> $log

& $py "u2_2d\scripts\59_coverage_comparison_figure.py" *>> $log
"$(Get-Date) PIPELINE DONE" *>> $log
