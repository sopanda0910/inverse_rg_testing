Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\sectorfix_retrain.log"
$py = ".venv\Scripts\python.exe"

# GATE ON THE PROPERTY, NOT ON A LOG MARKER.
#
# The first version waited for the string "U1 SECTORFIX DATA DONE" to appear
# in the data-regeneration log. That log is opened in APPEND mode, and it
# already contained that marker from the morning's failed run -- so the gate
# fired instantly, swapped the 4 rungs that happened to exist at that moment,
# and started a retrain on data where 26 of 30 supplement rungs were still
# single-sector. Exit codes and log markers are both stale-able; the number of
# regenerated rungs actually on disk is not.
"$(Get-Date) waiting for all 30 regenerated rungs" *>> $log
while ($true) {
    $n = @(Get-ChildItem "out\u1_2d\data_random_2000_sectorfix\*.pt" -ErrorAction SilentlyContinue).Count
    $busy = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
              Where-Object { $_.CommandLine -like "*01_generate_data*" }).Count
    if ($n -ge 30 -and $busy -eq 0) { break }
    Start-Sleep -Seconds 60
}
"$(Get-Date) all 30 rungs present and generators idle; swapping" *>> $log

& $py "u1_2d\scripts\swap_sectorfix_rungs.py" *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (swap/verify), aborting" *>> $log; exit 1 }

& $py "u2_2d\scripts\gpu_slots.py" --label "u1-sectorfix-retrain" -- `
    $py "u1_2d\scripts\02_train.py" --config "u1_2d\configs\wide2000_dense_sectorfix.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (train), exit $LASTEXITCODE" *>> $log; exit 1 }
"U1 SECTORFIX RETRAIN DONE $(Get-Date)" *>> $log
