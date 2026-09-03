Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan_relaxation\orchestrator.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\coverage_scan_relaxation" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) orchestrator (re)start" *>> $log
& $py "u2_2d\scripts\60_run_full_relaxation_matrix.py" --budget 3 --poll-seconds 20 *>> $log
"$(Get-Date) orchestrator exited $LASTEXITCODE" *>> $log
if ($LASTEXITCODE -eq 0) { "PIPELINE DONE $(Get-Date)" *>> $log }
