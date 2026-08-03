# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 55.0237 | 0.016 | 0.10 | plaquette | 0.98842 (0.00053) | 0.99377 (8.2e-08) | 0.99002 (0.0017) | -- |
| | | | | Q | -0.26562 (0.11) | -3.8014e-06 (1.6e-05) | 0.51562 (0.36) | -- |
| | | | | Q^2 | 0.76562 (0.11) | 2.1561e-05 (2.7e-05) | 0.67188 (0.26) | -- |

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