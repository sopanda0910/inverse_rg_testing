# Exactness suite report

## Frontier (rkl2 checkpoint)

| case | ESS/N (fiber) | log-w std | i-MH acc | z(raw) plaq | z(rw) plaq | z(raw) Q^2 | z(rw) Q^2 |
|------|---------------|-----------|----------|-------------|------------|------------|-----------|
| 8:2 | 0.004 | 6.7 | 0.04 | +7.1 | +nan | -4.7 | +nan |
| 8:4 | 0.008 | 5.8 | 0.03 | +1.0 | +nan | +2.0 | +nan |
| 8:8 | 0.004 | 7.8 | 0.05 | -5.8 | +nan | +5.8 | +nan |
| 8:14.1464 | 0.004 | 7.4 | 0.04 | -5.3 | +nan | +8.5 | +nan |
| 16:4 | 0.004 | 11.7 | 0.01 | -0.3 | +nan | +3.5 | +nan |
| 16:8 | 0.006 | 14.4 | 0.05 | -13.4 | +nan | +5.8 | +nan |
| 16:14.1464 | 0.005 | 17.8 | 0.01 | -11.1 | +nan | +8.0 | +nan |
| 16:25 | 0.004 | 16.8 | 0.02 | -4.4 | +nan | +8.0 | +nan |
| 16:55.0237 | 0.006 | 30.6 | 0.01 | -8.0 | +nan | +12.2 | +nan |

## Low-beta check (original v2 checkpoint)

| case | ESS/N (fiber) | log-w std | i-MH acc | z(raw) plaq | z(rw) plaq | z(raw) Q^2 | z(rw) Q^2 |
|------|---------------|-----------|----------|-------------|------------|------------|-----------|
| 8:2 | 0.004 | 8.2 | 0.02 | +19.2 | +nan | -7.5 | +nan |
| 8:4 | 0.010 | 5.6 | 0.03 | +9.9 | +nan | +0.4 | +nan |
| 8:14.1464 | 0.004 | 9.2 | 0.03 | +1.8 | +nan | +5.8 | +nan |
| 16:4 | 0.004 | 13.5 | 0.00 | +12.7 | +nan | +2.0 | +nan |
| 16:14.1464 | 0.007 | 18.6 | 0.02 | +4.4 | +nan | +6.5 | +nan |

## SMC ladder

base 8:1.3472, n = 192, checkpoint `out/u1_2d/checkpoints/score_net_rkl2.pt`

| level | arm | ESS/N | log-w std | uniq | obs | raw z | SNIS z | resampled z |
|-------|-----|-------|-----------|------|-----|-------|--------|-------------|
| 16@4 | transport | 0.007 | 11.2 | -- | plaquette | -0.6 | +3.6 | -- |
| | | | | | Q^2 | +1.2 | -2.3 | -- |
| 16@4 | smc | 0.007 | 11.8 | 0.02 | plaquette | -1.8 | +4.2 | +2.9 |
| | | | | | Q^2 | +2.0 | -0.3 | -0.3 |
| 32@14.1464 | transport | 0.005 | 38.3 | -- | plaquette | -19.0 | -4643.3 | -- |
| | | | | | Q^2 | +6.5 | -32007.6 | -- |
| 32@14.1464 | smc | 0.005 | 40.0 | 0.01 | plaquette | -17.5 | -1300.7 | -- |
| | | | | | Q^2 | +6.4 | +311151.1 | -- |

z-scores vs exact character-expansion references (finite volume).
The SMC arm resamples by the per-level fiber weights before each next
lift; unique-ancestor fraction shows how much genuine diversity
survives resampling at this n (resampled sems use the unique count).
Validity per arm: at level 1 both arms' per-level weights are exact,
so SNIS there is noisy rather than biased. At level >= 2 that holds
only for the SMC arm (asymptotically, through resampling); the
transport arm's coarse ensemble is an unweighted lift with unknown
density, so its per-level SNIS corrects only the last lift and is
BIASED, not merely noisy.

## Free-energy certificate

log E[w] must equal the exact 2 L_f^2 log(2 pi) + log Z(beta_f, L_f)
- log Z(beta_c, L_c) from the character expansion (valid where the
coarse ensemble follows exp(-S_matched); see `valid` flags in
smc_results.json). Heavy-tailed weights bias the estimate low.

| level | arm | valid | log mean w | exact dF | gap | sem |
|-------|-----|-------|------------|----------|-----|-----|
| 16@4 | transport | True | 1061.01 | 1535.50 | -474.49 | 0.87 |
| 16@4 | smc | True | 1061.89 | 1535.50 | -473.61 | 0.89 |
| 32@14.1464 | transport | False | 13427.36 | 15340.97 | -1913.61 | 1.00 |
| 32@14.1464 | smc | True | 13425.45 | 15340.97 | -1915.52 | 1.00 |