# Regenerate everything that depended on the local-sweep repair tail.
#
# The tail is dropped: the delivered product becomes the raw lift, plus (in
# U(2) only) the conditional SU(2) heatbath, which GENERATES a sector the model
# does not produce and is not repair. All repair is left to HMC.
#
# WHAT IS NOT HERE, because it never used the tail and so does not change:
#   * the U(2) coverage scan and every improvement factor (28_crossover_scan.py
#     calls generate_fine_from_coarse, which stops after the SU(2) heatbath --
#     n_retherm_sweeps lives in generate_ladder, one level up)
#   * the U(1) volume scan, whose seed arm is explicitly the raw lift
#   * the U(1) coverage retrain, scored at record 0
#
# LADDER SIZE. The benchmarks take `generated[:n_chains]`, so only the first
# 16-64 configurations of each rung are ever used. Generating the deployed
# 1024 would be 8-64x waste; 128 leaves margin and takes the ladder phase from
# ~78 min to ~10.
#
# ORDER. Serial on purpose: concurrent CUDA contexts on this card time-slice
# rather than add throughput (measured: one 16-chain worker 1.49 s/traj, two
# 3.11 each, three 5.04 each). Cheap jobs first so failures surface early and
# partial results are in hand before the long one.

$ErrorActionPreference = "Stop"
$root = "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$py   = "$root\.venv\Scripts\python.exe"
Set-Location $root
$log = "$root\out\u2_2d\noretherm_campaign.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Step($name, $argv) {
    $t0 = Get-Date
    "[$((Get-Date).ToString('HH:mm:ss'))] START $name" | Tee-Object -Append $log
    & $py @argv 2>&1 | Tee-Object -Append $log
    if ($LASTEXITCODE -ne 0) {
        "[$((Get-Date).ToString('HH:mm:ss'))] FAILED $name (exit $LASTEXITCODE)" |
            Tee-Object -Append $log
        exit 1
    }
    $m = [int]((Get-Date) - $t0).TotalMinutes
    "[$((Get-Date).ToString('HH:mm:ss'))] DONE  $name  ($m min)" |
        Tee-Object -Append $log
}

"=== no-retherm campaign, started $(Get-Date) ===" | Tee-Object -Append $log

# --- ladders (everything below depends on these) ---------------------------
Step "ladder default (L=32, L=64)" @(
    "u2_2d\scripts\03_run_ladder.py",
    "--config", "u2_2d\configs\default_noretherm.yaml",
    "--n-configs", "128")

Step "ladder wide (L=32, L=64, L=128)" @(
    "u2_2d\scripts\03_run_ladder.py",
    "--config", "u2_2d\configs\wide_noretherm.yaml",
    "--n-configs", "128")

# --- U(1) entry cost, all five couplings -----------------------------------
Step "u1 entry cost" @(
    "u1_2d\scripts\14_diffusion_vs_instanton_hmc.py",
    "--config", "u1_2d\configs\v2_noretherm.yaml",
    "--out-dir", "out\u1_2d\diffusion_vs_instanton_noretherm")

# --- U(2) seed benchmarks, lifted arms only --------------------------------
# B, C, D, F, G start cold or hot and never touch the preconditioner, so they
# are unchanged and are reused from the existing runs at the same chain count.
Step "seed benchmark L=32 (rung 0), arms A,E,H" @(
    "u2_2d\scripts\08_hmc_seed_benchmark.py",
    "--config", "u2_2d\configs\default_noretherm.yaml",
    "--rung", "0", "--n-chains", "64",
    "--arms", "A_diffusion_seed,E_diffusion_plus_winding,H_diffusion_plus_odd_winding",
    "--out-dir", "out\u2_2d\seed_benchmark_rung0_noretherm")

Step "seed benchmark L=64 (top rung), arms A,E,H" @(
    "u2_2d\scripts\08_hmc_seed_benchmark.py",
    "--config", "u2_2d\configs\default_noretherm.yaml",
    "--rung", "-1", "--n-chains", "64",
    "--arms", "A_diffusion_seed,E_diffusion_plus_winding,H_diffusion_plus_odd_winding",
    "--out-dir", "out\u2_2d\seed_benchmark_noretherm")

# --- the long one: L=128 at 16 chains --------------------------------------
# 16 rather than 32 because a 32-chain batch has already left the launch-bound
# regime (4.14 s/traj against 1.75 at 16), so halving the chains is 2.4x
# cheaper rather than 2x. The cold arms D and G stay at 32 chains from the
# existing run; that asymmetry is deliberate and has to be disclosed if both
# end up in one table.
Step "seed benchmark L=128 (rung 2), arms A,H, 16 chains" @(
    "u2_2d\scripts\08_hmc_seed_benchmark.py",
    "--config", "u2_2d\configs\wide_noretherm.yaml",
    "--rung", "2", "--n-chains", "16",
    "--arms", "A_diffusion_seed,H_diffusion_plus_odd_winding",
    "--out-dir", "out\u2_2d\seed_benchmark_wide_L128_noretherm")

"=== campaign finished $(Get-Date) ===" | Tee-Object -Append $log
