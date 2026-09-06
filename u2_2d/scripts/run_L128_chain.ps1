Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\L128_chain.log"
$py = ".venv\Scripts\python.exe"
$slots = "u2_2d\scripts\gpu_slots.py"

# GATE ON A FREE GPU SLOT, NOT ON ONE PID. The first version of this script
# waited for a specific process (rung0's benchmark worker) to exit, which
# fired correctly and still overcommitted the card: the slot that process
# freed had already been taken by the rung1 benchmark, while the relaxation
# orchestrator independently held two more. Five CUDA contexts were live at
# once against a measured ceiling of three, and this job -- the heaviest of
# them at ~3.5 GiB, more than the other three combined -- is the one that had
# already died once under contention with CUDNN_STATUS_EXECUTION_FAILED_CUDART.
# `gpu_slots.py` is a machine-wide counting semaphore, so "wait until the
# machine has room" is now expressible; a per-process gate never could.
#
# Both stages take a slot. The ladder extension and the benchmark are
# separate processes, so a single outer acquisition would be released
# between them and could not cover both.
"$(Get-Date) queued for a GPU slot (ladder extension)" *>> $log

& $py $slots --label "L128-ladder" -- `
    $py "u2_2d\scripts\03_run_ladder.py" --config "u2_2d\configs\wide.yaml" --device cuda `
    --beta-schedule 105.651 416.524 1660.076283 *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (ladder), exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) ladder done, queued for a GPU slot (benchmark)" *>> $log

# Reduced scope, deliberately: 4 decision-relevant arms x 32 chains instead of
# 8 x 64. The full grid at this volume is ~13.6 h by measured per-arm cost at
# L=64, which does not fit the run budget alongside the relaxation matrix. The
# halved chain count widens bootstrap intervals ~40%; acceptable because this
# point establishes WHETHER the pattern survives at a volume the checkpoint
# never trained on, not a precision measurement of it.
& $py $slots --label "L128-benchmark" -- `
    $py "u2_2d\scripts\08_hmc_seed_benchmark.py" --config "u2_2d\configs\wide.yaml" `
    --device cuda --rung 2 --n-chains 32 `
    --arms "A_diffusion_seed,D_cold_plus_winding,G_cold_plus_odd_winding,H_diffusion_plus_odd_winding" `
    --out-dir "out/u2_2d/seed_benchmark_wide_L128" *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (benchmark), exit $LASTEXITCODE" *>> $log; exit 1 }

"L128 CHAIN DONE $(Get-Date)" *>> $log
