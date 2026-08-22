# Queue for the five outstanding items, 2026-08-21.
#
# Ordering rationale: the capacity retrain (item 2) is the long pole and owns the
# GPU for hours, and items 3-5 are cheap. So the cheap items run FIRST and
# finish inside the first hour; the retrain then runs alone with the machine to
# itself, and its dependent scoring runs after it.
#
# Every stage writes a sentinel under out/u2_2d/queue_0821/. Re-running the
# script skips completed stages, so a crash or a reboot resumes rather than
# restarting. Delete a sentinel to force one stage to re-run.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_queue_0821.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "out\u2_2d\queue_0821"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $state, $logs | Out-Null

# Hold the machine awake for the duration; releases when this process exits.
$awake = Start-Process -FilePath "powershell" -PassThru -WindowStyle Hidden `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File", "u2_2d/scripts/keep_awake.ps1" `
    -WorkingDirectory $repo

function Invoke-Stage {
    # NOT $Args -- that is a PowerShell automatic variable and
    # splatting it silently launches python with no script.
    param([string]$Name, [string[]]$StageArgs)
    $sentinel = Join-Path $state "$Name.done"
    if (Test-Path $sentinel) {
        Write-Output "[skip] $Name (sentinel present)"
        return
    }
    $log = Join-Path $logs "q_$Name.log"
    $started = Get-Date
    Write-Output "[run ] $Name  $($started.ToString('HH:mm:ss'))"
    & $py @StageArgs *>&1 | Out-File -FilePath $log -Encoding utf8
    $code = $LASTEXITCODE
    $mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
    if ($code -eq 0) {
        "ok $($started.ToString('s'))" | Out-File -FilePath $sentinel -Encoding utf8
        Write-Output "[done] $Name  ${mins} min"
    } else {
        Write-Output "[FAIL] $Name  exit $code after ${mins} min -- see $log"
    }
}

# ---- 1. u1 PRE/POST, recomputed with tau_int-aware error bars ---------------
# The naive across-configuration sem inflated |z|; u1's convention is per-chain
# tau_int (NARRATIVE 25.7 / review item M4). Same run, corrected denominator.
Invoke-Stage "01_u1_pre_post" @(
    "-u", "u1_2d/scripts/59_pre_post_retherm.py",
    "--device", "cuda", "--coarse-betas", "14.1464,55.0237",
    "--n-configs", "256", "--n-chains", "16", "--burn-in", "800",
    "--sampler-steps", "200", "--sweeps", "0,2,5,10,20,40")

# ---- 3. P(Q) sampling under the MARGINAL move -------------------------------
# Every PARITY-STUCK verdict on record was measured with the retired joint
# proposal, and those verdicts gate seed_exact_sectors and the ladder base.
# Both volumes, and the couplings the old verdicts ruled out (51.75, 56).
Invoke-Stage "03a_pq_marginal_L8" @(
    "-u", "u2_2d/scripts/07_pq_sampling.py", "--device", "cuda",
    "--lattice-size", "8", "--betas", "6,10,14,20",
    "--charge-step", "1", "--winding-interval", "5",
    "--out-dir", "out/u2_2d/pq_sampling_marginal_L8")
Invoke-Stage "03b_pq_marginal_L16" @(
    "-u", "u2_2d/scripts/07_pq_sampling.py", "--device", "cuda",
    "--lattice-size", "16", "--betas", "14,28,51.75,56",
    "--charge-step", "1", "--winding-interval", "5",
    "--out-dir", "out/u2_2d/pq_sampling_marginal_L16")

# ---- 4. n_retherm scan, scored on the WORST scale ---------------------------
# Both volumes, because the u1/u2 difference in whether the tail damages the
# infrared may be a volume effect as much as a coupling one.
Invoke-Stage "04_retherm_scan" @(
    "-u", "u2_2d/scripts/33_retherm_scan.py", "--device", "cuda",
    "--cases", "16:105.244,32:105.244", "--n-configs", "256",
    "--sampler-steps", "200", "--sweeps", "0,2,5,10,20,40,80")

