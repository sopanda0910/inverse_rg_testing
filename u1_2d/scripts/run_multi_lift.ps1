# u1 multi-lift program -- the mirror of u2_2d/scripts/run_multi_lift.ps1.
# CPU by design: u1 batched HMC is faster on CPU at L <= 32 (see CLAUDE.md's
# device table) and it leaves the GPU entirely to the u2 queue.
$py = ".venv\Scripts\python.exe"
$env:U1_2D_TORCH_THREADS = "4"
$runs = @(
  @{ beta = "1.30"; dir = "out/u1_2d/multi_lift_incov";   r = 10; tag = "A: endpoint beta 52.9 IN COVERAGE, ladder retherm" },
  @{ beta = "1.30"; dir = "out/u1_2d/multi_lift_incov";   r = 0;  tag = "A0: same, PURE model composition" },
  @{ beta = "1.75"; dir = "out/u1_2d/multi_lift_ceiling"; r = 10; tag = "B: endpoint beta 75.4, +26% PAST the training ceiling" },
  @{ beta = "1.75"; dir = "out/u1_2d/multi_lift_ceiling"; r = 0;  tag = "B0: same, PURE model composition" }
)
foreach ($run in $runs) {
  Write-Output ("=" * 74)
  Write-Output ("[u1 multi-lift] " + $run.tag + "  " + (Get-Date -Format HH:mm:ss))
  & $py -u u1_2d/scripts/60_multi_lift_compounding.py --device cpu `
      --start-size 8 --start-beta $run.beta --n-lifts 3 `
      --intermediate-retherm $run.r --out-dir $run.dir
  if ($LASTEXITCODE -ne 0) { Write-Output "[u1 multi-lift] FAILED: $($run.tag)" }
}
Write-Output ("[u1 multi-lift] all done " + (Get-Date -Format HH:mm:ss))
