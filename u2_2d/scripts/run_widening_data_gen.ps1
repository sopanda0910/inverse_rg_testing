Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\data_widening_test\gen.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\data_widening_test" | Out-Null
$py = ".venv\Scripts\python.exe"
"$(Get-Date) widening-test data generation (re)start" *>> $log
& $py "u2_2d\scripts\01_generate_data.py" --config "u2_2d\configs\widening_test.yaml" --device cpu *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
