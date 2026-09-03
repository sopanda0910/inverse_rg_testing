Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan\default_l64_extra.log"
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) extra parallel job (re)start: default checkpoint, L=64" *>> $log

function Test-ScanDone($path, $n) {
    if (-not (Test-Path $path)) { return $false }
    try { return (Get-Content $path -Raw | ConvertFrom-Json).Count -ge $n }
    catch { return $false }
}

if (Test-ScanDone "out\u2_2d\coverage_scan\default\crossover_L64_topo.json" 8) {
    "$(Get-Date) default L=64 scan already complete -- skipping" *>> $log
} else {
    & $py "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints default --fine-size 64 --n-couplings 8 *>> $log
    if ($LASTEXITCODE -ne 0) {
        "$(Get-Date) default L=64 scan FAILED, exit $LASTEXITCODE" *>> $log
        exit 1
    }
}
"$(Get-Date) PIPELINE DONE" *>> $log
