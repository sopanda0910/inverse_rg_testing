# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.021 | 0.08 | plaquette | 0.96625 (0.00094) | 0.96999 (0.00089) | 0.96998 (0.0028) | -- |
| | | | | Q | -0.09375 (0.15) | 0.81686 (0.22) | 0.82812 (0.34) | -- |
| | | | | Q^2 | 1.3438 (0.19) | 1.0194 (0.022) | 0.98438 (0.077) | -- |
| 16 | 55.0237 | 0.016 | 0.05 | plaquette | 0.99172 (0.00035) | 0.99267 (6e-08) | 0.99259 (0.0011) | -- |
| | | | | Q | -0.03125 (0.11) | 1.4302e-07 (2e-07) | 0.046875 (0.22) | -- |
| | | | | Q^2 | 0.71875 (0.12) | 1.4705e-07 (2.1e-07) | 0.078125 (0.22) | -- |
| 32 | 55.0237 | 0.016 | 0.11 | plaquette | 0.992 (0.00013) | 0.99262 (8.9e-06) | 0.99266 (0.00041) | -- |
| | | | | Q | 0.32812 (0.21) | 1.0101 (0.014) | 0.60938 (0.55) | -- |
| | | | | Q^2 | 2.9531 (0.47) | 1.0403 (0.057) | 1.4844 (1.1) | -- |
| 32 | 218.58 | 0.016 | 0.03 | plaquette | 0.99514 (0.00013) | 0.99613 (4e-17) | 0.99602 (0.0002) | -- |
| | | | | Q | -0.078125 (0.23) | 2.8095e-13 (4e-13) | 0.70312 (1.3) | -- |
| | | | | Q^2 | 3.2656 (0.64) | 5.619e-13 (7.9e-13) | 2.1094 (3.8) | -- |

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