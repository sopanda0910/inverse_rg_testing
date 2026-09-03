Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\wide_train.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\checkpoints" | Out-Null
$py = ".venv\Scripts\python.exe"
"$(Get-Date) wide-coverage retrain (re)start" *>> $log
& $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\wide.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
