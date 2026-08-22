# Restart of the capacity retrain and its dependants, 2026-08-21 12:55.
#
# WHY THIS REPLACES run_queue_par.ps1. The parallel queue put four CUDA contexts
# on an 8 GiB card -- the capacity retrain plus two L=64 crossover scans plus the
# L=16 P(Q) run -- and the retrain, which is the biggest of the four (hidden 96,
# depth 5, batch 64), died at epoch 36 with `CUDA error: out of memory`. It was
# the long pole and the only stage nothing else could substitute for, so the
# parallel queue killed exactly the wrong process.
#
# Worse, the original script would then have carried on into phase B and built a
# ladder, a validation and a seed benchmark on the epoch-36 checkpoint that
# happened to be lying on disk, and every number in the capacity A/B would have
# been produced by a quarter-trained net. Nothing in Wait-Stages made phase B
# conditional on phase A having SUCCEEDED. That is fixed here: phase B does not
# start unless training exits 0.
#
# THREE CHANGES:
#   1. Training auto-resumes. `resume: true` and `snapshot_every: 2` are now set
#      in capacity.yaml, so a crash costs at most two epochs instead of ten, and
#      the loop below simply restarts it. The snapshot carries the optimizer, the
#      EMA, the LR schedule and the history, so a resumed run is not a different
#      experiment.
#   2. expandable_segments:True. Most of these OOMs are fragmentation rather than
#      genuine exhaustion -- four contexts allocating different block sizes on the
#      same card. The expandable allocator is the standard remedy and costs
#      nothing when memory is plentiful.
#   3. Phase B is gated on the training sentinel.
#
# The two crossover scans and the L=16 P(Q) run are NOT restarted here -- they
# survived, are still running detached, and are making progress.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_queue_resume.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "out\u2_2d\queue_0821"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $state, $logs | Out-Null

$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

function Start-Stage {
    param([string]$Name, [string[]]$StageArgs)
    $sentinel = Join-Path $state "$Name.done"
    if (Test-Path $sentinel) { Write-Host "[skip] $Name"; return $null }
    $log = Join-Path $logs "q_$Name.log"
    $proc = Start-Process -FilePath $py -PassThru -WindowStyle Hidden `
        -WorkingDirectory $repo -ArgumentList $StageArgs `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    Write-Host "[run ] $Name  pid $($proc.Id)  $(Get-Date -Format 'HH:mm:ss')"
    return [pscustomobject]@{ Name = $Name; Proc = $proc; Sentinel = $sentinel
                              Started = Get-Date }
}

function Wait-Stages {
    param([object[]]$Stages, [string]$Phase)
    $live = @($Stages | Where-Object {
        $_ -ne $null -and $_.PSObject.Properties.Name -contains "Proc" })
    if (-not $live.Count) { Write-Host "[$Phase] nothing to wait for"; return $true }
    Write-Host "[$Phase] waiting on $($live.Count) stage(s)"
    $ok = $true
    foreach ($s in $live) {
        $s.Proc.WaitForExit()
        $mins = [math]::Round(((Get-Date) - $s.Started).TotalMinutes, 1)
        if ($s.Proc.ExitCode -eq 0) {
            "ok" | Out-File -FilePath $s.Sentinel -Encoding utf8
            Write-Host "[done] $($s.Name)  ${mins} min"
        } else {
            Write-Host "[FAIL] $($s.Name)  exit $($s.Proc.ExitCode) after ${mins} min"
            $ok = $false
        }
    }
    return $ok
}

