# SUPERSEDED -- joint winding proposal AND three broken statistics

The record is `../pq_sampling_marginal_L8_v3/` and
`../pq_sampling_marginal_L16_v3/`.

Two independent reasons not to quote anything here.

**The move.** These runs used `--charge-step 2`, the JOINT proposal, whose odd
acceptance is 0.000. Their verdicts say where P(Q) could be sampled *by a move
that is no longer used*. Under the marginal odd move every coupling tested
SAMPLES, including L = 16 beta = 51.75 and 56 and L = 8 beta = 20, all of which
are labelled PARITY-STUCK here.

**The statistics.** Three defects, all fixed 2026-08-22 and all in
`07_pq_sampling.py`:
* `odd_z` summed per-sector bootstrap errors in QUADRATURE over multinomial
  cells, which are negatively correlated -- so every |odd_z| here is too small;
* the agreement test `chi2 < 2 * n_sectors` was never chi-squared distributed
  and rejected ~10% of datasets drawn from the exact distribution; and
* `PARITY-STUCK` was declared from `|odd_z| > 2`, a significance gate with
  essentially NO power on the pathology it names (measured: 5%, its null rate).

`48_verdict_calibration.py` measures the false-positive rate of the current
verdict against a synthetic null. These runs predate it.
