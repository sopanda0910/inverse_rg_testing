# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 32 | 14.1464 | 0.032 | 0.03 | plaquette | 0.95868 (0.00053) | 0.9629 (0.0016) | 0.96233 (0.0028) | 0.96398 | -9.9 | -- |
| | | | | Q | -0.64062 (0.31) | -0.87455 (0.68) | -0.78125 (0.97) | 0 | -2.0 | -- |
| | | | | Q^2 | 6.5781 (1.1) | 1.7491 (1.4) | 1.5625 (1.9) | 1.904 | +4.3 | -- |
| 32 | 110 | 0.016 | 0.05 | plaquette | 0.9827 (0.00014) | 0.98504 (5.6e-17) | 0.98475 (0.00039) | 0.99544 | -90.8 | -- |
| | | | | Q | 0.875 (0.25) | 8.1393e-14 (1.2e-13) | 0.82812 (0.73) | 0 | +3.5 | -- |
| | | | | Q^2 | 4.7188 (0.75) | 8.1486e-14 (1.2e-13) | 1.5156 (1.4) | 0.19636 | +6.1 | -- |

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
| 32 | 14.1464 | 13426.36 | 15340.97 | -1914.61 | 0.69 |
| 32 | 110 | 103888.76 | 106579.67 | -2690.91 | 1.00 |