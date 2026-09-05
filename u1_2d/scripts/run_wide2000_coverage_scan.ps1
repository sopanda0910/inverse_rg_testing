Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\wide2000_coverage_scan.log"
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

# Mirrors run_wide250_pipeline.ps1's generalization+thermalization+merge
# section (training is already done -- score_net_wide2000.pt, train->ladder
# ->validate completed 2026-09-04). Same case list as wide250's own scan
# (A/D up to bc=55.0237, C/F size-scan cases) PLUS the five new high-beta D
# cases (bc=100/150/220/320/470 -> bf=398.5/598.5/878.5/1278.5/1878.5) added
# to 06_generalization_study.py's D_COARSE_BETAS specifically so this
# checkpoint's actual new territory (past wide250's 250 ceiling, toward its
# own 2000) is probed, not just the range wide250 already covered.
"$(Get-Date) wide2000 coverage scan start" *>> $log

$ckpt = "out\u1_2d\checkpoints\score_net_wide2000.pt"
$genDir = "out\u1_2d\coverage_scan\wide2000\generalization"
$thermDir = "out\u1_2d\coverage_scan\wide2000\thermalization"
$mergedOut = "out\u1_2d\coverage_scan\wide2000\crossover_window.json"
$cases = "A_bc0.25,A_bc0.5,A_bc0.75,A_bc1,A_bc1.5,A_bc2,A_bc3,A_bc4,A_bc5,A_bc6,A_bc8," `
    + "D_bc14.1464,D_bc20,D_bc30,D_bc40,D_bc55.0237,D_bc100,D_bc150,D_bc220,D_bc320,D_bc470," `
    + "C_L64,F_L64_bc55.0237"

if (-not (Test-Path "$genDir\summary.json")) {
    & $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $ckpt --out-dir $genDir --device cuda --cases $cases *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) generalization study FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) $genDir\summary.json already exists -- resuming any still-missing cases" *>> $log
    & $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $ckpt --out-dir $genDir --device cuda --cases $cases *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) generalization study FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
}

if (-not (Test-Path $mergedOut)) {
    & $py "u1_2d\scripts\05_hmc_thermalization.py" --generalization $genDir --checkpoint $ckpt --out $thermDir *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) thermalization benchmark FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }

    & $py "u1_2d\scripts\35_crossover_window.py" --dir $thermDir --out $mergedOut *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) crossover-window merge FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
} else {
    "$(Get-Date) $mergedOut already exists -- skipping thermalization+merge" *>> $log
}

"PIPELINE DONE $(Get-Date)" *>> $log
