# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.016 | 0.03 | plaquette | 0.958 (0.001) | 0.97125 (7.6e-08) | 0.96832 (0.0068) | -- |
| | | | | Q | 0.015625 (0.15) | 0.99998 (2.2e-05) | 1.0312 (0.17) | -- |
| | | | | Q^2 | 1.3281 (0.22) | 1 (1.8e-05) | 1.0938 (0.52) | -- |
| 16 | 55.0237 | 0.016 | 0.14 | plaquette | 0.98965 (0.00025) | 0.99253 (8.5e-07) | 0.99116 (0.00077) | -- |
| | | | | Q | -0.015625 (0.14) | -0.00019149 (0.00026) | -0.10938 (0.36) | -- |
| | | | | Q^2 | 1.2031 (0.22) | 0.00019343 (0.00026) | 0.64062 (0.29) | -- |
| 32 | 55.0237 | 0.016 | 0.05 | plaquette | 0.98959 (0.00015) | 0.99064 (1.7e-05) | 0.99062 (0.00012) | -- |
| | | | | Q | -0.45312 (0.28) | 1.0443 (0.062) | 0.078125 (0.8) | -- |
| | | | | Q^2 | 5.0781 (1) | 1.1809 (0.25) | 0.98438 (1.1) | -- |
| 32 | 218.58 | 0.016 | 0.14 | plaquette | 0.99285 (8.4e-05) | 0.99435 (8.4e-23) | 0.99411 (0.00018) | -- |
| | | | | Q | -0.90625 (0.27) | -1 (1e-19) | -0.64062 (0.46) | -- |
| | | | | Q^2 | 5.5 (1.2) | 1 (3.1e-19) | 1.4531 (0.91) | -- |

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
| 16 | 14.1464 | 3372.48 | 3835.24 | -462.76 | 1.00 |
| 16 | 55.0237 | 13001.26 | 13517.04 | -515.78 | 1.00 |
| 32 | 55.0237 | 51933.24 | 54068.17 | -2134.93 | 0.98 |
| 32 | 218.58 | 207635.87 | 210552.87 | -2916.99 | 1.00 |