# Fan the marginal-move bias scan over the idle CPU cores, 2026-08-21.
#
# The GPU queue (training + two volume scans + P(Q)) holds the GPU at ~99% but
# leaves the CPU at ~34%. U(2) HMC at L = 8 is FASTER on CPU than on GPU (0.52
# gpu/cpu in the device table), so this work is not merely idle-filling -- L = 8
# is where it belongs anyway.
#
# One process per (beta, sweep count) cell, one torch thread each: both heavy
# stages in this project are latency-bound, and threads inside one unit make it
# worse (154 sweeps/s on 1 thread, 91 on 12). Six cells.
#
# STATISTICS. Resolving a 1% deficit in P(odd) ~ 0.48 at 3 sigma needs
# sigma <= 0.0016, i.e. n_chains * n_draws / (2 tau) >~ 1e5 with tau ~ 0.85
# draws. 128 chains x 1280 draws gives ~9.6e4 effective, so a 1% effect lands
# near 3 sigma per cell and the three cells of a beta together decide the trend.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_bias_scan.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

$env:U1_2D_TORCH_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

$procs = @()
foreach ($beta in @("10", "14")) {
    foreach ($sw in @("5", "25", "100")) {
        $name = "bias_b${beta}_s${sw}"
        $log = Join-Path $logs "q_$name.log"
        $p = Start-Process -FilePath $py -PassThru -WindowStyle Hidden `
            -WorkingDirectory $repo -RedirectStandardOutput $log `
            -RedirectStandardError "$log.err" -ArgumentList @(
                "-u", "u2_2d/scripts/34_marginal_move_bias.py",
                "--device", "cpu", "--lattice-size", "8",
                "--betas", $beta, "--su2-sweeps", $sw,
                "--n-chains", "128", "--n-draws", "1280",
                "--burn-in", "600", "--thin", "5",
                "--out-dir", "out/u2_2d/marginal_move_bias/$name")
        Write-Host "[run ] $name  pid $($p.Id)  $(Get-Date -Format 'HH:mm:ss')"
        $procs += $p
    }
}

foreach ($p in $procs) { $p.WaitForExit() }
Write-Host "[bias scan] all cells finished $(Get-Date -Format 'HH:mm:ss')"
