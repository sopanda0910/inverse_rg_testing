# Re-run the U(1) ladder and its validation on the <Q^2>-matched schedule
# (configs/v2_topomatched.yaml: 3.9174, 13.5864, 52.7535), leaving the deployed
# plaquette-matched ensembles untouched.
#
# Built to survive the laptop dying mid-run, which is the expected failure here:
#   * each stage is a separate process, and a stage that has already produced its
#     output is skipped on restart, so a crash costs at most the running stage;
#   * the wrapper retries a stage that exits non-zero, up to -MaxRetries, since a
#     CUDA OOM or a suspend-resume fault is usually transient;
#   * progress is appended to a status file with timestamps, so the state after
#     an unattended crash can be read without re-deriving it;
#   * the machine is held awake for the duration and released on exit.
#
#   powershell -ExecutionPolicy Bypass -File u1_2d/scripts/run_topomatched.ps1
#
# To resume after a crash, run the identical command: completed stages are
# detected and skipped.

param(
    [string]$Config = "u1_2d/configs/v2_topomatched.yaml",
    [int]$MaxRetries = 3,
    [switch]$Force
)

$ErrorActionPreference = "Continue"
Set-Location (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)

$py = ".venv\Scripts\python.exe"
$status = "out\u1_2d\topomatched_status.log"
New-Item -ItemType Directory -Force -Path "out\u1_2d" | Out-Null

function Say($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $status -Value $line -Encoding utf8
}

# Hold the machine awake. keep_awake.ps1 calls SetThreadExecutionState and
# releases when its process exits, so it is started as a child and stopped in
# the finally block rather than leaving a global setting behind.
$awake = $null
$keepAwake = "u2_2d\scripts\keep_awake.ps1"
if (Test-Path $keepAwake) {
    $awake = Start-Process -FilePath "powershell" -PassThru -WindowStyle Hidden `
        -ArgumentList "-ExecutionPolicy", "Bypass", "-File", $keepAwake
    Say "keep-awake started (pid $($awake.Id))"
}

# stage name, script, log, and the artifact whose presence means it is done
$stages = @(
    @{ Name = "03_ladder";   Script = "u1_2d\scripts\03_run_ladder.py";
       Log = "out\u1_2d\topomatched_ladder.log";
       Done = "out\u1_2d\generated_topomatched" },
    @{ Name = "04_validate"; Script = "u1_2d\scripts\04_validate.py";
       Log = "out\u1_2d\topomatched_validate.log";
       Done = "out\u1_2d\validation_topomatched\report.md" }
)

Say "=== run start, config $Config ==="
$failed = $false
try {
    foreach ($s in $stages) {
        if ((Test-Path $s.Done) -and (-not $Force)) {
            $n = (Get-ChildItem -Recurse -File $s.Done -ErrorAction SilentlyContinue |
                  Measure-Object).Count
            if ($n -gt 0 -or (Test-Path $s.Done -PathType Leaf)) {
                Say "$($s.Name): output present, skipping"
                continue
            }
        }
        $ok = $false
        for ($try = 1; $try -le $MaxRetries -and -not $ok; $try++) {
            Say "$($s.Name): attempt $try of $MaxRetries"
            & $py "-u" $s.Script "--config" $Config *>&1 |
                Tee-Object -FilePath $s.Log -Append | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $ok = $true
                Say "$($s.Name): completed"
            } else {
                Say "$($s.Name): exit code $LASTEXITCODE (see $($s.Log))"
                Start-Sleep -Seconds 20
            }
        }
        if (-not $ok) {
            Say "$($s.Name): FAILED after $MaxRetries attempts, stopping"
            $failed = $true
            break
        }
    }
} finally {
    if ($awake -and -not $awake.HasExited) {
        Stop-Process -Id $awake.Id -Force -ErrorAction SilentlyContinue
        Say "keep-awake released"
    }
}

if ($failed) { Say "=== run INCOMPLETE ==="; exit 1 }
Say "=== run complete ==="
exit 0
