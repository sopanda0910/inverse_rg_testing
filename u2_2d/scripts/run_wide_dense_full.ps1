Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\wide_dense_full.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\checkpoints" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) u2 wide_dense full pipeline start" *>> $log

& $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (train), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) training done, starting ladder" *>> $log

& $py "u2_2d\scripts\03_run_ladder.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (ladder), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) ladder done, starting validate" *>> $log

& $py "u2_2d\scripts\04_validate.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (validate), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) validate done, starting relaxation matrix (wide_dense only, PRIORITY set in 60_run_full_relaxation_matrix.py)" *>> $log

& $py "u2_2d\scripts\60_run_full_relaxation_matrix.py" --budget 2 --poll-seconds 20 *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (relaxation matrix), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) relaxation matrix done, computing per-observable tau" *>> $log

& $py "u2_2d\scripts\68_per_observable_tau.py" --dir "out\u2_2d\coverage_scan_relaxation\wide_dense" *>> $log

"PIPELINE DONE $(Get-Date)" *>> $log