# ---- 5a. Volume scan: does the seed's advantage survive L = 32 -> 64? -------
# data_v2 holds 40 L=32 ensembles, so no base generation is needed.
#
# The four bases are chosen by MODEL BETA, not by fine beta, so the comparison
# isolates volume from training coverage -- which the L=32 scan showed is what
# actually governs seed quality. Each matches an L=32-scan point closely:
#     L32   8.376 -> L64 beta_f  25.3, model 6.35   (vs 6.18  at L_f=32)
#     L32  23.370 -> L64 beta_f  87.0, model 21.76  (vs 22.19 -- the KNOWN BAD
#                                       point, mid-gap between rungs 14 and 26)
#     L32  46.447 -> L64 beta_f 179.6, model 44.90  (vs 45.90)
#     L32 105.423 -> L64 beta_f 415.6, model 103.90 (vs 103.73 -- the BEST
#                                       point, 0.2% from the top training rung)
# If the good/bad pattern reproduces at twice the volume, coverage rather than
# volume is confirmed as the controlling variable. If it does not, volume is a
# separate effect and the L=32 conclusion does not transfer.
Invoke-Stage "05a_volume_plain" @(
    "-u", "u2_2d/scripts/28_crossover_scan.py", "--device", "cuda",
    "--data-dir", "out/u2_2d/data_v2", "--fine-size", "64",
    "--betas", "8.376,23.3695,46.4473,105.423",
    "--tag", "volume_L64_plain", "--out-dir", "out/u2_2d/crossover_L64")
Invoke-Stage "05b_volume_winding" @(
    "-u", "u2_2d/scripts/28_crossover_scan.py", "--device", "cuda",
    "--data-dir", "out/u2_2d/data_v2", "--fine-size", "64",
    "--betas", "8.376,23.3695,46.4473,105.423",
    "--topological-updates", "--winding-charge-step", "1",
    "--winding-interval", "5",
    "--tag", "volume_L64_wind", "--out-dir", "out/u2_2d/crossover_L64")

# ---- 5c. The two figures that need no new compute ---------------------------
Invoke-Stage "05c_dissociation" @("-u", "u2_2d/scripts/32_dissociation.py")

# ---- 2. THE CAPACITY EXPERIMENT (the long pole) -----------------------------
# hidden 64->96, depth 4->5, batch 32->64, epochs 120->260, on the SAME data_v2.
# Nothing else changes, so a difference is attributable to capacity rather than
# to data -- which is the whole point, since both previous coverage attempts
# changed the data and regressed.
Invoke-Stage "02a_capacity_train" @(
    "-u", "u2_2d/scripts/02_train.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cuda")
Invoke-Stage "02b_capacity_ladder" @(
    "-u", "u2_2d/scripts/03_run_ladder.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cuda")
Invoke-Stage "02c_capacity_validate" @(
    "-u", "u2_2d/scripts/04_validate.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cpu")
# The A/B against the incumbent. Four criteria; a MISSING criterion returns
# INCOMPLETE rather than a verdict.
# The three GUARDS v2 failed. These are the criteria the capacity experiment
# exists to recover, so they are the ones that must be measured, and each has to
# be run on the SAME protocol the incumbent's record used or the comparison is
# between protocols rather than between checkpoints.
Invoke-Stage "02d_capacity_seedbench" @(
    "-u", "u2_2d/scripts/08_hmc_seed_benchmark.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--out-dir", "out/u2_2d/seed_benchmark_cap")
# n-retherm 0 and the four-arm set: this is the incumbent's protocol of record.
# At 10 retherm sweeps `halve` scores t_therm 0 while sitting 19% off
# pre-retherm, which is how the first v2 comparison was accidentally run.
Invoke-Stage "02e_capacity_prol_L32" @(
    "-u", "u2_2d/scripts/17_prolongator_baseline.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--rung", "0", "--n-retherm", "0",
    "--arms", "ape", "smear", "diffusion_raw", "diffusion_tuned",
    "--out-dir", "out/u2_2d/prolongator_L32_cap_matched")
Invoke-Stage "02f_capacity_prol_L64" @(
    "-u", "u2_2d/scripts/17_prolongator_baseline.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--rung", "-1", "--n-retherm", "0",
    "--arms", "ape", "smear", "diffusion_raw", "diffusion_tuned",
    "--out-dir", "out/u2_2d/prolongator_L64_cap_matched")
Invoke-Stage "02g_capacity_density" @(
    "-u", "u2_2d/scripts/18_density_gap.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--out-dir", "out/u2_2d/density_gap_cap")
# --data-suffix v2 because the capacity experiment reuses data_v2 UNCHANGED;
# its data-side criterion is v2's, by construction, and should say so.
Invoke-Stage "02h_capacity_report" @(
    "-u", "u2_2d/scripts/25_challenger_report.py",
    "--suffix", "cap", "--data-suffix", "v2")

# ---- final: regenerate the figure set on whatever is deployed ---------------
Invoke-Stage "06_figures" @("-u", "u2_2d/scripts/10_paper_figures.py")
Invoke-Stage "07_lead_figure" @("-u", "u2_2d/scripts/30_seed_quality_figure.py")

Write-Output ""
Write-Output "queue finished $(Get-Date -Format 'HH:mm:ss')"
Get-ChildItem $state -Filter *.done | ForEach-Object { Write-Output "  done: $($_.BaseName)" }
if ($awake -and -not $awake.HasExited) { Stop-Process -Id $awake.Id -Force }
