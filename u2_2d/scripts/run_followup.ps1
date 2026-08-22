# Follow-up to run_queue_par.ps1, 2026-08-21.
#
# ITEM 1 -- the retherm scan's SECOND case never ran. It was queued as
# `--cases 16:105.244,32:105.244`, but there is no L = 32 ensemble at beta
# 105.244 in data_v2 (the L = 32 rungs there are 105.423 and 105.651), so the
# script printed "(skip) missing ..." and produced a ONE-case scan.
#
# That matters more than a typo usually would, because the two cases disagree
# and the missing one is the decisive one. At L = 32, beta = 414.9 the tail does
# NOT damage the infrared: W(8x8) bias/sigma falls 0.0808 -> 0.0093 from 0 to 80
# sweeps, and the best setting is n_retherm = 20 rather than the deployed 10.
# The damage that motivated the whole scan was measured at L = 64, beta = 416.5
# (31_division_of_labour.py: W(8x8) 378 -> 1581 ppm across ten sweeps) -- almost
# the same coupling at twice the volume. So on the evidence in hand the damage
# is a VOLUME effect, and the case that would confirm or kill that is exactly the
# one that got skipped.
#
# 32:105.651 is the ladder rung of record: it matches to fine beta 416.524 at
# L = 64, the coupling 31_division_of_labour.py used.
#
# Both cases are re-run rather than just the missing one, because the script
# writes all of its records into a single retherm_scan.json and a partial re-run
# would clobber the L = 32 result that is already good.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_followup.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "out\u2_2d\queue_0821"
$logs = Join-Path $repo "out\u2_2d\logs"

# Wait for the main queue to release the GPU. The retherm scan at L = 64 lifts
# 256 configurations through a 200-step sampler and then runs 80 cumulative
# sweeps on them; running it against a live training job would slow both.
#
# Poll for the QUEUE process specifically, not for "any python": the queue is
# briefly python-free between phases, and a bare `Get-Process python` check
# would fire this off in the middle of one.
while ($true) {
    $q = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
         Where-Object { $_.CommandLine -like "*run_queue_par.ps1*" }
    if (-not $q) { break }
    Start-Sleep -Seconds 60
}
Write-Host "[followup] main queue clear $(Get-Date -Format 'HH:mm:ss')"

# The stale sentinel names a run that only covered half its cases.
Remove-Item (Join-Path $state "04_retherm_scan.done") -ErrorAction SilentlyContinue

$log = Join-Path $logs "q_04_retherm_scan_fixed.log"
$started = Get-Date
Write-Host "[run ] 04_retherm_scan_fixed  $($started.ToString('HH:mm:ss'))"
& $py -u u2_2d/scripts/33_retherm_scan.py --device cuda `
    --cases "16:105.244,32:105.651" --n-configs 256 `
    --sampler-steps 200 --sweeps "0,2,5,10,20,40,80" *>&1 |
    Out-File -FilePath $log -Encoding utf8
$code = $LASTEXITCODE
$mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
if ($code -eq 0) {
    "ok" | Out-File -FilePath (Join-Path $state "04_retherm_scan.done") -Encoding utf8
    Write-Host "[done] 04_retherm_scan_fixed  ${mins} min"
} else {
    Write-Host "[FAIL] 04_retherm_scan_fixed  exit $code after ${mins} min -- see $log"
}
