Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$watchLog = "out\u2_2d\data_random_2000\gen.log"
$chainLog = "out\u1_2d\data_random_2000\chain_wait.log"
New-Item -ItemType Directory -Force -Path "out\u1_2d\data_random_2000" | Out-Null
"$(Get-Date) waiting for u2 random_rungs_2000 to finish before starting u1's" *>> $chainLog

while ($true) {
    if (Test-Path $watchLog) {
        $tail = Get-Content $watchLog -Tail 5 -ErrorAction SilentlyContinue
        if ($tail -match "PIPELINE DONE" -or $tail -match "FAILED") {
            "$(Get-Date) u2 job finished (or failed) -- starting u1 random_rungs_2000" *>> $chainLog
            break
        }
    }
    Start-Sleep -Seconds 60
}

Start-ScheduledTask -TaskName "u1_random_rungs_2000_local"
"$(Get-Date) u1_random_rungs_2000_local task started" *>> $chainLog
