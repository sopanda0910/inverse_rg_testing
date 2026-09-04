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
    } -ArgumentList $py, $i, (Get-Location).Path
}
$jobs | Wait-Job | Receive-Job *>> $log
$jobs | Remove-Job

& $py "u1_2d\scripts\01_generate_data.py" --config "u1_2d\configs\random_rungs_2000_gen.yaml" --merge-shards --out-dir out\u1_2d\data_random_2000 *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED, exit $LASTEXITCODE" *>> $log; exit 1 }
"PIPELINE DONE $(Get-Date)" *>> $log
