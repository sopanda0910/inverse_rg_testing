# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 8 | 8 | 0.023 | 0.05 | plaquette | 0.81169 (0.0064) | 0.88308 (0.0039) | 0.8765 (0.02) | -- |
| | | | | Q | -0.046875 (0.1) | -2.0847e-08 (4.6e-08) | -0.14062 (0.28) | -- |
| | | | | Q^2 | 0.67188 (0.11) | 7.7231e-08 (7.6e-08) | 0.14062 (0.28) | -- |
| 16 | 25 | 0.016 | 0.03 | plaquette | 0.92086 (0.0017) | 0.94936 (3e-14) | 0.94441 (0.0059) | -- |
| | | | | Q | 0.046875 (0.16) | -1 (4.5e-15) | -0.3125 (0.94) | -- |
| | | | | Q^2 | 1.5781 (0.27) | 1 (4.5e-15) | 1 (0) | -- |
| 32 | 14.1464 | 0.016 | 0.02 | plaquette | 0.87757 (0.0015) | 0.90109 (1.8e-08) | 0.90087 (0.0018) | -- |
| | | | | Q | 0.25 (0.38) | 6 (5.5e-05) | 5.75 (2) | -- |
| | | | | Q^2 | 8.9375 (1.6) | 36 (0.00027) | 35 (7.8) | -- |

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
| 8 | 8 | 479.86 | 603.91 | -124.05 | 0.82 |
| 16 | 25 | 5801.89 | 6386.71 | -584.82 | 1.00 |
| 32 | 14.1464 | 12928.54 | 15340.97 | -2412.43 | 1.00 |