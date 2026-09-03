Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
$log = "out\u2_2d\coverage_scan\cap_run.log"
"$(Get-Date) pipeline (re)start" *>> $log
& ".venv\Scripts\python.exe" "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints cap *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) PIPELINE DONE" *>> $log
