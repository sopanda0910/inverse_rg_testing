<#
.SYNOPSIS
    Launch stage 01 across CPU and GPU at once.

.DESCRIPTION
    The device split is measured, not assumed (see the header of
    01_generate_data.py). GPU/CPU trajectory rate on this machine:

        L=8/32ch 0.52x | L=16/32ch 1.34x | L=32/32ch 4.67x | L=32/64ch 8.30x

    So the L=8 rungs go to CPU -- where the GPU is actually 2x SLOWER, because
    the kernels are too small to pay for their launches -- and everything from
    L=16 up goes to the GPU, whose throughput is flat at ~5 traj/s all the way to
    L=64 and therefore has capacity to spare. Running both groups concurrently
    uses the whole machine instead of leaving one processor idle.

    Within each group the shards follow the contract in
    u1_2d/scripts/shard_runner.py: round-robin rung selection, own summary file,
    merged at the end. Each CPU shard is pinned to ONE torch thread; threads
    inside a shard make it slower, not faster, at these tensor sizes.

.PARAMETER CpuShards
    Number of concurrent single-threaded CPU processes (L=8 rungs).

.PARAMETER GpuShards
    Number of concurrent CUDA processes. 3-4 on an 8 GiB card: each carries its
    own CUDA context, and the speedup flattens once the GPU actually saturates.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_stage01.ps1
#>
[CmdletBinding()]
param(
    [string]$Config = "u2_2d/configs/default.yaml",
    [int]$CpuShards = 3,
    [int]$GpuShards = 4,
    [string]$LogDir = "out/u2_2d/logs"
)

$ErrorActionPreference = "Stop"
$python = ".venv\Scripts\python.exe"
$script = "u2_2d\scripts\01_generate_data.py"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

$jobs = @()
$start = Get-Date

foreach ($i in 0..($CpuShards - 1)) {
    $log = Join-Path $LogDir "stage01_cpu$i.log"
    $env:U2_2D_TORCH_THREADS = "1"
    $env:PYTHONUNBUFFERED = "1"
    $p = Start-Process -FilePath $python -PassThru -NoNewWindow `
        -ArgumentList $script, "--config", $Config, "--only-sizes", "8",
                      "--shard", "$i/$CpuShards", "--device", "cpu" `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    # Touching .Handle caches the process handle in .NET. Without it, ExitCode is
    # $null after the process exits -- Start-Process -PassThru does not retain the
    # handle by itself, so every shard reads as a failure even when all of them
    # succeeded. This is the single most common Start-Process trap.
    $null = $p.Handle
    $jobs += [pscustomobject]@{ Name = "cpu$i"; Process = $p; Log = $log }
}

foreach ($i in 0..($GpuShards - 1)) {
    $log = Join-Path $LogDir "stage01_gpu$i.log"
    $env:U2_2D_TORCH_THREADS = "1"
    $env:PYTHONUNBUFFERED = "1"
    $p = Start-Process -FilePath $python -PassThru -NoNewWindow `
        -ArgumentList $script, "--config", $Config, "--only-sizes", "16,32",
                      "--shard", "$i/$GpuShards", "--device", "cuda" `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    $null = $p.Handle
    $jobs += [pscustomobject]@{ Name = "gpu$i"; Process = $p; Log = $log }
}

Write-Host "launched $($jobs.Count) shards ($CpuShards cpu + $GpuShards gpu)"
foreach ($j in $jobs) { Write-Host ("  {0,-6} pid {1,-7} -> {2}" -f $j.Name, $j.Process.Id, $j.Log) }

foreach ($j in $jobs) { $j.Process.WaitForExit() }
$elapsed = (Get-Date) - $start

$failed = @($jobs | Where-Object { $_.Process.ExitCode -ne 0 })
foreach ($j in $jobs) {
    Write-Host ("{0,-6} exit {1}" -f $j.Name, $j.Process.ExitCode)
}
if ($failed.Count -gt 0) {
    Write-Host "FAILED shards: $($failed.Name -join ', ') -- summaries NOT merged"
    exit 1
}

& $python $script --config $Config --merge-shards
Write-Host ("stage 01 complete in {0:hh\:mm\:ss}" -f $elapsed)
