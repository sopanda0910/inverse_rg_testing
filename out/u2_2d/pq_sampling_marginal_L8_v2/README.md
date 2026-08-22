# SUPERSEDED -- correct move, pre-rebuild statistics

The record is `../pq_sampling_marginal_L8_v3/` and
`../pq_sampling_marginal_L16_v3/`.

These used the MARGINAL odd move, which is the right one, but they were scored
before `07_pq_sampling.py`'s statistics were rebuilt on 2026-08-22: the odd-weight
error bar was a quadrature sum over correlated multinomial cells, the agreement
test was a quantity that was never chi-squared distributed, and `PARITY-STUCK`
was a significance gate rather than a flip count. The `_v2` runs in particular
report PARITY-STUCK and DISAGREES at couplings the rebuilt test scores as
SAMPLED with p = 0.287 and 0.612.

They also predate history saving, so they cannot be re-analysed -- which is why
they were re-run rather than re-scored, and why `--reanalyse` now exists.
