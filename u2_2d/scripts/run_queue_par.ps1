# PARALLEL queue, 2026-08-21. Replaces the sequential run_queue_0821.ps1.
#
# WHY. The sequential version left the machine at 13% GPU / 28% CPU and, worse,
# put the 3.5 h capacity retrain LAST despite it depending on nothing but
# data_v2, which was already on disk. Wall clock was set by the sum of the
# stages rather than by the longest one.
#
# The dependency graph is almost entirely flat:
#
#   02a train ──► 02b ladder ──┬─► 02c validate
#                              ├─► 02d seed benchmark
#                              ├─► 02e prolongator L32
#                              └─► 02f prolongator L64
#   02a train ──► 02g density gap          (needs the checkpoint, not the ladder)
#   04 retherm, 05a/05b volume, 05c figures: independent of everything
#
# So phase A starts the long pole together with every independent stage, and
# phase B fans out behind the ladder. Wall clock becomes ~max(training, rest)
# plus the phase-B tail instead of the sum.
#
# CONCURRENCY. U(2) work here is kernel-launch bound (192 chains cost 9.8% more
# than 64), so several processes overlap well -- 5 concurrent shards previously
# took the GPU from 47% to 92%. Each process carries its own CUDA context
# (~200 MiB) and 8 GiB is ample.
#
# Sentinels under out/u2_2d/queue_0821/ are shared with the sequential script,
# so anything already finished is skipped.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_queue_par.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "out\u2_2d\queue_0821"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $state, $logs | Out-Null

$awake = Start-Process -FilePath "powershell" -PassThru -WindowStyle Hidden `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File", "u2_2d/scripts/keep_awake.ps1" `
    -WorkingDirectory $repo

# Launch one stage detached, returning a tracking object. NOT named $Args --
# that is a PowerShell automatic variable and splatting it silently launches
# python with no script at all, straight into the REPL.
function Start-Stage {
    param([string]$Name, [string[]]$StageArgs)
    $sentinel = Join-Path $state "$Name.done"
    if (Test-Path $sentinel) {
        Write-Host "[skip] $Name"
        return $null
    }
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
    $live = @($Stages | Where-Object { $_ -ne $null -and $_.PSObject.Properties.Name -contains "Proc" })
    if (-not $live.Count) { Write-Output "[$Phase] nothing to wait for"; return }
    Write-Output "[$Phase] waiting on $($live.Count) stage(s)"
    foreach ($s in $live) {
        $s.Proc.WaitForExit()
        $mins = [math]::Round(((Get-Date) - $s.Started).TotalMinutes, 1)
        if ($s.Proc.ExitCode -eq 0) {
            "ok" | Out-File -FilePath $s.Sentinel -Encoding utf8
            Write-Output "[done] $($s.Name)  ${mins} min"
        } else {
            Write-Output "[FAIL] $($s.Name)  exit $($s.Proc.ExitCode) after ${mins} min"
        }
    }
}

# ---------------- PHASE A: the long pole plus everything independent --------
$a = @()
# The 3.5 h retrain goes FIRST, not last. hidden 64->96, depth 4->5,
# batch 32->64, epochs 120->260, on the SAME data_v2 so any difference is
# attributable to capacity rather than to data.
$a += Start-Stage "02a_capacity_train" @(
    "-u", "u2_2d/scripts/02_train.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cuda")
$a += Start-Stage "04_retherm_scan" @(
    "-u", "u2_2d/scripts/33_retherm_scan.py", "--device", "cuda",
    # 32:105.651, not 32:105.244 -- data_v2 has no L=32 ensemble at 105.244, so
    # that case silently skipped. 105.651 is the ladder rung of record and
    # matches to fine beta 416.524 at L = 64.
    "--cases", "16:105.244,32:105.651", "--n-configs", "256",
    "--sampler-steps", "200", "--sweeps", "0,2,5,10,20,40,80")
