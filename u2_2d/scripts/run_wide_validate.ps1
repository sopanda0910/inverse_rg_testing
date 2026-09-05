Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\wide_validate.log"
$py = ".venv\Scripts\python.exe"
"$(Get-Date) u2 wide validate start" *>> $log
& $py "u2_2d\scripts\04_validate.py" --config "u2_2d\configs\wide.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
