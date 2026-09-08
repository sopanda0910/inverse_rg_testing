Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u1_2d\sectorfix_data.log"
$py = ".venv\Scripts\python.exe"
$env:U1_2D_TORCH_THREADS = "1"

# CPU-ONLY, and deliberately so: it runs alongside the u2 wide_dense retrain
# on the GPU without contending for it. u1 batched HMC at L<=32 is faster on
# CPU than GPU anyway (CLAUDE.md's measured device table), so this is not a
# compromise. 6 shards, one thread each -- stage 01 is latency-bound, and
# threads inside one shard measurably slow it down.
"$(Get-Date) u1 sector-coverage data regen start (30 rungs, burn_in 8000)" *>> $log
$jobs = @()
for ($i = 0; $i -lt 6; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($py, $i, $repo)
        Set-Location $repo
        $env:U1_2D_TORCH_THREADS = "1"
        & $py "u1_2d\scripts\01_generate_data.py" `
            --config "u1_2d\configs\random_rungs_2000_gen_sectorfix.yaml" `
            --shard "$i/6" --device cpu
        if ($LASTEXITCODE -ne 0) { throw "shard $i exited $LASTEXITCODE" }
    } -ArgumentList $py, $i, (Get-Location).Path
}
$jobs | Wait-Job | Receive-Job *>> $log
$states = $jobs | ForEach-Object { $_.State }
$jobs | Remove-Job
if ($states -contains "Failed") { "$(Get-Date) FAILED (shard), aborting" *>> $log; exit 1 }

& $py "u1_2d\scripts\01_generate_data.py" `
    --config "u1_2d\configs\random_rungs_2000_gen_sectorfix.yaml" --merge-shards *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (merge), exit $LASTEXITCODE" *>> $log; exit 1 }
"U1 SECTORFIX DATA DONE $(Get-Date)" *>> $log
