# Unattended queue for the five U(2) publication gaps.
#
# Everything is sequential, logged per stage under out/u2_2d/logs/, and SKIPS a
# stage whose output already exists -- so this can be re-run after a kill and it
# resumes rather than restarting. Nothing here overwrites a result of record:
# the retrained checkpoint, its ladder and its validation all go to parallel
# `_cov` paths, so the A/B comparison survives and the deployed artifacts stay
# exactly as they were.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_fixes.ps1
#
# Hold the machine awake for the duration; keep_awake releases on exit, so
# there is no global setting left behind.

$ErrorActionPreference = "Continue"

# ABSOLUTE PATHS THROUGHOUT. Launched from Task Scheduler the process working
# directory is not the repo, and a relative `.venv\Scripts\python.exe` then
# raises CommandNotFoundException -- which is terminating for `&`, so the queue
# dies on its first stage with an empty log while the task reports 0x80070002.
# Deriving the root from $PSScriptRoot removes the whole class of failure.
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (-not (Test-Path $py)) { Write-Host "FATAL: no python at $py"; exit 1 }

# SINGLE INSTANCE, enforced here rather than trusted to the scheduler. Task
# Scheduler's MultipleInstances setting does not see a queue started by hand,
# and two copies of this script run the same stage against the same output file
# -- which nearly corrupted the beta = 14 ensemble on 2026-08-20. The lock holds
# the PID; a lock whose process is gone is stale and gets taken over.
$lock = Join-Path $logs "run_fixes.lock"
if (Test-Path $lock) {
    $old = (Get-Content $lock -ErrorAction SilentlyContinue | Select-Object -First 1)
    $alive = $null
    if ($old) { $alive = Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue }
    if ($alive) {
        Write-Host "another queue is running (pid $old); exiting"
        exit 0
    }
    Write-Host "clearing stale lock from pid $old"
}
Set-Content -Path $lock -Value $PID -Encoding utf8

# Queue-level output goes to a file too. Under the scheduler there is no console
# to read, and the per-stage logs alone cannot say which stage was skipped.
Start-Transcript -Path (Join-Path $logs "run_fixes.log") -Force | Out-Null

Write-Host "repo   $repo"
Write-Host "python $py"
Write-Host "pid    $PID"

$awake = Start-Process powershell -PassThru -WindowStyle Hidden `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File",
                  (Join-Path $repo "u2_2d\scripts\keep_awake.ps1")

function Stage {
    param([string]$Name, [string]$Sentinel, [string[]]$Cmd, [string]$Touch)
    if ($Sentinel) { $Sentinel = Join-Path $repo $Sentinel }
    if ($Touch) { $Touch = Join-Path $repo $Touch }
    if ($Sentinel -and (Test-Path $Sentinel)) {
        Write-Host "[skip] $Name  (found $Sentinel)"
        return
    }
    Write-Host ""
    Write-Host "=== $Name  $(Get-Date -Format 'HH:mm:ss') ==="
    $log = Join-Path $logs "$Name.log"
    $Cmd[0] = Join-Path $repo $Cmd[0]
    & $py @Cmd *> $log
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host "[ok]   $Name  ->  $log"
        if ($Touch) { New-Item -ItemType File -Force -Path $Touch | Out-Null }
    } else {
        Write-Host "[FAIL] $Name  exit $code  ->  $log"
    }
}

# ---------------------------------------------------------------------------
# 0. Wait for the top-rung prolongator run already in flight. Both want the same
#    GPU and contending would only make each slower. Its own sentinel is the
#    report it writes last.
# ---------------------------------------------------------------------------
$inflight = Join-Path $repo "out\u2_2d\prolongator_L64\report.md"
$deadline = (Get-Date).AddMinutes(90)
while (-not (Test-Path $inflight) -and (Get-Date) -lt $deadline) {
    Write-Host "waiting for prolongator_L64 ... $(Get-Date -Format 'HH:mm:ss')"
    Start-Sleep -Seconds 60
}
if (Test-Path $inflight) {
    Write-Host "prolongator_L64 finished; starting the queue"
} else {
    Write-Host "prolongator_L64 did not finish inside 90 min; running it here"
}

# Covered as a stage too, so that a run started from an editor-attached shell
# and killed with that shell is picked up rather than silently lost. Its own
# report is the sentinel, so a completed run is skipped.
Stage "fix0_prolongator_L64" "out\u2_2d\prolongator_L64\report.md" @(
    "u2_2d\scripts\17_prolongator_baseline.py", "--config", "u2_2d\configs\default.yaml",
    "--rung", "1", "--n-traj", "400", "--n-chains", "64",
    "--out-dir", "out\u2_2d\prolongator_L64")

# ---------------------------------------------------------------------------
# 1. Parity positive control (item 5)
#    The beta = 14 base is regenerated on the base recipe first: on the old
#    short run it was itself 6.6 sigma off, and a control that is wrong cannot
#    certify anything.
# ---------------------------------------------------------------------------
Stage "fix1a_base14" "out\u2_2d\data\u2_L16_beta14.regenerated" @(
    "u2_2d\scripts\01_generate_data.py", "--config", "u2_2d\configs\default.yaml",
    "--only-sizes", "16", "--only-betas", "14", "--overwrite") `
    -Touch "out\u2_2d\data\u2_L16_beta14.regenerated"

