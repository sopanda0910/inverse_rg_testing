# The GPU stages that still owe a result, run SEQUENTIALLY. 2026-08-21 13:05.
#
# WHY SEQUENTIAL. Four concurrent CUDA contexts do not fit on this 8 GiB card at
# these workloads. Measured, twice, the hard way: the capacity retrain died at
# epoch 36 with `CUDA error: out of memory` at 11:58, and 03b (the L=16 P(Q) run
# under the marginal move) died the same way at 12:52 -- the instant the retrain
# was relaunched alongside it. `PYTORCH_CUDA_ALLOC_CONF=expandable_segments`,
# the usual remedy for fragmentation-driven OOM, is NOT SUPPORTED ON WINDOWS and
# warns and does nothing. So the only levers are context count and restartability.
#
# Three contexts (retrain + the two L=64 crossover scans) sit at ~4.2 GiB of
# 8 GiB and are stable. This script therefore waits for the two crossover scans
# to finish before adding anything, and then runs its own stages one at a time.
#
# WAIT CONDITION. It polls for the crossover PYTHON processes directly rather
# than for a parent PowerShell. The previous follow-up watcher keyed on the
# queue-runner process, and when that runner was killed by hand the watcher
# concluded the queue had finished and launched a retherm scan into a card that
# was already full -- which is what pushed 03b over the edge.
#
#   powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_gpu_tail.ps1

$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
$state = Join-Path $repo "out\u2_2d\queue_0821"
$logs = Join-Path $repo "out\u2_2d\logs"
New-Item -ItemType Directory -Force -Path $state, $logs | Out-Null

function Wait-For-Scans {
    while ($true) {
        $n = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
               Where-Object { $_.CommandLine -like "*28_crossover_scan*" }).Count
        if ($n -eq 0) { break }
        Start-Sleep -Seconds 120
    }
    Write-Host "[gpu tail] crossover scans clear $(Get-Date -Format 'HH:mm:ss')"
}

function Invoke-Stage {
    param([string]$Name, [string[]]$StageArgs)
    $sentinel = Join-Path $state "$Name.done"
    if (Test-Path $sentinel) { Write-Host "[skip] $Name"; return }
    $log = Join-Path $logs "q_$Name.log"
    $started = Get-Date
    Write-Host "[run ] $Name  $($started.ToString('HH:mm:ss'))"
    $p = Start-Process -FilePath $py -PassThru -WindowStyle Hidden `
        -WorkingDirectory $repo -RedirectStandardOutput $log `
        -RedirectStandardError "$log.err" -ArgumentList $StageArgs
    $p.WaitForExit()
    $mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
    if ($p.ExitCode -eq 0) {
        "ok" | Out-File -FilePath $sentinel -Encoding utf8
        Write-Host "[done] $Name  ${mins} min"
    } else {
        Write-Host "[FAIL] $Name  exit $($p.ExitCode) after ${mins} min -- see $log"
    }
}

Wait-For-Scans

# 03b: killed by OOM after 2 of 4 couplings, twice now (the first time by a
# Write-Output bug in the original queue). All four couplings are re-run rather
# than the two survivors, because 07_pq_sampling.py writes every record into a
# single pq_sampling.json and a partial re-run would drop the two that finished.
# 51.75 and 56 are the couplings whose PARITY-STUCK verdicts -- measured under
# the retired joint proposal -- currently disqualify them as a ladder base.
Invoke-Stage "03b_pq_marginal_L16" @(
    "-u", "u2_2d/scripts/07_pq_sampling.py", "--device", "cuda",
    "--lattice-size", "16", "--betas", "14,28,51.75,56",
    "--charge-step", "1", "--winding-interval", "5",
    "--out-dir", "out/u2_2d/pq_sampling_marginal_L16")

# The retherm scan, with the L=32 coarse case that the original queue skipped on
# a bad path (32:105.244 does not exist in data_v2; 32:105.651 is the rung of
# record and matches to fine beta 416.524 at L = 64). Both cases run: the script
# collects all records into one JSON.
Remove-Item (Join-Path $state "04_retherm_scan.done") -ErrorAction SilentlyContinue
Invoke-Stage "04_retherm_scan" @(
    "-u", "u2_2d/scripts/33_retherm_scan.py", "--device", "cuda",
    "--cases", "16:105.244,32:105.651", "--n-configs", "256",
    "--sampler-steps", "200", "--sweeps", "0,2,5,10,20,40,80")

Write-Host "[gpu tail] finished $(Get-Date -Format 'HH:mm:ss')"
