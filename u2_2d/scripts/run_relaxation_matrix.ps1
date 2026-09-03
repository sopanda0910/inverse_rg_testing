Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan_relaxation\orchestrator.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\coverage_scan_relaxation" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) orchestrator (re)start" *>> $log
& $py "u2_2d\scripts\60_run_full_relaxation_matrix.py" --budget 3 --poll-seconds 20 *>> $log
"$(Get-Date) orchestrator exited $LASTEXITCODE" *>> $log
if ($LASTEXITCODE -eq 0) {
    "PIPELINE DONE $(Get-Date)" *>> $log
} else {
    # Missing until 2026-09-03: this wrapper never wrote the literal
    # "FAILED" string watchdog_overnight.ps1's $explicitFail detector looks
    # for, and the stall detector only fires while the task state is
    # "Running" -- but a crashed orchestrator leaves the task "Ready", so
    # neither ever caught it. The orchestrator DIED SILENTLY once and the
    # watchdog reported it as merely "Ready, log age Nm" tick after tick with
    # no alert, discovered only by a direct status check. This line closes
    # that gap the same way every other wrapper script in this project does.
    "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log
    exit 1
}
