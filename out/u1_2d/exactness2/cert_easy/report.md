# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 2 | 0.004 | 0.04 | plaquette | 0.72389 (0.0037) | 0.54613 (5e-07) | 0.66509 (0.049) | 0.69777 | +7.1 | -- |
| | | | | Q | 0.0078125 (0.06) | 2 (6e-06) | 0.47266 (0.64) | 0 | +0.1 | -- |
| | | | | Q^2 | 0.91406 (0.069) | 4 (6e-06) | 2.2852 (0.69) | 1.2393 | -4.7 | -- |

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
| 8 | 2 | 196.67 | 287.04 | -90.38 | 1.00 |