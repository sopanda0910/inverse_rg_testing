# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 8 | 0.026 | 0.08 | plaquette | 0.8047 (0.005) | 0.87546 (0.0086) | 0.87009 (0.0086) | 0.93548 | -26.0 | -- |
| | | | | Q | -0.14062 (0.12) | 1.5908e-07 (2.1e-07) | 0.03125 (0.11) | 0 | -1.2 | -- |
| | | | | Q^2 | 0.89062 (0.14) | 1.7015e-07 (2.1e-07) | 0.03125 (0.11) | 0.16777 | +5.2 | -- |
| 16 | 8 | 0.016 | 0.08 | plaquette | 0.80144 (0.0035) | 0.85615 (6e-08) | 0.85151 (0.0097) | 0.93524 | -37.9 | -- |
| | | | | Q | -0.1875 (0.2) | 1 (1.4e-07) | 0.48438 (0.41) | 0 | -0.9 | -- |
| | | | | Q^2 | 2.5938 (0.44) | 1 (1.4e-07) | 0.67188 (0.48) | 0.87006 | +4.0 | -- |
| 16 | 25 | 0.016 | 0.06 | plaquette | 0.90597 (0.0022) | 0.93974 (0) | 0.93677 (0.0063) | 0.9798 | -33.2 | -- |
| | | | | Q | 0.17188 (0.15) | 2 (4.7e-21) | 1.8594 (0.55) | 0 | +1.2 | -- |
| | | | | Q^2 | 1.3906 (0.21) | 4 (9.3e-21) | 4.0781 (1.1) | 0.23539 | +5.4 | -- |
| 32 | 14.1464 | 0.016 | 0.02 | plaquette | 0.86092 (0.0016) | 0.88041 (3.3e-10) | 0.8788 (0.0015) | 0.96398 | -66.4 | -- |
| | | | | Q | 0.46875 (0.42) | 1 (2.1e-06) | 2.375 (1.3) | 0 | +1.1 | -- |
| | | | | Q^2 | 11.312 (1.9) | 1 (2.2e-06) | 6.5 (5.2) | 1.904 | +5.0 | -- |
| 32 | 110 | 0.016 | 0.05 | plaquette | 0.95382 (0.00069) | 0.96585 (0) | 0.9645 (0.0021) | 0.99544 | -60.5 | -- |
| | | | | Q | 0.54688 (0.3) | 1 (0) | 1.1094 (0.25) | 0 | +1.8 | -- |
| | | | | Q^2 | 6.0156 (1.2) | 1 (0) | 1.3281 (0.76) | 0.19636 | +5.0 | -- |

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