<#
.SYNOPSIS
    Full challenger pipeline: regenerate training data on the u1-style schedule,
    retrain, and rebuild every downstream result and figure.

.DESCRIPTION
    WHAT THIS IS. The u2 score net was trained on 12 fixed couplings. u1 trains on
    ~102 log-uniform draws across three volumes plus charged-sector augmentation
    and a heldout coupling, and that structure is what carried its generalization
    results. This queue ports it: 114 rungs, 28928 configs, betas 3.5 to 416.5 at
    L = 8, 16, 32 (+ the L = 64 reference), sector_augment on the six fixed
    high-beta rungs, one heldout coupling at beta = 80.

    NOTHING OF RECORD IS OVERWRITTEN. Everything runs against configs/v2.yaml,
    whose only difference from default.yaml is output paths:

        data       out/u2_2d/data_v2
        checkpoint out/u2_2d/checkpoints/det_score_net_v2.pt
        ladder     out/u2_2d/ladder_v2
        validation out/u2_2d/validation_v2

    The incumbent det_score_net.pt and its directories survive, so the challenger
    has to EARN deployment against the four criteria in stage zz_compare. This
    matters: the 2026-08-20 coverage retrain improved L = 64 extended loops and
    regressed L = 32, the density gap and seed quality, and that was only visible
    because the incumbent was still there to compare against.

    Every stage is skipped if its sentinel exists, so a kill resumes rather than
    restarts.

      powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_overnight.ps1
#>
$ErrorActionPreference = "Continue"

# ABSOLUTE PATHS THROUGHOUT -- see run_fixes.ps1 for why a relative python path
# is a terminating error under a detached launch.
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
if (-not (Test-Path $py)) { Write-Host "FATAL: no python at $py"; exit 1 }

$lock = Join-Path $logs "run_overnight.lock"
if (Test-Path $lock) {
    $old = (Get-Content $lock -ErrorAction SilentlyContinue | Select-Object -First 1)
    $alive = $null
    if ($old) { $alive = Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue }
    if ($alive) { Write-Host "another queue is running (pid $old); exiting"; exit 0 }
    Write-Host "clearing stale lock from pid $old"
}
Set-Content -Path $lock -Value $PID -Encoding utf8
Start-Transcript -Path (Join-Path $logs "run_overnight.log") -Force | Out-Null

Write-Host "repo   $repo"
Write-Host "pid    $PID"
Write-Host "start  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

