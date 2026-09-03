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
if (Test-Path $ckpt) {
    "$(Get-Date) $ckpt already exists -- skipping training" *>> $log
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
# Scoped to exactly the 16 parts-A/D cases 05_hmc_thermalization.py's default
# --parts A,D consumes (read off the deployed checkpoint's own
# out/u1_2d/generalization/summary.json) -- the unscoped run is a much larger
# 44-case, multi-part study this comparison does not need.
$cases = "A_bc0.25,A_bc0.5,A_bc0.75,A_bc1,A_bc1.5,A_bc2,A_bc3,A_bc4,A_bc5,A_bc6,A_bc8,D_bc14.1464,D_bc20,D_bc30,D_bc40,D_bc55.0237"

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
