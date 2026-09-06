Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\wide2000_dense_full.log"
New-Item -ItemType Directory -Force -Path "out\u1_2d\checkpoints" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) u1 wide2000_dense full pipeline start" *>> $log

& $py "u1_2d\scripts\02_train.py" --config "u1_2d\configs\wide2000_dense.yaml" --device cuda --resume *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (train), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) training done, starting ladder" *>> $log

& $py "u1_2d\scripts\03_run_ladder.py" --config "u1_2d\configs\wide2000_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (ladder), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) ladder done, starting validate" *>> $log

& $py "u1_2d\scripts\04_validate.py" --config "u1_2d\configs\wide2000_dense.yaml" --device cpu *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (validate), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) validate done, starting matched L16-target eval" *>> $log

# Same matched L=8->16 comparison used for wide2000 vs deployed
# (u1_2d/scripts/06_generalization_study.py's F_L16_bc* cases), now for
# wide2000_dense, so it lands on the identical 7 couplings and can be
# compared directly against out/u1_2d/coverage_scan/wide2000_L16target/.
$ckpt = "out\u1_2d\checkpoints\score_net_wide2000_dense.pt"
$cases = "F_L16_bc75.3776,F_L16_bc100.377,F_L16_bc137.876,F_L16_bc187.876,F_L16_bc250.376,F_L16_bc375.375,F_L16_bc500.375"
$genDir = "out\u1_2d\coverage_scan\wide2000_dense_L16target\generalization"
$thermDir = "out\u1_2d\coverage_scan\wide2000_dense_L16target\thermalization"
$mergedOut = "out\u1_2d\coverage_scan\wide2000_dense_L16target\crossover_window.json"

& $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $ckpt --out-dir $genDir --device cuda --cases $cases *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (generalization), exit $LASTEXITCODE" *>> $log; exit 1 }

& $py "u1_2d\scripts\05_hmc_thermalization.py" --generalization $genDir --checkpoint $ckpt --out $thermDir --parts F *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (thermalization), exit $LASTEXITCODE" *>> $log; exit 1 }

& $py "u1_2d\scripts\35_crossover_window.py" --dir $thermDir --out $mergedOut *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (crossover-window merge), exit $LASTEXITCODE" *>> $log; exit 1 }

"PIPELINE DONE $(Get-Date)" *>> $log
