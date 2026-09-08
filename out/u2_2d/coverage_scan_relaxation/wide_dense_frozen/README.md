# wide_dense scored against the FROZEN-supplement checkpoint

These are the scan outputs produced 2026-09-06/07 against
`det_score_net_wide_dense.pt` **as it stood before the 2026-09-07 retrain** --
i.e. the checkpoint trained on supplement rungs that carried no topological
coverage (all 128 configurations at a single sector, per-rung <Q^2> = 0.000).

They are kept, not deleted, because they are the control arm of a genuine
A/B: the corrected checkpoint is trained on the SAME couplings, the SAME
capacity and the SAME fixed rungs, differing only in whether the 31 supplement
rungs carry Q != 0 coverage (post-fix per-rung <Q^2> = 0.79-1.03).

Why the retrain was needed at all: `wide_dense.yaml` sets `resume: true`, the
resume file was already at epoch 120/120 from the pre-fix run, and the
retrain that was supposed to follow the 2026-09-06 data regeneration printed
`resuming from epoch 120` and did zero epochs. The data was corrected; the
model never saw it.

Numbers of record from this directory: seed resolves 15/28 at L=32 and
14/16 at L=64.
