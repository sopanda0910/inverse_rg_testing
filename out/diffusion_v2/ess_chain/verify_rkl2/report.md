# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.016 | 0.10 | plaquette | 0.96039 (0.0008) | 0.96738 (3.1e-05) | 0.96259 (0.0027) | -- |
| | | | | Q | -0.078125 (0.13) | 0.0069032 (0.0096) | 0.40625 (0.51) | -- |
| | | | | Q^2 | 1.0469 (0.2) | 0.0069633 (0.0097) | 1 (0.94) | -- |
| 16 | 55.0237 | 0.016 | 0.03 | plaquette | 0.98948 (0.00025) | 0.99334 (3.5e-05) | 0.99209 (0.0018) | -- |
| | | | | Q | -0.0625 (0.14) | -0.99259 (0.0087) | -0.64062 (0.51) | -- |
| | | | | Q^2 | 1.3125 (0.21) | 0.99593 (0.0053) | 0.67188 (0.47) | -- |
| 32 | 55.0237 | 0.016 | 0.06 | plaquette | 0.98957 (0.00012) | 0.99061 (9.4e-08) | 0.98977 (0.00036) | -- |
| | | | | Q | -0.1875 (0.27) | -1.9999 (0.00021) | -0.39062 (0.57) | -- |
| | | | | Q^2 | 4.5625 (0.86) | 3.9997 (0.00042) | 0.82812 (1.1) | -- |
| 32 | 218.58 | 0.016 | 0.10 | plaquette | 0.99272 (6.4e-05) | 0.9934 (1.6e-16) | 0.99355 (0.00014) | -- |
| | | | | Q | -0.17188 (0.28) | -1.9501e-12 (2.8e-12) | -0.09375 (1.3) | -- |
| | | | | Q^2 | 4.8594 (1.1) | 3.9006e-12 (5.5e-12) | 5.3125 (2.4) | -- |

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