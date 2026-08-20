<#
.SYNOPSIS
    Run stages 02 -> 06 after stage 01 has finished.

.DESCRIPTION
    Stages 02, 03, 04 and 06 are chained because each consumes the previous
    one's output. Stage 05 (the topology study) depends on nothing but the
    physics -- no checkpoint, no ensembles -- so it is launched immediately and
    in parallel on the CPU, which costs nothing because training is GPU-bound.

    Stage 04 runs on CPU: it is dominated by reference HMC at L <= 32, and above
    that it generates no reference at all (the top ladder rung is the
    extrapolation the whole method exists for).

    Each stage aborts the chain on a non-zero exit, so a failure cannot be
    laundered into a "completed" run with missing outputs.

    Stdout and stderr go to SEPARATE files. Do not "simplify" this back to
    `& $python ... *>&1 | Tee-Object`: PowerShell 5.1 wraps every stderr line of a
    native executable in a NativeCommandError record, and the wrapping discarded
    the body of a real traceback on 2026-08-19 -- the log kept the words
    "Traceback (most recent call last):" and threw away every frame after it.
    Tee-Object also writes UTF-16, which renders the log as mojibake.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File u2_2d/scripts/run_all.ps1
#>
[CmdletBinding()]
param(
    [string]$Config = "u2_2d/configs/default.yaml",
    [string]$LogDir = "out/u2_2d/logs",
    [switch]$SkipTopology,
    [string]$StartAt = "02_train"
)

$ErrorActionPreference = "Stop"
$python = ".venv\Scripts\python.exe"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
$env:PYTHONUNBUFFERED = "1"

$topology = $null
if (-not $SkipTopology) {
    $log = Join-Path $LogDir "stage05_topology.log"
    $env:U2_2D_TORCH_THREADS = "4"
    $topology = Start-Process -FilePath $python -PassThru -NoNewWindow `
        -ArgumentList "u2_2d\scripts\05_topology_study.py", "--device", "cpu" `
        -RedirectStandardOutput $log -RedirectStandardError "$log.err"
    # Touching .Handle caches the process handle in .NET. Without it, ExitCode is
    # $null after the process exits -- Start-Process -PassThru does not retain the
    # handle by itself, so every shard reads as a failure even when all of them
    # succeeded. This is the single most common Start-Process trap.
    $null = $topology.Handle
    Write-Host "stage 05 (topology) launched in parallel on cpu, pid $($topology.Id) -> $log"
}

$stages = @(
    @{ Name = "02_train";      Script = "u2_2d\scripts\02_train.py";      Device = $null },
    @{ Name = "03_run_ladder"; Script = "u2_2d\scripts\03_run_ladder.py"; Device = $null },
    @{ Name = "04_validate";   Script = "u2_2d\scripts\04_validate.py";   Device = "cpu" },
    @{ Name = "06_figures";    Script = "u2_2d\scripts\06_figures.py";    Device = $null }
)

$startIndex = [array]::IndexOf(($stages | ForEach-Object { $_.Name }), $StartAt)
if ($startIndex -lt 0) {
    Write-Host "unknown -StartAt '$StartAt'; expected one of: $(($stages | ForEach-Object { $_.Name }) -join ', ')"
    exit 2
}
if ($startIndex -gt 0) { Write-Host "resuming at $StartAt (skipping $startIndex earlier stage(s))" }

$env:U2_2D_TORCH_THREADS = "8"
foreach ($stage in $stages[$startIndex..($stages.Count - 1)]) {
    $log = Join-Path $LogDir "stage$($stage.Name).log"
    $errLog = "$log.err"
    $arguments = @($stage.Script, "--config", $Config)
    if ($stage.Device) { $arguments += @("--device", $stage.Device) }
    Write-Host "--- $($stage.Name) -> $log"
    $started = Get-Date
    $p = Start-Process -FilePath $python -PassThru -NoNewWindow -ArgumentList $arguments `
        -RedirectStandardOutput $log -RedirectStandardError $errLog
    $null = $p.Handle
    $p.WaitForExit()
    if ($p.ExitCode -ne 0) {
        Write-Host "$($stage.Name) FAILED (exit $($p.ExitCode)); stopping the chain"
        if (Test-Path $errLog) { Get-Content $errLog | Select-Object -Last 40 }
        if ($topology -and -not $topology.HasExited) { $topology.Kill() }
        exit $p.ExitCode
    }
    Write-Host ("    done in {0:hh\:mm\:ss}" -f ((Get-Date) - $started))
}

if ($topology) {
    Write-Host "waiting on stage 05..."
    $topology.WaitForExit()
    Write-Host "stage 05 exit $($topology.ExitCode)"
}
Write-Host "all stages complete"
