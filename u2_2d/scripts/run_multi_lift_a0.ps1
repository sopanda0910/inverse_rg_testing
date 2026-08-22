# A0 crashed on a cache-format bug (fixed) and was skipped. Re-run it once the
# main program is done, so the card never holds a fourth CUDA context.
while (-not (Select-String -Path 'out/u2_2d/logs/q_multilift.log' -Pattern 'all done' -Quiet -ErrorAction SilentlyContinue)) {
  Start-Sleep -Seconds 30
}
Write-Output ("[A0 rerun] starting " + (Get-Date -Format HH:mm:ss))
& ".venv\Scripts\python.exe" -u u2_2d/scripts/45_multi_lift_compounding.py --device cuda `
    --start-size 8 --start-beta 6.4002 --n-lifts 3 `
    --intermediate-retherm 0 --out-dir out/u2_2d/multi_lift_incov
Write-Output ("[A0 rerun] done " + (Get-Date -Format HH:mm:ss))
