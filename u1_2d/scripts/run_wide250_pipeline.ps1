Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\wide250_pipeline.log"
$py = ".venv\Scripts\python.exe"
# Fragmentation-driven OOM is the documented failure mode on this 8 GiB card
# with several concurrent CUDA contexts (CLAUDE.md, run_queue_resume.ps1).
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

"$(Get-Date) pipeline (re)start" *>> $log
& $py "u1_2d\scripts\01_generate_data.py" --config "u1_2d\configs\wide250.yaml" *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) data-gen FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }

$ckpt = "out\u1_2d\checkpoints\score_net_wide250.pt"
# Checked by EPOCH COUNT in history.json, not by the checkpoint file's mere
# existence -- a checkpoint can exist mid-training (periodic saves), and
# Test-Path alone treated that as "done" once already (u2's cov15 CPU run).
# u1's history.json appends one non-epoch heldout-summary entry at the end,
# so this takes the max epoch over entries that HAVE one, not the last entry.
function Test-TrainingDone($historyPath, $epochs) {
    if (-not (Test-Path $historyPath)) { return $false }
    try {
        $h = Get-Content $historyPath -Raw | ConvertFrom-Json
        $withEpoch = $h | Where-Object { $_.PSObject.Properties.Name -contains "epoch" }
        if ($withEpoch.Count -eq 0) { return $false }
        $maxEpoch = ($withEpoch | Measure-Object -Property epoch -Maximum).Maximum
        return ($maxEpoch + 1) -ge $epochs
    } catch { return $false }
}
if (Test-TrainingDone "out\u1_2d\checkpoints\score_net_wide250.history.json" 100) {
    "$(Get-Date) $ckpt already trained -- skipping training" *>> $log
} else {
    # --resume: harmless on a fresh run (no .resume snapshot yet); on a
    # Task-Scheduler-triggered restart after a crash it continues from the
    # last snapshot (train.snapshot_every: 5) instead of losing all epochs.
    & $py "u1_2d\scripts\02_train.py" --config "u1_2d\configs\wide250.yaml" --resume *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) training FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
}
"$(Get-Date) score_net_wide250.pt trained -- running its generalization + thermalization scan" *>> $log

$genDir = "out\u1_2d\coverage_scan\wide250\generalization"
$thermDir = "out\u1_2d\coverage_scan\wide250\thermalization"
$mergedOut = "out\u1_2d\coverage_scan\wide250\crossover_window.json"
# Scoped to the 16 parts-A/D cases 05_hmc_thermalization.py's default
# --parts A,D consumes (read off the deployed checkpoint's own
# out/u1_2d/generalization/summary.json) -- the unscoped run is a much larger
# 44-case, multi-part study this comparison does not need. PLUS two VOLUME
# cases (base_size 32 -> fine 64): C_L64 (beta 14.1464) and F_L64_bc55.0237
# (beta 218.58, the SAME coupling the deployed checkpoint's own L=64 point in
# crossover_window.json uses) -- without these the wide250 comparison would
# have zero L=64 data, since every A/D case lifts L=16 -> L=32.
$cases = "A_bc0.25,A_bc0.5,A_bc0.75,A_bc1,A_bc1.5,A_bc2,A_bc3,A_bc4,A_bc5,A_bc6,A_bc8,D_bc14.1464,D_bc20,D_bc30,D_bc40,D_bc55.0237,C_L64,F_L64_bc55.0237"

if (-not (Test-Path "$genDir\summary.json")) {
    & $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $ckpt --out-dir $genDir --device cuda --cases $cases *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) generalization study FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) $genDir\summary.json already exists -- skipping (re-running "`
    + "with the same --cases resumes any still-missing cases; 06 skips ones "`
    + "already in summary.json)" *>> $log
    & $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $ckpt --out-dir $genDir --device cuda --cases $cases *>> $log
}

if (-not (Test-Path $mergedOut)) {
    & $py "u1_2d\scripts\05_hmc_thermalization.py" --generalization $genDir --checkpoint $ckpt --out $thermDir *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) thermalization benchmark FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }

    & $py "u1_2d\scripts\35_crossover_window.py" --dir $thermDir --out $mergedOut *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) crossover-window merge FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) $mergedOut already exists -- skipping thermalization+merge" *>> $log
}

& $py "u1_2d\scripts\67_coverage_comparison_figure.py" *>> $log

"PIPELINE DONE $(Get-Date)" *>> $log
