Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\data_random_2000\gen.log"
New-Item -ItemType Directory -Force -Path "out\u1_2d\data_random_2000" | Out-Null
$py = ".venv\Scripts\python.exe"
"$(Get-Date) u1 random_rungs 2000 local gen start" *>> $log

# 5 shards, one thread each -- same reasoning as u2's local job: leaves
# physical cores free for the concurrently-running GPU relaxation matrix's
# launch-dispatch overhead.
$jobs = @()
for ($i = 0; $i -lt 5; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($py, $i, $repo)
        Set-Location $repo
        $env:U1_2D_TORCH_THREADS = "1"
        & $py "u1_2d\scripts\01_generate_data.py" --config "u1_2d\configs\random_rungs_2000_gen.yaml" --shard "$i/5" --device cpu
        # A native command's nonzero exit does NOT mark a PowerShell job
        # "Failed" on its own -- the first version of this script silently
        # logged "PIPELINE DONE" while every shard had crashed with a
        # traceback, because nothing here checked $LASTEXITCODE. Throwing
        # makes the job's own State actually reflect the failure.
        if ($LASTEXITCODE -ne 0) { throw "shard $i exited $LASTEXITCODE" }
    } -ArgumentList $py, $i, (Get-Location).Path
}
$jobs | Wait-Job | Receive-Job *>> $log
$states = $jobs | ForEach-Object { $_.State }
$jobs | Remove-Job

# u1's --shard mode writes each rung's ensemble as its own final .pt file
# directly (unlike u2's shard-summary-then-merge pattern) -- no merge-shards
# step exists for plain ensemble generation, only for --rebuild-matching's
# side files, which this task doesn't use. Confirmed by reading the script:
# --merge-shards accepts no --out-dir flag at all, which is what made an
# earlier version of this wrapper fail immediately (exit 2, unrecognized arg).
if ($states -contains "Failed") {
    "$(Get-Date) FAILED, one or more shards errored" *>> $log
    exit 1
}

# Earlier crashes (fixed 2026-09-04: match_coarse_beta's default bracket
# couldn't reach the coarse-beta match for fine beta above ~1024) left some
# already-saved ensembles without a matching.json entry, since a shard only
# writes its matching dict once at the very end of its loop and a rung that
# already exists on disk is skipped entirely (never re-attempts matching).
# A single non-sharded --rebuild-matching pass backfills any ensemble file
# that's missing one -- safe to run every time, it skips keys already present.
& $py "u1_2d\scripts\01_generate_data.py" --config "u1_2d\configs\random_rungs_2000_gen.yaml" --rebuild-matching *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, rebuild-matching exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
