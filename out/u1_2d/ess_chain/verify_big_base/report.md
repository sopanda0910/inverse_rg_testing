# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.017 | 0.05 | plaquette | 0.96748 (0.00077) | 0.96843 (0.00017) | 0.96885 (0.0037) | -- |
| | | | | Q | -0.078125 (0.14) | -1.9621 (0.044) | -1.1406 (0.99) | -- |
| | | | | Q^2 | 1.1719 (0.23) | 3.907 (0.11) | 2.7969 (1.4) | -- |
| 16 | 55.0237 | 0.016 | 0.03 | plaquette | 0.99241 (0.0003) | 0.99211 (4.2e-06) | 0.99213 (5.1e-05) | -- |
| | | | | Q | -0.15625 (0.087) | 0.99411 (0.0072) | 0.46875 (0.55) | -- |
| | | | | Q^2 | 0.5 (0.083) | 0.99516 (0.0064) | 0.53125 (0.5) | -- |
| 32 | 55.0237 | 0.026 | 0.03 | plaquette | 0.99252 (0.00017) | 0.99269 (1.6e-05) | 0.99266 (4.5e-05) | -- |
| | | | | Q | -0.46875 (0.22) | 0.27983 (0.28) | 0.57812 (0.49) | -- |
| | | | | Q^2 | 3.3125 (0.51) | 0.27983 (0.28) | 0.57812 (0.49) | -- |
| 32 | 218.58 | 0.016 | 0.05 | plaquette | 0.99707 (9.9e-05) | 0.99785 (1.2e-07) | 0.99781 (0.00011) | -- |
| | | | | Q | -0.78125 (0.21) | -4.517e-06 (6.4e-06) | -0.046875 (0.63) | -- |
| | | | | Q^2 | 3.3125 (0.64) | 1.3553e-05 (1.9e-05) | 0.60938 (1.6) | -- |

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
| 16 | 14.1464 | 3319.03 | 3835.24 | -516.21 | 0.97 |
| 16 | 55.0237 | 12947.80 | 13517.04 | -569.24 | 0.99 |
| 32 | 55.0237 | 51706.19 | 54068.17 | -2361.98 | 0.77 |
| 32 | 218.58 | 207649.84 | 210552.87 | -2903.02 | 1.00 |