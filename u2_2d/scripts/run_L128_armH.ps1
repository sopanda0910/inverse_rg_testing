Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\L128_armH.log"
$py = ".venv\Scripts\python.exe"

# ARM H, SPLIT OUT TO RUN CONCURRENTLY WITH THE MAIN L=128 PROCESS.
#
# Why: arm A measured 1.99 h at this volume, 7.0x its cost at L=64 rather
# than the 2x predicted from sites/chains -- at L=128 the GPU is
# arithmetic-bound, so the halved chain count bought nothing. That put the
# remaining three arms at ~16.4 h SEQUENTIALLY, finishing ~14:00, past the
# 10-11:00 deadline after which this machine is on battery.
#
# The two odd-winding arms (G, H) carry essentially all of that cost and are
# INDEPENDENT of each other, so running one of them in a second process
# converts a sum into a max. Nothing is discarded: the main process keeps
# arm D (already ~48 min in) and then runs G.
#
# Separate out-dir on purpose. `08_hmc_seed_benchmark.py` caches per arm but
# both processes would write `seed_benchmark.json` at the end, and the later
# writer would clobber the other's summary with a partial one. Arm A is
# copied in so this process's mandatory-A guard is satisfied from cache
# rather than by re-running two hours of it. When H lands, its arm file is
# copied into the main directory, where the main process will find it cached
# and skip it -- so the split costs no duplicated work in either direction.
& $py "u2_2d\scripts\gpu_slots.py" --label "L128-armH" -- `
    $py "u2_2d\scripts\08_hmc_seed_benchmark.py" --config "u2_2d\configs\wide.yaml" `
    --device cuda --rung 2 --n-chains 32 `
    --arms "A_diffusion_seed,H_diffusion_plus_odd_winding" `
    --out-dir "out/u2_2d/seed_benchmark_wide_L128_h" *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED armH, exit $LASTEXITCODE" *>> $log; exit 1 }

Copy-Item "out\u2_2d\seed_benchmark_wide_L128_h\arm_H_diffusion_plus_odd_winding.json" `
          "out\u2_2d\seed_benchmark_wide_L128\" -Force
"ARM H DONE $(Get-Date), copied into main dir" *>> $log
