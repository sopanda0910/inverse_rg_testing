# Master driver for the u2 thermalization / autocorrelation package (2026-08-24).
# Waits for the transport-off ladder to release the GPU, then runs two waves of
# two concurrent processes each, then the two analyses.
$ErrorActionPreference = "Continue"
$py = ".venv/Scripts/python.exe"
$top = "out/u2_2d/ladder_transport_off/ladder_L64_beta416.524.pt"

Write-Host "waiting for transport-off ladder ($top) ..."
$stable = 0
while ($stable -lt 3) {
  if (Test-Path $top) {
    $a = (Get-Item $top).Length
    Start-Sleep -Seconds 10
    $b = (Get-Item $top).Length
    if ($a -eq $b -and $a -gt 0) { $stable++ } else { $stable = 0 }
  } else { Start-Sleep -Seconds 15 }
}
Write-Host "ladder done at $(Get-Date -Format HH:mm:ss)"

Write-Host "=== WAVE 1 (L=64) start $(Get-Date -Format HH:mm:ss) ==="
& powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_ta_wave1.ps1
Write-Host "=== WAVE 2 (L=32) start $(Get-Date -Format HH:mm:ss) ==="
& powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_ta_wave2.ps1

Write-Host "=== transport ablation $(Get-Date -Format HH:mm:ss) ==="
& $py u2_2d/scripts/51_transport_ablation.py 2>&1

Write-Host "=== tuned-sweep stability $(Get-Date -Format HH:mm:ss) ==="
& $py u2_2d/scripts/52_tuned_sweep_stability.py --seeds 0 1 2 3 4 --rung -1 2>&1

Write-Host "=== ALL DONE $(Get-Date -Format HH:mm:ss) ==="