# ---------------- TRAINING, with auto-resume on crash -----------------------
$trainSentinel = Join-Path $state "02a_capacity_train.done"
$attempt = 0
while (-not (Test-Path $trainSentinel) -and $attempt -lt 12) {
    $attempt++
    $log = Join-Path $logs "q_02a_capacity_train_r$attempt.log"
    $started = Get-Date
    Write-Host "[run ] 02a_capacity_train attempt $attempt  $($started.ToString('HH:mm:ss'))"
    $p = Start-Process -FilePath $py -PassThru -WindowStyle Hidden `
        -WorkingDirectory $repo -RedirectStandardOutput $log `
        -RedirectStandardError "$log.err" -ArgumentList @(
            "-u", "u2_2d/scripts/02_train.py",
            "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda")
    $p.WaitForExit()
    $mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
    # DO NOT trust the exit code alone. On 2026-08-21 attempt 2 completed all 260
    # epochs, printed its checkpoint line and left no traceback, and the loop
    # still read it as a failure -- then burned attempts 3..12 re-resuming from
    # epoch 260, running zero epochs each, and finally ABORTED without starting
    # phase B on a training run that had actually succeeded. The script's last
    # line is `checkpoint: <path>`, so its presence in the log is the real
    # completion test; the exit code is only a fallback.
    $finished = Select-String -Path $log -Pattern '^checkpoint: ' -Quiet -ErrorAction SilentlyContinue
    if ($p.ExitCode -eq 0 -or $finished) {
        "ok" | Out-File -FilePath $trainSentinel -Encoding utf8
        Write-Host "[done] 02a_capacity_train  ${mins} min (attempt $attempt)"
    } else {
        Write-Host "[retry] 02a_capacity_train exit $($p.ExitCode) after ${mins} min -- resuming in 60 s"
        Start-Sleep -Seconds 60
    }
}

if (-not (Test-Path $trainSentinel)) {
    Write-Host "[ABORT] training did not complete in $attempt attempts."
    Write-Host "        Phase B is NOT started: a ladder, validation and seed"
    Write-Host "        benchmark built on a partial checkpoint would silently"
    Write-Host "        produce a capacity A/B for a net that was never trained."
    exit 1
}

# ---------------- PHASE B: everything behind the trained checkpoint ---------
$b1 = @()
$b1 += Start-Stage "02b_capacity_ladder" @(
    "-u", "u2_2d/scripts/03_run_ladder.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cuda")
$b1 += Start-Stage "02g_capacity_density" @(
    "-u", "u2_2d/scripts/18_density_gap.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--out-dir", "out/u2_2d/density_gap_cap")
$null = Wait-Stages $b1 "phase B1"

$b2 = @()
$b2 += Start-Stage "02c_capacity_validate" @(
    "-u", "u2_2d/scripts/04_validate.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cpu")
$b2 += Start-Stage "02d_capacity_seedbench" @(
    "-u", "u2_2d/scripts/08_hmc_seed_benchmark.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--out-dir", "out/u2_2d/seed_benchmark_cap")
$b2 += Start-Stage "02e_capacity_prol_L32" @(
    "-u", "u2_2d/scripts/17_prolongator_baseline.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--rung", "0", "--n-retherm", "0",
    "--arms", "ape", "smear", "diffusion_raw", "diffusion_tuned",
    "--out-dir", "out/u2_2d/prolongator_L32_cap_matched")
$b2 += Start-Stage "02f_capacity_prol_L64" @(
    "-u", "u2_2d/scripts/17_prolongator_baseline.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--rung", "-1", "--n-retherm", "0",
    "--arms", "ape", "smear", "diffusion_raw", "diffusion_tuned",
    "--out-dir", "out/u2_2d/prolongator_L64_cap_matched")
$null = Wait-Stages $b2 "phase B2"

# ---------------- PHASE C: scoring and figures ------------------------------
$c = @()
$c += Start-Stage "02h_capacity_report" @(
    "-u", "u2_2d/scripts/25_challenger_report.py",
    "--suffix", "cap", "--data-suffix", "v2")
$c += Start-Stage "06_figures" @("-u", "u2_2d/scripts/10_paper_figures.py")
$c += Start-Stage "07_lead_figure" @("-u", "u2_2d/scripts/30_seed_quality_figure.py")
$null = Wait-Stages $c "phase C"

Write-Host ""
Write-Host "queue finished $(Get-Date -Format 'HH:mm:ss')"
Get-ChildItem $state -Filter *.done | ForEach-Object { Write-Host "  done: $($_.BaseName)" }
