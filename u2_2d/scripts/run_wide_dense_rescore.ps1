Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\wide_dense_rescore.log"
$py = ".venv\Scripts\python.exe"

# RE-SCORE wide_dense AGAINST THE CORRECTED CHECKPOINT.
#
# The previous scan matrix (preserved under wide_dense_frozen/, see its README)
# measured a checkpoint that had never been trained on the corrected data: the
# 2026-09-06 retrain hit `resume: true` with a completed epoch-120 resume file
# and did zero epochs. The checkpoint was retrained 2026-09-07.
#
# Budget 2, deliberately: the measured ceiling for this card is three CUDA
# contexts, and leaving one free lets the u1 retrain run without evicting
# anything. Each scan re-reads the script from disk at launch, so it picks up
# the current estimator (chi2/dof veto included) automatically.
"$(Get-Date) wide_dense re-score against corrected checkpoint" *>> $log
& $py "u2_2d\scripts\60_run_full_relaxation_matrix.py" --budget 2 --poll-seconds 30 *>> $log
"WIDE_DENSE RESCORE DONE $(Get-Date)" *>> $log
