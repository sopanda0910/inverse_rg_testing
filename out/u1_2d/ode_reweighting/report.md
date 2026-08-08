# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.016 | 0.02 | plaquette | 0.96582 (0.00079) | 0.96657 (1.6e-05) | 0.96349 (0.0045) | -- |
| | | | | Q | -0.1875 (0.14) | -0.99412 (0.0073) | -0.03125 (1.4) | -- |
| | | | | Q^2 | 1.25 (0.21) | 1.0004 (0.00046) | 1 (0) | -- |
| 16 | 55.0237 | 0.016 | 0.05 | plaquette | 0.99098 (0.00043) | 0.99241 (2.7e-05) | 0.99235 (0.00061) | -- |
| | | | | Q | -0.23438 (0.096) | 0.98081 (0.026) | 0.92188 (0.3) | -- |
| | | | | Q^2 | 0.64062 (0.098) | 0.99945 (0.00068) | 0.98438 (0.1) | -- |
| 32 | 55.0237 | 0.016 | 0.11 | plaquette | 0.99145 (0.00018) | 0.99326 (5.5e-12) | 0.99279 (0.00041) | -- |
| | | | | Q | -0.625 (0.21) | -8.3915e-09 (1.8e-08) | -0.65625 (0.64) | -- |
| | | | | Q^2 | 3.1562 (0.4) | 3.608e-08 (4.7e-08) | 1.9375 (0.91) | -- |
| 32 | 218.58 | 0.016 | 0.06 | plaquette | 0.99647 (9.5e-05) | 0.99718 (3.7e-23) | 0.99714 (0.00014) | -- |
| | | | | Q | -0.70312 (0.19) | -2 (0) | -1.0156 (0.67) | -- |
| | | | | Q^2 | 2.8281 (0.51) | 4 (0) | 1.9531 (1.3) | -- |

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
| 16 | 14.1464 | 3377.36 | 3835.24 | -457.88 | 1.00 |
| 16 | 55.0237 | 12983.64 | 13517.04 | -533.40 | 0.98 |
| 32 | 55.0237 | 51906.54 | 54068.17 | -2161.63 | 1.00 |
| 32 | 218.58 | 207326.47 | 210552.87 | -3226.40 | 1.00 |