# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 2 | 0.004 | 0.04 | plaquette | 0.72389 (0.0037) | 0.54613 (5e-07) | 0.66509 (0.049) | 0.69777 | +7.1 | -- |
| | | | | Q | 0.0078125 (0.06) | 2 (6e-06) | 0.47266 (0.64) | 0 | +0.1 | -- |
| | | | | Q^2 | 0.91406 (0.069) | 4 (6e-06) | 2.2852 (0.69) | 1.2393 | -4.7 | -- |
| 8 | 4 | 0.008 | 0.03 | plaquette | 0.86605 (0.0024) | 0.87448 (0.0054) | 0.87062 (0.014) | 0.86353 | +1.0 | -- |
| | | | | Q | -0.078125 (0.049) | -0.76349 (0.19) | -0.8125 (0.29) | 0 | -1.6 | -- |
| | | | | Q^2 | 0.60938 (0.065) | 0.90733 (0.1) | 0.96875 (0.27) | 0.48202 | +2.0 | -- |
| 8 | 8 | 0.004 | 0.05 | plaquette | 0.92659 (0.0015) | 0.94937 (0.0011) | 0.94254 (0.0071) | 0.93548 | -5.8 | -- |
| | | | | Q | -0.042969 (0.041) | -0.049853 (0.066) | -0.019531 (0.14) | 0 | -1.0 | -- |
| | | | | Q^2 | 0.43359 (0.045) | 0.049881 (0.066) | 0.12109 (0.13) | 0.16777 | +5.8 | -- |
| 8 | 14.1464 | 0.004 | 0.04 | plaquette | 0.96016 (0.00081) | 0.96603 (4.3e-05) | 0.96667 (0.0015) | 0.96441 | -5.3 | -- |
| | | | | Q | 0.019531 (0.032) | 0.9681 (0.035) | 0.63672 (0.2) | 0 | +0.6 | -- |
| | | | | Q^2 | 0.26172 (0.028) | 0.97371 (0.029) | 0.63672 (0.2) | 0.029101 | +8.5 | -- |
| 16 | 4 | 0.004 | 0.01 | plaquette | 0.8632 (0.0013) | 0.86292 (8.4e-05) | 0.86261 (0.0025) | 0.86352 | -0.3 | -- |
| | | | | Q | 0.19922 (0.1) | -1.0025 (0.0041) | -0.98828 (0.19) | 0 | +1.9 | -- |
| | | | | Q^2 | 2.7383 (0.23) | 1.013 (0.016) | 1.0117 (0.19) | 1.9339 | +3.5 | -- |
| 16 | 8 | 0.006 | 0.05 | plaquette | 0.92445 (0.0008) | 0.9425 (0.0041) | 0.94014 (0.0027) | 0.93524 | -13.4 | -- |
| | | | | Q | -0.03125 (0.086) | 0.73889 (0.26) | -0.75 (0.55) | 0 | -0.4 | -- |
| | | | | Q^2 | 1.875 (0.17) | 0.76956 (0.25) | 2.3984 (0.65) | 0.87006 | +5.8 | -- |
| 16 | 14.1464 | 0.005 | 0.01 | plaquette | 0.95881 (0.00047) | 0.96092 (0.00079) | 0.96771 (0.0041) | 0.96398 | -11.1 | -- |
| | | | | Q | 0.10547 (0.076) | 0.040105 (0.074) | 0.67969 (0.52) | 0 | +1.4 | -- |
| | | | | Q^2 | 1.4727 (0.12) | 0.084421 (0.098) | 0.875 (0.27) | 0.47451 | +8.0 | -- |
| 16 | 25 | 0.004 | 0.02 | plaquette | 0.97874 (0.00024) | 0.97901 (0.00013) | 0.9803 (0.0017) | 0.9798 | -4.4 | -- |
| | | | | Q | -0.03125 (0.068) | -0.98138 (0.025) | -0.58203 (0.35) | 0 | -0.5 | -- |
| | | | | Q^2 | 1.1953 (0.12) | 0.9814 (0.025) | 0.58203 (0.35) | 0.23539 | +8.0 | -- |
| 16 | 55.0237 | 0.006 | 0.01 | plaquette | 0.98952 (0.00017) | 0.99127 (0.00032) | 0.99087 (0.0013) | 0.9909 | -8.0 | -- |
| | | | | Q | -0.054688 (0.067) | -0.0025156 (0.003) | 0 (0) | 0 | -0.8 | -- |
| | | | | Q^2 | 1.1562 (0.092) | 0.0026392 (0.0031) | 0 (0) | 0.029016 | +12.2 | -- |

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
| 8 | 4 | 272.65 | 383.88 | -111.23 | 0.71 |
| 8 | 8 | 499.80 | 603.91 | -104.11 | 0.95 |
| 8 | 14.1464 | 848.73 | 958.81 | -110.09 | 0.97 |
| 16 | 4 | 1068.52 | 1535.50 | -466.98 | 1.00 |
| 16 | 8 | 1952.84 | 2415.63 | -462.80 | 0.79 |
| 16 | 14.1464 | 3374.87 | 3835.24 | -460.37 | 0.92 |
| 16 | 25 | 5903.04 | 6386.71 | -483.67 | 0.98 |
| 16 | 55.0237 | 12996.07 | 13517.04 | -520.98 | 0.83 |