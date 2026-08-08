# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.019 | 0.08 | plaquette | 0.96203 (0.00079) | 0.96522 (0.00034) | 0.96748 (0.0023) | -- |
| | | | | Q | -0.078125 (0.14) | -1.7651 (0.26) | -0.32812 (0.88) | -- |
| | | | | Q^2 | 1.2656 (0.23) | 3.8957 (0.19) | 2.1406 (1.1) | -- |
| 16 | 55.0237 | 0.016 | 0.03 | plaquette | 0.99182 (0.00025) | 0.99307 (7.1e-07) | 0.99211 (0.00095) | -- |
| | | | | Q | -0.29688 (0.091) | -2.5459e-05 (3.1e-05) | -0.03125 (0.17) | -- |
| | | | | Q^2 | 0.60938 (0.099) | 2.546e-05 (3.1e-05) | 0.03125 (0.17) | -- |
| 32 | 55.0237 | 0.017 | 0.06 | plaquette | 0.99207 (0.00014) | 0.99164 (8.1e-06) | 0.99162 (9.7e-05) | -- |
| | | | | Q | -0.95312 (0.22) | -2.9018 (0.11) | -1.7969 (1.1) | -- |
| | | | | Q^2 | 3.9531 (0.76) | 8.7309 (0.3) | 5.6094 (3) | -- |
| 32 | 218.58 | 0.016 | 0.05 | plaquette | 0.99365 (0.00014) | 0.9951 (0) | 0.99499 (0.00028) | -- |
| | | | | Q | -0.76562 (0.21) | 7.564e-25 (0) | -0.15625 (0.57) | -- |
| | | | | Q^2 | 3.4219 (0.52) | 1.5128e-24 (0) | 0.53125 (2) | -- |

Samples drawn from the probability-flow ODE (no charge projection, no
retherm); log q is the density of the ACTUAL samples, so the SNIS and
independence-Metropolis columns are exact estimators of the fine Wilson
target in the n_steps -> inf, exact-divergence limit. At finite
settings two residual biases remain (they shrink with steps/probes,
NOT with more samples): the Heun trapezoid approximates the discrete
map's true log-Jacobian, and Hutchinson noise is unbiased in log q but
biases the exponentiated weights (Jensen). Check stability under
doubled --ode-steps and increased --n-probes (or --n-probes 0) before
quoting. Errors: raw naive sem; i-MH sem inflated by the
low-acceptance autocorrelation factor sqrt((2-a)/a); reweighted
linearized SNIS error. Low ESS/N or i-MH acceptance makes the exact
estimators noisy -- raw columns stay the (biased) high-precision
numbers.

## Free-energy certificate

log E[w] vs the exact character-expansion Delta F
(2 L_f^2 log 2pi + log Z_f - log Z_c). An independent end-to-end
check of the weight chain against the solvable theory; heavy
tails bias the estimate LOW (rare dominant weights undersampled),
so agreement within a few sem certifies, disagreement of tens of
nats quantifies the same density gap the ESS sees.

| L | beta_f | log mean w | exact dF | gap | sem |
|---|--------|------------|----------|-----|-----|
| 16 | 14.1464 | 3341.74 | 3835.24 | -493.51 | 0.92 |
| 16 | 55.0237 | 12971.73 | 13517.04 | -545.31 | 1.00 |
| 32 | 55.0237 | 51786.33 | 54068.17 | -2281.84 | 0.97 |
| 32 | 218.58 | 207690.15 | 210552.87 | -2862.71 | 1.00 |