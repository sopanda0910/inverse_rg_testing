param([string]$Tag, [string]$Ckpt, [string]$Arm)

# One checkpoint's arm of the WIDENED evaluation grid (15 F_L16 couplings
# instead of 7). Launched once per checkpoint so the three run concurrently,
# one CUDA context each -- three is this card's measured ceiling.
#
# --skip-cached means the seven original couplings are NOT recomputed; only the
# eight new ones cost anything. Every arm is re-scored from saved series at the
# end by 70_rescore_crossover_from_series.py, so cases run on different days
# still land on one estimator.

Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$py = ".venv\Scripts\python.exe"
$log = "out\u1_2d\widegrid_$Tag.log"

$cases = "F_L16_bc75.3776,F_L16_bc100.377,F_L16_bc137.876,F_L16_bc187.876," +
         "F_L16_bc250.376,F_L16_bc375.375,F_L16_bc500.375," +
         "F_L16_bc62.8782,F_L16_bc87.8773,F_L16_bc117.877,F_L16_bc162.876," +
         "F_L16_bc217.876,F_L16_bc306.626,F_L16_bc437.875,F_L16_bc650.375"

$genDir   = "$Arm\generalization"
$thermDir = "$Arm\thermalization"
$merged   = "$Arm\crossover_window.json"

"$(Get-Date) widened-grid scan start: $Tag" *>> $log

& $py "u2_2d\scripts\gpu_slots.py" --label "u1-widegrid-$Tag" -- `
    $py "u1_2d\scripts\06_generalization_study.py" --checkpoint $Ckpt `
    --out-dir $genDir --device cuda --cases $cases *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (generalization) exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) generalization done" *>> $log

# STAGE 05 RUNS ON CPU, SHARDED -- and that is measured, not preference.
# This stage is ~98% batched HMC at L=16 (the diffusion sampling it also does
# is 7-8 s per case against ~385 s of HMC), and u1 batched HMC at L=16 is
# LAUNCH-BOUND, so the GPU is the wrong device: measured 2026-09-08 on this
# machine at 64 chains, CPU 6.26 traj/s against CUDA 1.20 traj/s. The first
# version of this script ran it with --device cuda, copied from the u2 runners
# where the crossover is at L=32/64 and the GPU genuinely wins. It does not
# transfer -- see CLAUDE.md's two separate device tables.
# Fan out over CASES, not threads: N single-threaded shards beat one
# N-threaded process on a launch-bound stage. Shards own disjoint L*_beta*/
# directories; the unsharded --skip-cached pass rebuilds the aggregates.
$env:U1_2D_DEVICE = "cpu"
$env:U1_2D_TORCH_THREADS = "1"
$shards = 4
$procs = @()
for ($i = 0; $i -lt $shards; $i++) {
    $procs += Start-Process -PassThru -WindowStyle Hidden -FilePath $py -ArgumentList `
        "u1_2d\scripts\05_hmc_thermalization.py", "--generalization", $genDir,
        "--checkpoint", $Ckpt, "--out", $thermDir, "--parts", "F",
        "--skip-cached", "--shard", "$i/$shards" `
        -RedirectStandardOutput "out\u1_2d\therm_${Tag}_$i.log" `
        -RedirectStandardError  "out\u1_2d\therm_${Tag}_$i.err"
}
$procs | Wait-Process -Timeout 14400 -EA SilentlyContinue

& $py "u1_2d\scripts\05_hmc_thermalization.py" --generalization $genDir `
    --checkpoint $Ckpt --out $thermDir --parts F --skip-cached *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (thermalization) exit $LASTEXITCODE" *>> $log; exit 1 }
"$(Get-Date) thermalization done" *>> $log

& $py "u1_2d\scripts\35_crossover_window.py" --dir $thermDir --out $merged *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (merge) exit $LASTEXITCODE" *>> $log; exit 1 }

"U1 WIDEGRID DONE $Tag $(Get-Date)" *>> $log
