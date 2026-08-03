# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.016 | 0.03 | plaquette | 0.95489 (0.0013) | 0.96891 (1.6e-06) | 0.96844 (0.0029) | -- |
| | | | | Q | -0.046875 (0.15) | -1.9989 (0.0015) | -1.9375 (0.24) | -- |
| | | | | Q^2 | 1.4844 (0.24) | 3.9979 (0.003) | 3.8125 (0.72) | -- |
| 16 | 55.0237 | 0.016 | 0.08 | plaquette | 0.99322 (0.00037) | 0.99506 (0) | 0.99395 (0.00046) | -- |
| | | | | Q | -0.0625 (0.083) | 1 (8.6e-21) | 0.8125 (0.24) | -- |
| | | | | Q^2 | 0.4375 (0.083) | 1 (8.6e-21) | 0.8125 (0.24) | -- |
| 32 | 55.0237 | 0.016 | 0.03 | plaquette | 0.99175 (0.00032) | 0.99455 (9.7e-22) | 0.99413 (0.00057) | -- |
| | | | | Q | -0.46875 (0.21) | -2 (3.3e-18) | -0.90625 (1.1) | -- |
| | | | | Q^2 | 2.875 (0.42) | 4 (6.6e-18) | 2 (1.9) | -- |
| 32 | 218.58 | 0.016 | 0.08 | plaquette | 0.9971 (0.00013) | 0.99798 (8e-09) | 0.99772 (0.0003) | -- |
| | | | | Q | 0.25 (0.22) | -1 (1.5e-05) | -0.46875 (0.69) | -- |
| | | | | Q^2 | 3.0625 (0.5) | 1 (4.6e-05) | 1.4688 (0.68) | -- |

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