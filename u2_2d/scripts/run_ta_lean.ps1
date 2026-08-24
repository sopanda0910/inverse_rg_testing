# Lean thermalization / autocorrelation package (2026-08-24, second cut).
#
# Changes from the first attempt, all measured rather than guessed:
#  * 300 trajectories, not 2000. Measured tau_int(plaq) = 3.3-3.9 and
#    tau_int(Q^2) = 4.9-5.2 at the top rung, so a 150-trajectory tail on each of
#    64 chains is ~30-45 tau per chain and ~2000-2900 tau in total. 2000 was
#    ~500 tau per chain: no extra resolution, 6x the wall clock.
#  * 4 arms locally, 3 with winding. `ape` and `flux` are dropped: 17's table
#    already records both as > 400 trajectories at this rung, and re-measuring a
#    known non-converger costs the same as measuring a real competitor.
#  * The real cost is `measure()` -- W(8x8) on 64 chains at L=64 EVERY
#    trajectory -- not the HMC. Measured throughput was ~0.35 traj/s against the
#    ~5 traj/s CLAUDE.md quotes for bare HMC, so the observable set, not the
#    sampler, sets the budget here.
$ErrorActionPreference = "Continue"
$py = ".venv/Scripts/python.exe"
$local = @("diffusion_raw","diffusion_tuned","smear","cold")
# diffusion_tuned MUST be here: it is the matched-budget arm. `smear` carries 15
# tuned sweeps and `diffusion_raw` carries none, so a round without
# diffusion_tuned compares unlike things and cannot answer whether the LIFT
# matters as opposed to the repair. Dropping it to save wall clock was a mistake
# the first time; it is the one arm the ablation cannot do without.
$topo  = @("diffusion_raw","diffusion_tuned","smear","cold")

function Run-Pair($rung, $tag) {
  $a = Start-Process -PassThru -NoNewWindow -FilePath $py -ArgumentList (@(
    "u2_2d/scripts/50_therm_autocorr.py","--rung",$rung,"--arms") + $local + @(
    "--n-traj","300","--n-chains","64","--out-dir","out/u2_2d/ta_${tag}_local")
  ) -RedirectStandardOutput "out/u2_2d/log_ta_${tag}_local.log" -RedirectStandardError "out/u2_2d/log_ta_${tag}_local.err"
  $b = Start-Process -PassThru -NoNewWindow -FilePath $py -ArgumentList (@(
    "u2_2d/scripts/50_therm_autocorr.py","--rung",$rung,"--winding","--arms") + $topo + @(
    "--n-traj","300","--n-chains","64","--out-dir","out/u2_2d/ta_${tag}_topo")
  ) -RedirectStandardOutput "out/u2_2d/log_ta_${tag}_topo.log" -RedirectStandardError "out/u2_2d/log_ta_${tag}_topo.err"
  Wait-Process -Id $a.Id, $b.Id
}

Write-Host "=== L=64 pair start $(Get-Date -Format HH:mm:ss) ==="
Run-Pair "-1" "L64"
Write-Host "=== L=32 pair start $(Get-Date -Format HH:mm:ss) ==="
Run-Pair "0" "L32"
Write-Host "=== tuned-sweep stability $(Get-Date -Format HH:mm:ss) ==="
& $py u2_2d/scripts/52_tuned_sweep_stability.py --seeds 0 1 2 3 4 --rung -1 2>&1
Write-Host "=== ALL DONE $(Get-Date -Format HH:mm:ss) ==="
