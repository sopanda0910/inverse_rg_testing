Set-Location "C:\Users\ompan\Desktop\Lattice QCD\inverse_rg_testing"
$log = "out\u2_2d\wide_dense_retrain.log"
$py = ".venv\Scripts\python.exe"
$env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"

# RETRAIN wide_dense ON THE CORRECTED DATA.
#
# The data was regenerated with sector augmentation on 2026-09-06 (per-rung
# <Q^2> went 0.000 -> 0.79-1.03, i.e. the supplement rungs finally carry
# Q != 0 coverage), but the retrain that followed did NOTHING: wide_dense.yaml
# sets `resume: true`, the resume file from the PREVIOUS run was already at
# epoch 120 of 120, and the trainer printed "resuming from epoch 120" and
# exited. So the checkpoint scored all through 2026-09-06/07 was still the one
# trained on the FROZEN ensembles.
#
# The stale resume file has been moved aside and the frozen-data checkpoint
# preserved as det_score_net_wide_dense_frozen.pt -- deliberately, because it
# turns an accident into a controlled A/B: identical capacity, identical fixed
# rungs, identical supplement COUPLINGS, differing only in whether those
# supplement rungs carry topological coverage.
#
# LESSON, and the reason this is worth a comment rather than a quiet fix:
# `resume: true` plus a completed resume file silently converts a retrain into
# a no-op. It is safe when the DATA is unchanged (its intended use, recovering
# from an OOM) and silently wrong the moment the data changes underneath it.
# A data-regeneration step must invalidate the resume state; it did not.
& $py "u2_2d\scripts\02_train.py" --config "u2_2d\configs\wide_dense.yaml" --device cuda *>> $log
if ($LASTEXITCODE -ne 0) { "$(Get-Date) FAILED (train), exit $LASTEXITCODE" *>> $log; exit 1 }
"WIDE_DENSE RETRAIN DONE $(Get-Date)" *>> $log