$awake = Start-Process powershell -PassThru -WindowStyle Hidden `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File",
                  (Join-Path $repo "u2_2d\scripts\keep_awake.ps1")

$CFG = "u2_2d\configs\v2.yaml"

function Stage {
    param([string]$Name, [string]$Sentinel, [string[]]$Cmd)
    if ($Sentinel) { $Sentinel = Join-Path $repo $Sentinel }
    if ($Sentinel -and (Test-Path $Sentinel)) {
        Write-Host "[skip] $Name  (found $Sentinel)"; return
    }
    Write-Host ""
    Write-Host "=== $Name  $(Get-Date -Format 'HH:mm:ss') ==="
    $log = Join-Path $logs "ov_$Name.log"
    $Cmd[0] = Join-Path $repo $Cmd[0]
    $t0 = Get-Date
    & $py @Cmd *> $log
    $code = $LASTEXITCODE
    $el = (Get-Date) - $t0
    if ($code -eq 0) {
        Write-Host ("[ok]   {0}  {1:hh\:mm\:ss}  -> {2}" -f $Name, $el, $log)
    } else {
        Write-Host ("[FAIL] {0}  exit {1}  {2:hh\:mm\:ss}  -> {3}" -f $Name, $code, $el, $log)
    }
}

# ---------------------------------------------------------------------------
# 1. DATA. Sharded across CPU and GPU concurrently; the device split is measured
#    (see run_stage01.ps1). L=8 to CPU where the GPU is 2x slower, L=16/32 to the
#    GPU across 4 contexts, and the single L=64 reference gets its own GPU shard
#    so it is not stuck behind 100 small rungs.
# ---------------------------------------------------------------------------
if (Test-Path (Join-Path $repo "out\u2_2d\data_v2\summary.json")) {
    Write-Host "[skip] stage01  (found data_v2\summary.json)"
} else {
    Write-Host ""
    Write-Host "=== stage01_data  $(Get-Date -Format 'HH:mm:ss') ==="
    $t0 = Get-Date
    # RELATIVE, deliberately. Start-Process -ArgumentList joins the array on
    # spaces and re-splits it, so an absolute path through "Lattice QCD" arrives
    # as two arguments and python opens 'C:\Users\ompan\Desktop\Lattice'. The
    # working directory is already $repo (Set-Location above), so a relative path
    # sidesteps the whole quoting problem -- which is what run_stage01.ps1 does.
    # `& $py @Cmd` in Stage() splats properly and is not affected.
    $script = "u2_2d\scripts\01_generate_data.py"
    $env:U2_2D_TORCH_THREADS = "1"
    $env:PYTHONUNBUFFERED = "1"
    $jobs = @()
    foreach ($i in 0..2) {
        $log = Join-Path $logs "ov_stage01_cpu$i.log"
        $p = Start-Process -FilePath $py -PassThru -NoNewWindow -WorkingDirectory $repo `
            -ArgumentList $script, "--config", $CFG, "--only-sizes", "8",
                          "--shard", "$i/3", "--device", "cpu" `
            -RedirectStandardOutput $log -RedirectStandardError "$log.err"
        # Touching .Handle caches the handle; without it ExitCode reads $null
        # after exit and every shard looks like a failure.
        $null = $p.Handle
        $jobs += [pscustomobject]@{ Name = "cpu$i"; Process = $p }
    }
    foreach ($i in 0..5) {
        $log = Join-Path $logs "ov_stage01_gpu$i.log"
        $p = Start-Process -FilePath $py -PassThru -NoNewWindow -WorkingDirectory $repo `
            -ArgumentList $script, "--config", $CFG, "--only-sizes", "16,32",
                          "--shard", "$i/6", "--device", "cuda" `
            -RedirectStandardOutput $log -RedirectStandardError "$log.err"
        $null = $p.Handle
        $jobs += [pscustomobject]@{ Name = "gpu$i"; Process = $p }
    }
    $log64 = Join-Path $logs "ov_stage01_gpu64.log"
    $p64 = Start-Process -FilePath $py -PassThru -NoNewWindow -WorkingDirectory $repo `
        -ArgumentList $script, "--config", $CFG, "--only-sizes", "64",
                      "--shard", "0/1", "--device", "cuda" `
        -RedirectStandardOutput $log64 -RedirectStandardError "$log64.err"
    $null = $p64.Handle
    $jobs += [pscustomobject]@{ Name = "gpu64"; Process = $p64 }

    Write-Host "launched $($jobs.Count) shards"
    foreach ($j in $jobs) { Write-Host ("  {0,-6} pid {1}" -f $j.Name, $j.Process.Id) }
    foreach ($j in $jobs) { $j.Process.WaitForExit() }
    foreach ($j in $jobs) { Write-Host ("  {0,-6} exit {1}" -f $j.Name, $j.Process.ExitCode) }
    $failed = @($jobs | Where-Object { $_.Process.ExitCode -ne 0 })
    if ($failed.Count -gt 0) {
        Write-Host "FAILED shards: $($failed.Name -join ', ') -- NOT merging, queue stops"
        Stop-Transcript | Out-Null
        if ($awake) { Stop-Process -Id $awake.Id -Force -ErrorAction SilentlyContinue }
        Remove-Item $lock -Force -ErrorAction SilentlyContinue
        exit 1
    }
    & $py $script --config $CFG --merge-shards *> (Join-Path $logs "ov_stage01_merge.log")
    Write-Host ("[ok]   stage01_data  {0:hh\:mm\:ss}" -f ((Get-Date) - $t0))
}

# ---------------------------------------------------------------------------
# 2. TRAIN the challenger.
# ---------------------------------------------------------------------------
Stage "stage02_train" "out\u2_2d\checkpoints\det_score_net_v2.pt" @(
    "u2_2d\scripts\02_train.py", "--config", $CFG, "--device", "cuda")

# ---------------------------------------------------------------------------
# 3-4. LADDER and VALIDATION on the challenger.
# ---------------------------------------------------------------------------
Stage "stage03_ladder" "out\u2_2d\ladder_v2\summary.json" @(
    "u2_2d\scripts\03_run_ladder.py", "--config", $CFG, "--device", "cuda")

Stage "stage04_validate" "out\u2_2d\validation_v2\report.md" @(
    "u2_2d\scripts\04_validate.py", "--config", $CFG, "--device", "cpu")

# ---------------------------------------------------------------------------
# 5. THE FOUR ACCEPTANCE CRITERIA, each measured on the challenger against the
#    incumbent's recorded number. Declared before the run, not after it.
#      (a) <Q^2> at the top rung  -- the reason for the retrain
#      (b) seed quality           -- what the coverage retrain broke
#      (c) L=32 extended loops    -- the other thing it broke
#      (d) density gap            -- ditto
# ---------------------------------------------------------------------------
Stage "stage08_seed_benchmark" "out\u2_2d\seed_benchmark_v2\seed_benchmark.json" @(
    "u2_2d\scripts\08_hmc_seed_benchmark.py", "--config", $CFG, "--device", "cuda",
    "--out-dir", "out\u2_2d\seed_benchmark_v2")

Stage "stage17_prolongator_L32" "out\u2_2d\prolongator_L32_v2\report.md" @(
    "u2_2d\scripts\17_prolongator_baseline.py", "--config", $CFG, "--device", "cuda",
    "--rung", "0", "--n-traj", "400", "--n-chains", "64",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_v2.pt",
    "--out-dir", "out\u2_2d\prolongator_L32_v2")

Stage "stage17_prolongator_L64" "out\u2_2d\prolongator_L64_v2\report.md" @(
    "u2_2d\scripts\17_prolongator_baseline.py", "--config", $CFG, "--device", "cuda",
    "--rung", "1", "--n-traj", "400", "--n-chains", "64",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_v2.pt",
    "--out-dir", "out\u2_2d\prolongator_L64_v2")

Stage "stage21_prolongator_obs" "out\u2_2d\prolongator_observables_v2\report.md" @(
    "u2_2d\scripts\21_prolongator_observables.py", "--config", $CFG, "--device", "cuda",
    "--out-dir", "out\u2_2d\prolongator_observables_v2")

Stage "stage18_density_gap" "out\u2_2d\density_gap_v2\density_gap.json" @(
    "u2_2d\scripts\18_density_gap.py", "--config", $CFG, "--device", "cuda",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_v2.pt",
    "--out-dir", "out\u2_2d\density_gap_v2")

# ---------------------------------------------------------------------------
# 6. FIGURES and reports, on the challenger. These go to figures_v2 so the
#    figures of record are untouched until the challenger is accepted.
# ---------------------------------------------------------------------------
Stage "stage06_figures" "" @(
    "u2_2d\scripts\06_figures.py", "--config", $CFG,
    "--out-dir", "out\u2_2d\figures_v2")

Stage "stage22_distributions" "" @(
    "u2_2d\scripts\22_distribution_figures.py", "--config", $CFG, "--device", "cuda",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_v2.pt",
    "--out-dir", "out\u2_2d\figures_v2")

Stage "stage10_paper_figures" "" @(
    "u2_2d\scripts\10_paper_figures.py", "--out-dir", "out\u2_2d\figures_v2")

Stage "stage16_cost_figures" "" @(
    "u2_2d\scripts\16_cost_figures.py", "--out-dir", "out\u2_2d\figures_v2")

Stage "stage20_prolongator_fig" "" @(
    "u2_2d\scripts\20_prolongator_figure.py",
    "--source", "out\u2_2d\prolongator_L64_v2",
    "--out", "out\u2_2d\figures_v2\fig15_prolongator.png")

# ---------------------------------------------------------------------------
# 7. IDENTITIES must still pass -- winding_interval touched the HMC step -- and
#    then the A/B verdict against the four criteria.
# ---------------------------------------------------------------------------
Stage "stage09_identities" "" @("u2_2d\scripts\09_verify_identities.py")

# 15 has no --config; it takes the coupling directly. This re-runs the parity
# mobility count under charge_step = 1, which is what makes fig09 a statement
# about the move now in use rather than the superseded joint proposal.
Stage "stage15_base_parity" "out\u2_2d\base_parity_v2\base_parity.json" @(
    "u2_2d\scripts\15_base_parity.py", "--device", "cuda",
    "--lattice-size", "16", "--betas", "14,21,28",
    "--out-dir", "out\u2_2d\base_parity_v2")

Stage "zz_compare" "" @("u2_2d\scripts\25_challenger_report.py")

Write-Host ""
Write-Host "queue finished $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Stop-Transcript | Out-Null
if ($awake) { Stop-Process -Id $awake.Id -Force -ErrorAction SilentlyContinue }
Remove-Item $lock -Force -ErrorAction SilentlyContinue
