# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.016 | 0.08 | plaquette | 0.96232 (0.00087) | 0.97242 (2.2e-06) | 0.97118 (0.0026) | -- |
| | | | | Q | 0.29688 (0.17) | 0.99897 (0.0015) | 0.65625 (0.64) | -- |
| | | | | Q^2 | 1.9844 (0.37) | 1.001 (0.0015) | 1.5 (0.85) | -- |
| 16 | 55.0237 | 0.037 | 0.13 | plaquette | 0.98857 (0.00028) | 0.98952 (0.00042) | 0.99021 (0.00043) | -- |
| | | | | Q | 0.4375 (0.18) | 0.027184 (0.23) | -0.21875 (0.33) | -- |
| | | | | Q^2 | 2.2188 (0.39) | 0.32072 (0.25) | 0.5 (0.24) | -- |
| 32 | 55.0237 | 0.016 | 0.03 | plaquette | 0.98853 (0.00018) | 0.98984 (6.1e-09) | 0.98944 (0.00033) | -- |
| | | | | Q | 0.73438 (0.34) | 2 (3e-06) | -1.5 (2.9) | -- |
| | | | | Q^2 | 7.9219 (1.2) | 4 (1.6e-05) | 10.844 (6) | -- |
| 32 | 218.58 | 0.016 | 0.06 | plaquette | 0.96175 (0.00031) | 0.96559 (0) | 0.96537 (0.00057) | -- |
| | | | | Q | 1.7188 (0.27) | -3 (0) | -1.9375 (1.1) | -- |
| | | | | Q^2 | 7.6562 (1.2) | 9 (0) | 6.25 (2.8) | -- |

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
| 16 | 14.1464 | 2966.87 | 3835.24 | -868.37 | 1.00 |
| 16 | 55.0237 | 12585.31 | 13517.04 | -931.74 | 0.65 |
| 32 | 55.0237 | 50277.61 | 54068.17 | -3790.56 | 1.00 |
| 32 | 218.58 | 200895.11 | 210552.87 | -9657.76 | 1.00 |