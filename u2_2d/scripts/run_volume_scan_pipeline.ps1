# Volume-scaling extension of the coverage-comparison work: runs the SAME
# cost-efficiency scan (28_crossover_scan.py via 58_training_coverage_scan.py)
# at L=64 for every coverage-ablation checkpoint, so 59's comparison figure
# can show the falloff-vs-coverage story at both volumes, not just L=32.
#
# SCOPED DOWN from 14 to 8 couplings per round (--n-couplings 8): L=64 is
# roughly as expensive per coupling as L=32 (GPU throughput is flat in L,
# CLAUDE.md), so an unscoped 14-coupling pass here would cost as much as
# everything already queued tonight, combined. 8 couplings still traces the
# curve shape; the log-uniform coupling selection in 28_crossover_scan.py
# picks a representative spread either way.
#
# PRIORITY ORDER, not brute concurrency: cov60 and default are the pair the
# actual decision rests on, so they go first. v2/cap are LOWEST priority --
# their coverage ceiling (~107.5) barely differs from default's (~104), so
# they add the least new information of the six, and are explicitly the ones
# to lose if the night runs out of time.
#
# GPU-CONTEXT-AWARE, not a strict "wait for everything else" gate. A logical
# job on this machine shows up as roughly two python.exe processes (a
# launcher + the real worker -- confirmed by memory: the worker holds
# ~1 GiB+, the launcher a few MB), so process-count/2 approximates context
# count. New scans only start once that estimate is below 3, matching
# CLAUDE.md's documented ceiling for this card, and it is CHECKED, not
# assumed -- it does not hardcode "wait for cov60_pipeline.log to say DONE"
# the way earlier scripts did, so it does not idle the GPU if a checkpoint's
# L=32 work happens to finish early.

Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\coverage_scan\volume_scan_pipeline.log"
$py = ".venv\Scripts\python.exe"
"$(Get-Date) pipeline (re)start" *>> $log

function Get-ActiveGpuJobs {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "02_train\.py|28_crossover_scan\.py" }
    if (-not $procs) { return 0 }
    $distinct = $procs | Select-Object -ExpandProperty CommandLine -Unique
    return [Math]::Ceiling($distinct.Count)
}

function Wait-ForGpuRoom($budget) {
    while ((Get-ActiveGpuJobs) -ge $budget) {
        Start-Sleep -Seconds 120
    }
}

function Test-TrainingDone($historyPath, $epochs) {
    if (-not (Test-Path $historyPath)) { return $false }
    try {
        $h = Get-Content $historyPath -Raw | ConvertFrom-Json
        if ($h.Count -eq 0) { return $false }
        return ($h[-1].epoch + 1) -ge $epochs
    } catch { return $false }
}

function Test-ScanDone($path, $n) {
    if (-not (Test-Path $path)) { return $false }
    try { return (Get-Content $path -Raw | ConvertFrom-Json).Count -ge $n }
    catch { return $false }
}

# tag -> (checkpoint path, history path, epochs)
$order = @(
    @{ tag="cov60"; hist="out\u2_2d\checkpoints\det_score_net_cov60.history.json"; epochs=120 },
    @{ tag="default"; hist=$null; epochs=0 },
    @{ tag="cov30"; hist="out\u2_2d\checkpoints\det_score_net_cov30.history.json"; epochs=120 },
    @{ tag="cov15"; hist="out\u2_2d\checkpoints\det_score_net_cov15.history.json"; epochs=120 },
    @{ tag="v2"; hist=$null; epochs=0 },
    @{ tag="cap"; hist=$null; epochs=0 }
)

foreach ($item in $order) {
    $tag = $item.tag
    if ($item.hist -and -not (Test-TrainingDone $item.hist $item.epochs)) {
        "$(Get-Date) [$tag] training not finished yet -- waiting" *>> $log
        while (-not (Test-TrainingDone $item.hist $item.epochs)) { Start-Sleep -Seconds 120 }
    }
    if (Test-ScanDone "out\u2_2d\coverage_scan\$tag\crossover_L64_topo.json" 8) {
        "$(Get-Date) [$tag] L=64 scan already complete -- skipping" *>> $log
        continue
    }
    "$(Get-Date) [$tag] waiting for GPU room (budget 3 contexts)" *>> $log
    Wait-ForGpuRoom 3
    "$(Get-Date) [$tag] starting L=64 scan (8 couplings, both rounds)" *>> $log
    & $py "u2_2d\scripts\58_training_coverage_scan.py" --checkpoints $tag --fine-size 64 --n-couplings 8 *>> $log
    if ($LASTEXITCODE -ne 0) {
        "$(Get-Date) [$tag] L=64 scan FAILED, exit $LASTEXITCODE -- continuing to the next checkpoint rather than blocking the whole queue on one failure" *>> $log
    } else {
        "$(Get-Date) [$tag] L=64 scan done" *>> $log
    }
}

"$(Get-Date) all checkpoints attempted -- regenerating comparison figures (L=32 and L=64)" *>> $log
& $py "u2_2d\scripts\59_coverage_comparison_figure.py" --out "out\u2_2d\figures\fig59_coverage_comparison.png" *>> $log
& $py "u2_2d\scripts\59_coverage_comparison_figure.py" --fine-size 64 --out "out\u2_2d\figures\fig59_coverage_comparison_L64.png" *>> $log
"$(Get-Date) PIPELINE DONE" *>> $log
