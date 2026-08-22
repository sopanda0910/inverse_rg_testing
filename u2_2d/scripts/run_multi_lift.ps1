# Multi-lift program: two chains x two retherm settings, run SEQUENTIALLY.
# Sequential is deliberate -- this card holds three CUDA contexts of this
# workload and two are already held by the sector trainings.
$py = ".venv\Scripts\python.exe"
$runs = @(
  @{ beta = "6.4002";  dir = "out/u2_2d/multi_lift_incov";   r = 10; tag = "A: in-coverage endpoint (model beta 61.7), ladder retherm" },
  @{ beta = "6.4002";  dir = "out/u2_2d/multi_lift_incov";   r = 0;  tag = "A0: same, PURE model composition" },
  @{ beta = "12.5129"; dir = "out/u2_2d/multi_lift_ceiling"; r = 10; tag = "B: endpoint +57% PAST the training ceiling, ladder retherm" },
  @{ beta = "12.5129"; dir = "out/u2_2d/multi_lift_ceiling"; r = 0;  tag = "B0: same, PURE model composition" }
)
foreach ($run in $runs) {
  Write-Output ("=" * 74)
  Write-Output ("[multi-lift] " + $run.tag + "  " + (Get-Date -Format HH:mm:ss))
  & $py -u u2_2d/scripts/45_multi_lift_compounding.py --device cuda `
      --start-size 8 --start-beta $run.beta --n-lifts 3 `
      --intermediate-retherm $run.r --out-dir $run.dir
  if ($LASTEXITCODE -ne 0) { Write-Output "[multi-lift] FAILED: $($run.tag)" }
}
Write-Output ("[multi-lift] all done " + (Get-Date -Format HH:mm:ss))
