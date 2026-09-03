Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\wide2000_train.log"
New-Item -ItemType Directory -Force -Path "out\u1_2d\checkpoints" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) u1 wide2000 retrain (re)start" *>> $log
& $py "u1_2d\scripts\02_train.py" --config "u1_2d\configs\wide2000.yaml" --device cuda --resume *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
