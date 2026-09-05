Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\wide2000_L16target_check.log"
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

# Corrected, fair comparison for wide2000's actual new coverage: its high-beta
# rungs (300-2000) are all fine=16 (lattice_size: 16 in wide2000.yaml), so the
# only way to test them is base_size=8 -> fine=16 cases (06_generalization_
# study.py's new F_L16_bc* entries), not the base_size=16 -> fine=32 cases an
# earlier run mistakenly used. Both the deployed checkpoint (score_net.pt,
# beta_max=60, never trained past there at all) and wide2000
# (score_net_wide2000.pt, beta_max=2000 but ONLY at fine=16) are run on the
# identical 7 cases so the comparison is apples-to-apples.
"$(Get-Date) wide2000 L16-target check start" *>> $log

$cases = "F_L16_bc75.3776,F_L16_bc100.377,F_L16_bc137.876,F_L16_bc187.876,F_L16_bc250.376,F_L16_bc375.375,F_L16_bc500.375"

foreach ($tag in @("deployed", "wide2000")) {
    if ($tag -eq "deployed") { $ckpt = "out\u1_2d\checkpoints\score_net.pt" }
    else { $ckpt = "out\u1_2d\checkpoints\score_net_wide2000.pt" }
    $genDir = "out\u1_2d\coverage_scan\wide2000_L16target\$tag\generalization"
    $thermDir = "out\u1_2d\coverage_scan\wide2000_L16target\$tag\thermalization"
    $mergedOut = "out\u1_2d\coverage_scan\wide2000_L16target\$tag\crossover_window.json"

    "$(Get-Date) [$tag] generalization study" *>> $log
    & $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $ckpt --out-dir $genDir --device cuda --cases $cases *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) [$tag] FAILED (generalization), exit $LASTEXITCODE" *>> $log; exit 1 }

    if (-not (Test-Path $mergedOut)) {
        "$(Get-Date) [$tag] thermalization benchmark" *>> $log
        & $py "u1_2d\scripts\05_hmc_thermalization.py" --generalization $genDir --checkpoint $ckpt --out $thermDir --parts F *>> $log
        if ($LASTEXITCODE -ne 0) { "$(Get-Date) [$tag] FAILED (thermalization), exit $LASTEXITCODE" *>> $log; exit 1 }

        & $py "u1_2d\scripts\35_crossover_window.py" --dir $thermDir --out $mergedOut *>> $log
        if ($LASTEXITCODE -ne 0) { "$(Get-Date) [$tag] FAILED (crossover-window merge), exit $LASTEXITCODE" *>> $log; exit 1 }
    } else {
        "$(Get-Date) [$tag] $mergedOut already exists -- skipping" *>> $log
    }
}

"PIPELINE DONE $(Get-Date)" *>> $log
