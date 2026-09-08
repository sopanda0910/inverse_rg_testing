Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\timing_jitter.log"
$py = ".venv\Scripts\python.exe"

# WAIT FOR AN IDLE GPU. This job measures wall-clock jitter, so running it
# alongside other CUDA work would measure the contention instead of the
# machine -- the one condition that makes the numbers meaningless. Poll until
# no other python process is running, then start.
"$(Get-Date) waiting for an idle GPU before timing" *>> $log
while ($true) {
    # GATE ON LIVE CUDA CONTEXTS, NOT ON "IS ANY PROJECT PYTHON RUNNING".
    #
    # Two failures produced this, in order. The first gate matched ANY
    # python.exe, which would have waited forever because an unrelated
    # project on this machine runs its own python continuously. Narrowing
    # it to this project's interpreter then DEADLOCKED on gpu_monitor.py:
    # the monitor added to watch for GPU contention is itself a project
    # python process that never exits, so it blocked the very job it was
    # supposed to protect -- the GPU sat idle from 01:06 to 07:55 while this
    # script waited on a process that uses no GPU at all.
    #
    # The property actually wanted is "no CUDA context but mine", which
    # gpu_monitor exposes directly. A process list was always a proxy for
    # it, and every proxy failure above came from something that is a
    # project process but not a GPU one.
    $n = & $py "u2_2d\scripts\gpu_monitor.py" --once 2>$null |
         Select-String -Pattern 'ours=(\d+)' | ForEach-Object { $_.Matches[0].Groups[1].Value }
    if ([int]$n -eq 0) { break }
    Start-Sleep -Seconds 120
}
"$(Get-Date) GPU idle, starting $($args.Count) timing repeats" *>> $log

# Short runs (50 trajectories) repeated, not one long run: the quantity being
# characterised is per-trajectory rate variability, and a short run measures
# that as well as a long one for a fraction of the cost. Separate out-dirs per
# repeat are REQUIRED -- 08_hmc_seed_benchmark.py caches completed arms and
# would otherwise reuse repeat 1's timings instead of measuring again.
$dirs = @()
foreach ($i in 1..3) {
    $d = "out/u2_2d/timing_rep$i"
    $dirs += $d
    "$(Get-Date) repeat $i -> $d" *>> $log
    & $py "u2_2d\scripts\08_hmc_seed_benchmark.py" --config "u2_2d\configs\wide.yaml" `
        --device cuda --rung 1 --n-traj 50 --n-chains 64 `
        --arms "A_diffusion_seed,E_diffusion_plus_winding,G_cold_plus_odd_winding" `
        --out-dir $d *>> $log
    if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED repeat $i, exit $LASTEXITCODE" *>> $log; exit 1 }
}

& $py "u2_2d\scripts\77_timing_jitter.py" --dirs ($dirs -join ",") *>> $log
"TIMING JITTER DONE $(Get-Date)" *>> $log
