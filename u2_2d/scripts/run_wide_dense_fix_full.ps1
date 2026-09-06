Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\wide_dense_fix_full.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\checkpoints" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
"$(Get-Date) u2 wide_dense FIX (sector_augment/seed_exact_sectors regen) full pipeline start" *>> $log

# --- Step 0: wipe the broken data_random_2000 (frozen coarse rungs, see
# random_rungs_2000_gen.yaml's header for the diagnosis) and regenerate with
# the fix, sharded exactly as the original generation was.
"$(Get-Date) removing stale out\u2_2d\data_random_2000" *>> $log
Remove-Item -Recurse -Force "out\u2_2d\data_random_2000" -ErrorAction SilentlyContinue

$env:U2_2D_TORCH_THREADS = "1"
$jobs = @()
for ($i = 0; $i -lt 5; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($py, $i, $repo)
        Set-Location $repo
        $env:U2_2D_TORCH_THREADS = "1"
        & $py "u2_2d\scripts\01_generate_data.py" --config "u2_2d\configs\random_rungs_2000_gen.yaml" --shard "$i/5" --device cpu
        if ($LASTEXITCODE -ne 0) { throw "shard $i exited $LASTEXITCODE" }
    } -ArgumentList $py, $i, (Get-Location).Path
}
$jobs | Wait-Job | Receive-Job *>> $log
$states = $jobs | ForEach-Object { $_.State }
$jobs | Remove-Job
if ($states -contains "Failed") { "$(Get-Date) FAILED (data regen shard), aborting" *>> $log; exit 1 }

& $py "u2_2d\scripts\01_generate_data.py" --config "u2_2d\configs\random_rungs_2000_gen.yaml" --merge-shards --out-dir out\u2_2d\data_random_2000 *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (merge shards), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) data regen done, starting retrain" *>> $log

# --- Steps 1-4: identical to run_wide_dense_full.ps1 (train -> ladder ->
# validate -> relaxation matrix -> per-observable tau), just against the
# corrected data_random_2000. Overwrites the wide_dense checkpoint/outputs in
# place -- the paper's "frozen coarse training input" paragraph already cites
# the OLD (broken) numbers as a historical diagnostic finding, so this is
# safe; the gap-vs-t_therm correlation numbers should be recomputed after
# this finishes.
& $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (train), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) training done, starting ladder" *>> $log

& $py "u2_2d\scripts\03_run_ladder.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (ladder), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) ladder done, starting validate" *>> $log

& $py "u2_2d\scripts\04_validate.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (validate), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) validate done, clearing stale relaxation-matrix outputs" *>> $log

# 60_run_full_relaxation_matrix.py's is_done() only checks file existence +
# row count, not content or checkpoint mtime -- it would otherwise see last
# run's (broken-checkpoint) crossover*.json files and think wide_dense is
# already finished, silently skipping the rerun this whole script exists for.
Remove-Item -Recurse -Force "out\u2_2d\coverage_scan_relaxation\wide_dense" -ErrorAction SilentlyContinue

& $py "u2_2d\scripts\60_run_full_relaxation_matrix.py" --budget 2 --poll-seconds 20 *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (relaxation matrix), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) relaxation matrix done, computing per-observable tau" *>> $log

& $py "u2_2d\scripts\68_per_observable_tau.py" --dir "out\u2_2d\coverage_scan_relaxation\wide_dense" *>> $log

"PIPELINE DONE $(Get-Date)" *>> $log
