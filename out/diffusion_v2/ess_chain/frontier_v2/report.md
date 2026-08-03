# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 2 | 0.005 | 0.02 | plaquette | 0.7463 (0.0039) | 0.69796 (0.0038) | 0.6879 (0.027) | 0.69777 | +12.5 | -- |
| | | | | Q | -0.015625 (0.061) | -1.0449 (0.079) | -0.39453 (0.74) | 0 | -0.3 | -- |
| | | | | Q^2 | 0.96094 (0.081) | 1.2229 (0.28) | 1.8242 (0.79) | 1.2393 | -3.4 | -- |
| 8 | 4 | 0.008 | 0.01 | plaquette | 0.88285 (0.0023) | 0.85294 (0.0078) | 0.85497 (0.011) | 0.86353 | +8.3 | -- |
| | | | | Q | -0.085938 (0.047) | 0.21508 (0.64) | 0.36719 (0.75) | 0 | -1.8 | -- |
| | | | | Q^2 | 0.57812 (0.043) | 0.99741 (0.0027) | 0.98438 (0.1) | 0.48202 | +2.2 | -- |
| 8 | 14.1464 | 0.012 | 0.02 | plaquette | 0.96805 (0.00079) | 0.97132 (0.0061) | 0.97333 (0.0036) | 0.96441 | +4.6 | -- |
| | | | | Q | -0.035156 (0.024) | 0.31788 (0.27) | -0.082031 (0.3) | 0 | -1.4 | -- |
| | | | | Q^2 | 0.15234 (0.023) | 0.37555 (0.27) | 0.27734 (0.26) | 0.029101 | +5.5 | -- |
| 16 | 4 | 0.007 | 0.03 | plaquette | 0.87674 (0.0013) | 0.88447 (0.004) | 0.87737 (0.0051) | 0.86352 | +10.3 | -- |
| | | | | Q | -0.082031 (0.094) | -0.72135 (0.25) | 0.039062 (0.48) | 0 | -0.9 | -- |
| | | | | Q^2 | 2.2773 (0.19) | 0.72165 (0.25) | 0.80469 (1.1) | 1.9339 | +1.8 | -- |
| 16 | 14.1464 | 0.004 | 0.02 | plaquette | 0.96534 (0.0005) | 0.97277 (3.6e-05) | 0.96903 (0.0027) | 0.96398 | +2.7 | -- |
| | | | | Q | 0.027344 (0.063) | -0.99555 (0.0061) | -0.39844 (0.65) | 0 | +0.4 | -- |
| | | | | Q^2 | 1.0273 (0.087) | 0.9958 (0.0059) | 1 (0) | 0.47451 | +6.3 | -- |

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