Stage "fix1b_ladder_mobile" "out\u2_2d\ladder_mobile\summary.json" @(
    "u2_2d\scripts\03_run_ladder.py", "--config", "u2_2d\configs\default.yaml",
    "--base-beta", "14", "--base-size", "16",
    "--out-dir", "out\u2_2d\ladder_mobile")

Stage "fix1c_parity_transport" "out\u2_2d\parity_transport\report.md" @(
    "u2_2d\scripts\19_parity_transport.py",
    "--ladders", "out\u2_2d\ladder", "out\u2_2d\ladder_mobile")

# ---------------------------------------------------------------------------
# 2. Density gap in nats per site (item 4)
#    Four cases: the first is the instrument validation, the last two are the
#    ladder's own rungs. Coarse ensembles are stage-01 HMC, never generated ones.
# ---------------------------------------------------------------------------
Stage "fix2_density_gap" "out\u2_2d\density_gap\report.md" @(
    "u2_2d\scripts\18_density_gap.py", "--config", "u2_2d\configs\default.yaml",
    "--n-configs", "64", "--ode-steps", "120", "--n-probes", "2",
    "--batch-size", "8")

# ---------------------------------------------------------------------------
# 3. Coupling coverage: retrain, then rebuild the ladder beside the one of
#    record (item 3). The deployed checkpoint saw a maximum model beta of 50.8
#    while the top rung needs 104.1 -- a 2.05x extrapolation, and the documented
#    cause of a coherent negative bias in ~24 observables there.
#
#    Everything goes to `_cov` paths. The A/B is the deliverable.
# ---------------------------------------------------------------------------
Stage "fix3a_train_cov" "out\u2_2d\checkpoints\det_score_net_cov.pt" @(
    "u2_2d\scripts\02_train.py", "--config", "u2_2d\configs\default.yaml",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_cov.pt")

Stage "fix3b_ladder_cov" "out\u2_2d\ladder_cov\summary.json" @(
    "u2_2d\scripts\03_run_ladder.py", "--config", "u2_2d\configs\default.yaml",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_cov.pt",
    "--out-dir", "out\u2_2d\ladder_cov")

Stage "fix3c_validate_cov" "out\u2_2d\validation_cov\summary.json" @(
    "u2_2d\scripts\04_validate.py", "--config", "u2_2d\configs\default.yaml",
    "--ladder-dir", "out\u2_2d\ladder_cov",
    "--out-dir", "out\u2_2d\validation_cov")

# --checkpoint is NOT optional here. 18_density_gap.py otherwise takes the
# checkpoint from the config, so --out-dir alone reruns the SAME weights into a
# new directory and produces a bit-identical "A/B" -- which is exactly what
# happened on the 2026-08-20 run (KL 9394.0 in both arms, to the decimal).
Stage "fix3d_density_cov" "out\u2_2d\density_gap_cov\report.md" @(
    "u2_2d\scripts\18_density_gap.py", "--config", "u2_2d\configs\default.yaml",
    "--checkpoint", "out\u2_2d\checkpoints\det_score_net_cov.pt",
    "--n-configs", "64", "--ode-steps", "120", "--n-probes", "2",
    "--batch-size", "8", "--out-dir", "out\u2_2d\density_gap_cov")

# ---------------------------------------------------------------------------
# 4. Prolongator baseline at the lower rung too (item 2). The top rung is
#    already running or done; rung 0 is the one where the couplings are weak
#    enough that the arms can actually separate.
# ---------------------------------------------------------------------------
Stage "fix4_prolongator_L32" "out\u2_2d\prolongator_L32\report.md" @(
    "u2_2d\scripts\17_prolongator_baseline.py", "--config", "u2_2d\configs\default.yaml",
    "--rung", "0", "--n-traj", "400", "--n-chains", "64",
    "--out-dir", "out\u2_2d\prolongator_L32")

# ---------------------------------------------------------------------------
# 5. Figures and the regenerated results section
# ---------------------------------------------------------------------------
Stage "fix5a_cost_figures" "" @("u2_2d\scripts\16_cost_figures.py")
Stage "fix5b_prolongator_figure" "" @("u2_2d\scripts\20_prolongator_figure.py")
Stage "fix5c_paper_figures" "" @("u2_2d\scripts\10_paper_figures.py")
Stage "fix5d_results" "" @("u2_2d\scripts\12_results_section.py")

Write-Host ""
Write-Host "=== queue finished $(Get-Date -Format 'HH:mm:ss') ==="
Get-ChildItem $logs -Filter "fix*.log" | ForEach-Object {
    Write-Host ("{0,-28} {1,8:N0} bytes" -f $_.Name, $_.Length)
}

if ($awake -and -not $awake.HasExited) { Stop-Process -Id $awake.Id -Force }
Remove-Item $lock -Force -ErrorAction SilentlyContinue
Stop-Transcript | Out-Null
