# Re-run the coverage-checkpoint density gap, correctly this time.
#
# The original fix3d_density_cov passed only --out-dir, so 18_density_gap.py
# took its checkpoint from the config and reran the DEPLOYED net into a new
# directory: KL 9394.0 in both arms, identical to the decimal. --checkpoint now
# exists and is passed explicitly.
#
# Waits for U2FixQueue to stop first -- both stages are GPU-bound and the card
# is 8 GiB.

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo
$py   = Join-Path $repo ".venv\Scripts\python.exe"
$logs = Join-Path $repo "out\u2_2d\logs"

while ((Get-ScheduledTask -TaskName U2FixQueue -ErrorAction SilentlyContinue).State -eq "Running") {
    Start-Sleep -Seconds 30
}
Write-Host "queue idle; starting corrected density_gap_cov"

& $py (Join-Path $repo "u2_2d\scripts\18_density_gap.py") `
    --config (Join-Path $repo "u2_2d\configs\default.yaml") `
    --checkpoint (Join-Path $repo "out\u2_2d\checkpoints\det_score_net_cov.pt") `
    --n-configs 64 --ode-steps 120 --n-probes 2 --batch-size 8 `
    --out-dir (Join-Path $repo "out\u2_2d\density_gap_cov") `
    *> (Join-Path $logs "fix3d_density_cov_FIXED.log")

Write-Host "exit $LASTEXITCODE"
