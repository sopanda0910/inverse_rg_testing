# Wave 1: top rung (L=64, beta=416.524). Two processes, run concurrently.
#
# THE COST DECOMPOSITION THAT SETS THIS SHAPE. On this GPU u2 HMC is
# kernel-launch-bound and FLAT at ~5 traj/s from L=16 to L=64 (CLAUDE.md), i.e.
# ~205 ms/trajectory, while the marginal odd winding move costs ~1609 ms -- 8x
# a plain trajectory. So the winding move, not the chain length, is the budget.
#
# It is also only needed for HALF the measurements: tau_int(Q^2), parity flips
# and the freezing contrast are topological, while t_therm, the dispersion audit
# and tau_int of local observables are not. Paying 8x on all six arms to measure
# quantities that do not use the move was the actual waste.
#
#   local  : 6 arms, NO winding, 600 traj  -> ~0.25 s/traj
#   topo   : 3 arms, winding,    400 traj  -> ~0.53 s/traj
$ErrorActionPreference = "Continue"
$py = ".venv/Scripts/python.exe"

$local = Start-Process -PassThru -NoNewWindow -FilePath $py -ArgumentList @(
  "u2_2d/scripts/50_therm_autocorr.py","--rung","-1",
  "--arms","diffusion_raw","diffusion_tuned","smear","ape","flux","cold",
  "--n-traj","600","--n-chains","64",
  "--out-dir","out/u2_2d/therm_autocorr_L64_local"
) -RedirectStandardOutput out/u2_2d/log_ta_L64_local.log -RedirectStandardError out/u2_2d/log_ta_L64_local.err

$topo = Start-Process -PassThru -NoNewWindow -FilePath $py -ArgumentList @(
  "u2_2d/scripts/50_therm_autocorr.py","--rung","-1","--winding",
  "--arms","diffusion_raw","smear","cold",
  "--n-traj","400","--n-chains","64",
  "--out-dir","out/u2_2d/therm_autocorr_L64_topo"
) -RedirectStandardOutput out/u2_2d/log_ta_L64_topo.log -RedirectStandardError out/u2_2d/log_ta_L64_topo.err

Wait-Process -Id $local.Id, $topo.Id
Write-Host "=== WAVE 1 DONE ==="
