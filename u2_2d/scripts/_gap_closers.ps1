# The two remaining figure-parity items, run as ONE process so they never add
# more than a single CUDA context alongside the two sector-experiment trainings
# (three is this card's measured ceiling).
$py = ".venv\Scripts\python.exe"
Write-Host "[gap] retherm reconciliation $(Get-Date -Format 'HH:mm:ss')"
& $py -u u2_2d/scripts/42_retherm_reconcile.py --device cuda
Write-Host "[gap] observable scan $(Get-Date -Format 'HH:mm:ss')"
& $py -u u2_2d/scripts/43_observable_scan.py --device cuda
Write-Host "[gap] done $(Get-Date -Format 'HH:mm:ss')"
