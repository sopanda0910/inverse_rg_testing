# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 2 | 0.004 | 0.02 | plaquette | 0.76397 (0.0034) | 0.69141 (2.9e-16) | 0.69204 (0.0098) | 0.69777 | +19.2 | -- |
| | | | | Q | 0.082031 (0.055) | 2 (8.9e-14) | 0.36328 (0.85) | 0 | +1.5 | -- |
| | | | | Q^2 | 0.77734 (0.062) | 4 (8.9e-14) | 2.3164 (0.87) | 1.2393 | -7.5 | -- |
| 8 | 4 | 0.010 | 0.03 | plaquette | 0.88541 (0.0022) | 0.87077 (0.0058) | 0.86655 (0.0091) | 0.86353 | +9.9 | -- |
| | | | | Q | -0.10156 (0.044) | -0.14629 (0.13) | -0.28125 (0.22) | 0 | -2.3 | -- |
| | | | | Q^2 | 0.5 (0.05) | 0.16218 (0.14) | 0.28125 (0.22) | 0.48202 | +0.4 | -- |
| 8 | 14.1464 | 0.004 | 0.03 | plaquette | 0.96619 (0.00099) | 0.96602 (3.5e-05) | 0.96747 (0.0012) | 0.96441 | +1.8 | -- |
| | | | | Q | -0.019531 (0.027) | 0.99556 (0.0052) | 0.57812 (0.32) | 0 | -0.7 | -- |
| | | | | Q^2 | 0.19141 (0.028) | 0.99589 (0.0049) | 0.69531 (0.24) | 0.029101 | +5.8 | -- |
| 16 | 4 | 0.004 | 0.00 | plaquette | 0.87888 (0.0012) | 0.90018 (0.0008) | 0.88968 (0.0026) | 0.86352 | +12.7 | -- |
| | | | | Q | 0.14453 (0.096) | 0.89485 (0.14) | -0.94531 (0.46) | 0 | +1.5 | -- |
| | | | | Q^2 | 2.3633 (0.21) | 0.99984 (0.00022) | 1 (0) | 1.9339 | +2.0 | -- |
| 16 | 14.1464 | 0.007 | 0.02 | plaquette | 0.96607 (0.00047) | 0.97057 (0.0013) | 0.97156 (0.0018) | 0.96398 | +4.4 | -- |
| | | | | Q | -0.12109 (0.067) | 0.28337 (0.65) | -0.50781 (0.56) | 0 | -1.8 | -- |
| | | | | Q^2 | 1.168 (0.11) | 0.9999 (0.00012) | 1.0469 (0.23) | 0.47451 | +6.5 | -- |

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
| 8 | 2 | 204.69 | 287.04 | -82.36 | 1.00 |
| 8 | 4 | 261.79 | 383.88 | -122.09 | 0.61 |
| 8 | 14.1464 | 841.33 | 958.81 | -117.48 | 1.00 |
| 16 | 4 | 1027.95 | 1535.50 | -507.55 | 0.95 |
| 16 | 14.1464 | 3324.39 | 3835.24 | -510.86 | 0.73 |