# Volume scan. The four L=32 bases are chosen by MODEL BETA so the comparison
# isolates volume from training coverage: model 21.76 (the KNOWN BAD point,
# mid-gap between rungs 14 and 26), 44.90, 103.90 (the BEST point, 0.2% from the
# top rung) and 200.16 (past it, extrapolation). If the good/bad pattern
# reproduces at twice the volume then coverage, not volume, is the controlling
# variable.
$a += Start-Stage "05a_volume_plain" @(
    "-u", "u2_2d/scripts/28_crossover_scan.py", "--device", "cuda",
    "--data-dir", "out/u2_2d/data_v2", "--fine-size", "64",
    "--betas", "23.3695,46.4473,105.423,201.673",
    "--tag", "volume_L64_plain", "--out-dir", "out/u2_2d/crossover_L64")
$a += Start-Stage "05b_volume_winding" @(
    "-u", "u2_2d/scripts/28_crossover_scan.py", "--device", "cuda",
    "--data-dir", "out/u2_2d/data_v2", "--fine-size", "64",
    "--betas", "23.3695,46.4473,105.423,201.673",
    "--topological-updates", "--winding-charge-step", "1",
    "--winding-interval", "5",
    "--tag", "volume_L64_wind", "--out-dir", "out/u2_2d/crossover_L64")
$a += Start-Stage "05c_dissociation" @("-u", "u2_2d/scripts/32_dissociation.py")
# Re-run of the L=16 P(Q) test under the marginal move. It is the verdict that
# gates seed_exact_sectors and the ladder base, and beta 51.75 / 56 are the two
# couplings currently disqualified on a JOINT-proposal verdict.
$a += Start-Stage "03b_pq_marginal_L16" @(
    "-u", "u2_2d/scripts/07_pq_sampling.py", "--device", "cuda",
    "--lattice-size", "16", "--betas", "14,28,51.75,56",
    "--charge-step", "1", "--winding-interval", "5",
    "--out-dir", "out/u2_2d/pq_sampling_marginal_L16")
Wait-Stages $a "phase A"

# ---------------- PHASE B: everything behind the trained checkpoint ---------
$b1 = @()
$b1 += Start-Stage "02b_capacity_ladder" @(
    "-u", "u2_2d/scripts/03_run_ladder.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cuda")
# Density gap needs only the checkpoint, so it runs alongside the ladder.
$b1 += Start-Stage "02g_capacity_density" @(
    "-u", "u2_2d/scripts/18_density_gap.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--out-dir", "out/u2_2d/density_gap_cap")
Wait-Stages $b1 "phase B1"

$b2 = @()
$b2 += Start-Stage "02c_capacity_validate" @(
    "-u", "u2_2d/scripts/04_validate.py", "--config", "u2_2d/configs/capacity.yaml",
    "--device", "cpu")
$b2 += Start-Stage "02d_capacity_seedbench" @(
    "-u", "u2_2d/scripts/08_hmc_seed_benchmark.py",
    "--config", "u2_2d/configs/capacity.yaml", "--device", "cuda",
    "--out-dir", "out/u2_2d/seed_benchmark_cap")
# --n-retherm 0 with the four-arm set: the incumbent's protocol of record. At 10
# sweeps `halve` scores t_therm 0 while sitting 19% off pre-retherm, which is how
# the first v2 comparison was accidentally run against a different protocol.
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
Wait-Stages $b2 "phase B2"

# ---------------- PHASE C: scoring and figures ------------------------------
$c = @()
# --data-suffix v2 because the capacity experiment reuses data_v2 UNCHANGED, so
# its data-side criterion is v2's by construction rather than MISSING.
$c += Start-Stage "02h_capacity_report" @(
    "-u", "u2_2d/scripts/25_challenger_report.py",
    "--suffix", "cap", "--data-suffix", "v2")
$c += Start-Stage "06_figures" @("-u", "u2_2d/scripts/10_paper_figures.py")
$c += Start-Stage "07_lead_figure" @("-u", "u2_2d/scripts/30_seed_quality_figure.py")
Wait-Stages $c "phase C"

Write-Output ""
Write-Output "queue finished $(Get-Date -Format 'HH:mm:ss')"
Get-ChildItem $state -Filter *.done | ForEach-Object { Write-Output "  done: $($_.BaseName)" }
if ($awake -and -not $awake.HasExited) { Stop-Process -Id $awake.Id -Force }
