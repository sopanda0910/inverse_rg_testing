Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\wide2000_train.log"
New-Item -ItemType Directory -Force -Path "out\u1_2d\checkpoints" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) u1 wide2000 retrain (re)start" *>> $log
& $py "u1_2d\scripts\02_train.py" --config "u1_2d\configs\wide2000.yaml" --device cuda --resume *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (train), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) training done, starting ladder" *>> $log

# Mirrors u2's already-completed wide-checkpoint pipeline (run_wide_ladder.ps1 /
# run_wide_validate.ps1): once training converges, generate the ladder and
# validate it against reference HMC, so the wide2000 result is fully ready
# without a manual handoff.
& $py "u1_2d\scripts\03_run_ladder.py" --config "u1_2d\configs\wide2000.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (ladder), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) ladder done, starting validate" *>> $log

& $py "u1_2d\scripts\04_validate.py" --config "u1_2d\configs\wide2000.yaml" --device cpu *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (validate), exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
