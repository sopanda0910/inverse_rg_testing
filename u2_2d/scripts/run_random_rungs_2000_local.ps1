Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\data_random_2000\gen.log"
New-Item -ItemType Directory -Force -Path "out\u2_2d\data_random_2000" | Out-Null
$py = ".venv\Scripts\python.exe"
$env:U2_2D_TORCH_THREADS = "1"
"$(Get-Date) u2 random_rungs 2000 local gen start" *>> $log

# 5 shards, one thread each -- leaves 3 of 8 physical cores free for the
# concurrently-running GPU relaxation matrix's launch-dispatch overhead.
$jobs = @()
for ($i = 0; $i -lt 5; $i++) {
    $jobs += Start-Job -ScriptBlock {
        param($py, $i, $repo)
        Set-Location $repo
        $env:U2_2D_TORCH_THREADS = "1"
        & $py "u2_2d\scripts\01_generate_data.py" --config "u2_2d\configs\random_rungs_2000_gen.yaml" --shard "$i/5" --device cpu
        # A native command's nonzero exit does not mark a PowerShell job
        # "Failed" on its own -- throwing makes a shard crash actually
        # visible to the state check below (this run itself succeeded, but
        # the gap was latent and got caught for real in u1's twin script).
        if ($LASTEXITCODE -ne 0) { throw "shard $i exited $LASTEXITCODE" }
    } -ArgumentList $py, $i, (Get-Location).Path
}
$jobs | Wait-Job | Receive-Job *>> $log
$states = $jobs | ForEach-Object { $_.State }
$jobs | Remove-Job
if ($states -contains "Failed") { "$(Get-Date) FAILED, one or more shards errored" *>> $log; exit 1 }

& $py "u2_2d\scripts\01_generate_data.py" --config "u2_2d\configs\random_rungs_2000_gen.yaml" --merge-shards --out-dir out\u2_2d\data_random_2000 *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
