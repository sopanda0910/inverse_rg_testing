# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 55.0237 | 0.016 | 0.11 | plaquette | 0.98868 (0.00045) | 0.99366 (2.5e-07) | 0.99161 (0.0012) | -- |
| | | | | Q | -0.32812 (0.1) | -2.9114e-05 (4.2e-05) | -0.078125 (0.14) | -- |
| | | | | Q^2 | 0.79688 (0.17) | 3.2285e-05 (4.5e-05) | 0.078125 (0.14) | -- |

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