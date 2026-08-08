# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.020 | 0.10 | plaquette | 0.94948 (0.0012) | 0.95817 (0.00058) | 0.95818 (0.0031) | -- |
| | | | | Q | 0.14062 (0.17) | 0.87307 (0.14) | 0.1875 (0.43) | -- |
| | | | | Q^2 | 1.7656 (0.31) | 0.91593 (0.11) | 0.625 (0.27) | -- |
| 16 | 55.0237 | 0.035 | 0.10 | plaquette | 0.97454 (0.00084) | 0.98221 (0.0005) | 0.98157 (0.00064) | -- |
| | | | | Q | -0.015625 (0.1) | -0.61174 (0.29) | 0.10938 (0.2) | -- |
| | | | | Q^2 | 0.64062 (0.098) | 0.61177 (0.29) | 0.14062 (0.2) | -- |
| 32 | 55.0237 | 0.016 | 0.13 | plaquette | 0.9741 (0.00056) | 0.98029 (4.1e-12) | 0.97885 (0.00068) | -- |
| | | | | Q | 0.15625 (0.24) | 3 (1.1e-08) | 2.25 (0.69) | -- |
| | | | | Q^2 | 3.5938 (0.57) | 9 (2.1e-08) | 7.125 (1.7) | -- |
| 32 | 218.58 | 0.016 | 0.06 | plaquette | 0.97422 (0.0005) | 0.98208 (0) | 0.97977 (0.0012) | -- |
| | | | | Q | 0 (0.23) | -1 (0) | -1.4531 (0.95) | -- |
| | | | | Q^2 | 3.3125 (0.52) | 1 (0) | 3.9844 (1.3) | -- |

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

## Free-energy certificate

log E[w] vs the exact character-expansion Delta F
(2 L_f^2 log 2pi + log Z_f - log Z_c). An independent end-to-end
check of the weight chain against the solvable theory; heavy
tails bias the estimate LOW (rare dominant weights undersampled),
so agreement within a few sem certifies, disagreement of tens of
nats quantifies the same density gap the ESS sees.

| L | beta_f | log mean w | exact dF | gap | sem |
|---|--------|------------|----------|-----|-----|
| 16 | 14.1464 | 2939.84 | 3835.24 | -895.41 | 0.89 |
| 16 | 55.0237 | 12232.78 | 13517.04 | -1284.26 | 0.67 |
| 32 | 55.0237 | 48775.27 | 54068.17 | -5292.90 | 1.00 |
| 32 | 218.58 | 196675.72 | 210552.87 | -13877.15 | 1.00 |