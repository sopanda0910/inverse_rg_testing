# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 55.0237 | 0.016 | 0.10 | plaquette | 0.97766 (0.00087) | 0.99038 (3.7e-07) | 0.98821 (0.0019) | -- |
| | | | | Q | -0.29688 (0.13) | 5.7913e-06 (1.4e-05) | -0.32812 (0.45) | -- |
| | | | | Q^2 | 1.1719 (0.18) | 1.8375e-05 (2.2e-05) | 0.73438 (0.85) | -- |

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