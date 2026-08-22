# The sector-distribution experiment, 2026-08-21.
#
# Two arms, identical but for the distribution the training data's topological
# charges were drawn from (exact P(Q) vs uniform over the same support). If they
# agree, `seed_exact_sectors` is a training-data convenience rather than the
# method's dependency on exact solvability -- which is what decides whether the
# construction transfers to 4D SU(3).
#
# THREE LESSONS FROM TODAY ARE BAKED IN:
#   1. At most THREE concurrent CUDA contexts on this 8 GiB card. Two OOM kills
#      were paid for that number. Each phase here runs two.
#   2. Never test a training run's completion on the exit code alone. On
#      2026-08-21 a run that finished all 260 epochs and printed its checkpoint
#      line was read as a failure, burned ten no-op retries and aborted the
#      queue. The real test is the script's own final `checkpoint: <path>` line.
#   3. Never let a dependent stage start behind a training that did not finish;
#      a ladder on a partial checkpoint produces a silently meaningless A/B.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_sector_experiment.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "out\u2_2d\sector_experiment\state"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $state, $logs | Out-Null

function Wait-For-Script {
    param([string]$Needle)
    while ($true) {
        $n = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
               Where-Object { $_.CommandLine -like "*$Needle*" }).Count
        if ($n -eq 0) { break }
        Start-Sleep -Seconds 60
    }
}

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
                              Log = $log; Started = Get-Date }
}

function Wait-Stages {
    param([object[]]$Stages, [string]$Phase, [string]$DoneMarker = $null)
    $live = @($Stages | Where-Object {
        $_ -ne $null -and $_.PSObject.Properties.Name -contains "Proc" })
    if (-not $live.Count) { Write-Host "[$Phase] nothing to wait for"; return $true }
    Write-Host "[$Phase] waiting on $($live.Count) stage(s)"
    $ok = $true
    foreach ($s in $live) {
        $s.Proc.WaitForExit()
        $mins = [math]::Round(((Get-Date) - $s.Started).TotalMinutes, 1)
        $done = $s.Proc.ExitCode -eq 0
        if (-not $done -and $DoneMarker) {
            $done = Select-String -Path $s.Log -Pattern $DoneMarker -Quiet -ErrorAction SilentlyContinue
        }
        if ($done) {
            "ok" | Out-File -FilePath $s.Sentinel -Encoding utf8
            Write-Host "[done] $($s.Name)  ${mins} min"
        } else {
            Write-Host "[FAIL] $($s.Name)  exit $($s.Proc.ExitCode) after ${mins} min"
            $ok = $false
        }
    }
    return $ok
}

Write-Host "[sector] waiting for the data build to finish $(Get-Date -Format 'HH:mm:ss')"
Wait-For-Script "39_sector_distribution_data"
Write-Host "[sector] data ready $(Get-Date -Format 'HH:mm:ss')"

# ---- PHASE 1: train both arms concurrently (2 CUDA contexts) ---------------
$p1 = @()
foreach ($arm in @("exact", "uniform")) {
    $p1 += Start-Stage "sector_train_$arm" @(
        "-u", "u2_2d/scripts/02_train.py",
        "--config", "u2_2d/configs/sector_$arm.yaml", "--device", "cuda")
}
if (-not (Wait-Stages $p1 "phase 1 (train)" '^checkpoint: ')) {
    Write-Host "[ABORT] a training arm did not finish; not running the ladder."
    exit 1
}

# ---- PHASE 2: ladder for each arm (2 CUDA contexts) ------------------------
$p2 = @()
foreach ($arm in @("exact", "uniform")) {
    $p2 += Start-Stage "sector_ladder_$arm" @(
        "-u", "u2_2d/scripts/03_run_ladder.py",
        "--config", "u2_2d/configs/sector_$arm.yaml", "--device", "cuda")
}
$null = Wait-Stages $p2 "phase 2 (ladder)"

# ---- PHASE 3: validate (cpu) + prolongator (cuda) --------------------------
$p3 = @()
foreach ($arm in @("exact", "uniform")) {
    $p3 += Start-Stage "sector_validate_$arm" @(
        "-u", "u2_2d/scripts/04_validate.py",
        "--config", "u2_2d/configs/sector_$arm.yaml", "--device", "cpu")
}
$null = Wait-Stages $p3 "phase 3a (validate)"

$p4 = @()
foreach ($arm in @("exact", "uniform")) {
    $p4 += Start-Stage "sector_prol_$arm" @(
        "-u", "u2_2d/scripts/17_prolongator_baseline.py",
        "--config", "u2_2d/configs/sector_$arm.yaml", "--device", "cuda",
        "--rung", "0", "--n-retherm", "0",
        "--arms", "ape", "smear", "diffusion_raw", "diffusion_tuned",
        "--out-dir", "out/u2_2d/prolongator_sector_$arm")
}
$null = Wait-Stages $p4 "phase 3b (prolongator)"

# ---- PHASE 4: the comparison ----------------------------------------------
$p5 = @()
$p5 += Start-Stage "sector_report" @("-u", "u2_2d/scripts/40_sector_experiment_report.py")
$null = Wait-Stages $p5 "phase 4 (report)"

Write-Host ""
Write-Host "[sector] finished $(Get-Date -Format 'HH:mm:ss')"
