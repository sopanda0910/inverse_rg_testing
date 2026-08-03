# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.016 | 0.11 | plaquette | 0.95612 (0.0011) | 0.96639 (1.2e-07) | 0.96309 (0.0037) | -- |
| | | | | Q | -0.14062 (0.12) | -2 (7.3e-06) | -0.125 (0.64) | -- |
| | | | | Q^2 | 0.89062 (0.14) | 4 (7.6e-06) | 1.5312 (0.77) | -- |
| 16 | 55.0237 | 0.016 | 0.06 | plaquette | 0.98801 (0.00028) | 0.9882 (1.4e-05) | 0.98819 (0.00033) | -- |
| | | | | Q | -0.4375 (0.1) | -0.0034924 (0.0049) | 0.015625 (0.086) | -- |
| | | | | Q^2 | 0.84375 (0.13) | 0.0034947 (0.0049) | 0.015625 (0.086) | -- |
| 32 | 55.0237 | 0.016 | 0.03 | plaquette | 0.98747 (0.00021) | 0.98907 (1.3e-10) | 0.9891 (0.00024) | -- |
| | | | | Q | -1.0469 (0.24) | -1.4474e-06 (2e-06) | -0.14062 (0.49) | -- |
| | | | | Q^2 | 4.6406 (0.78) | 5.7896e-06 (8.2e-06) | 0.26562 (0.96) | -- |
| 32 | 218.58 | 0.016 | 0.05 | plaquette | 0.97282 (0.0013) | 0.99115 (0) | 0.9903 (0.0024) | -- |
| | | | | Q | -0.875 (0.47) | -2 (0) | -1.4375 (0.88) | -- |
| | | | | Q^2 | 14.719 (3.6) | 4 (0) | 3.25 (3.6) | -- |

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