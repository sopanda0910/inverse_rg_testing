# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 32 | 14.1464 | 0.023 | 0.05 | plaquette | 0.95804 (0.00058) | 0.9632 (0.00039) | 0.96233 (0.0018) | 0.96398 | -10.3 | -- |
| | | | | Q | -0.078125 (0.26) | -1.1941 (0.22) | -1.0938 (0.6) | 0 | -0.3 | -- |
| | | | | Q^2 | 4.4219 (0.74) | 1.5822 (0.66) | 1.75 (2.6) | 1.904 | +3.4 | -- |
| 32 | 110 | 0.016 | 0.05 | plaquette | 0.98246 (0.00019) | 0.98499 (0) | 0.98449 (0.0005) | 0.99544 | -68.4 | -- |
| | | | | Q | 0.375 (0.25) | 2 (7.5e-23) | 1.1875 (1.6) | 0 | +1.5 | -- |
| | | | | Q^2 | 4.0312 (0.72) | 4 (1.5e-22) | 5.375 (3.3) | 0.19636 | +5.3 | -- |

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