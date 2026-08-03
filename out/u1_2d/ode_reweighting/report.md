# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | HMC ref |
|---|--------|---------------|----------|-----|-----|------------|------|---------|
| 16 | 14.1464 | 0.023 | 0.08 | plaquette | 0.96627 (0.00081) | 0.97386 (0.0019) | 0.96744 (0.00068) | -- |
| | | | | Q | -0.15625 (0.12) | 0.76181 (0.23) | 0.29688 (0.082) | -- |
| | | | | Q^2 | 0.9375 (0.16) | 0.87462 (0.16) | 0.51562 (0.13) | -- |
| 16 | 55.0237 | 0.020 | 0.08 | plaquette | 0.99128 (0.00042) | 0.99276 (3.7e-05) | 0.99204 (0.00012) | -- |
| | | | | Q | -0.25 (0.11) | 0.87115 (0.15) | 0.1875 (0.073) | -- |
| | | | | Q^2 | 0.8125 (0.13) | 0.87136 (0.15) | 0.375 (0.061) | -- |
| 32 | 55.0237 | 0.018 | 0.08 | plaquette | 0.99113 (0.00021) | 0.99281 (6.9e-05) | 0.99267 (7.2e-05) | -- |
| | | | | Q | -0.28125 (0.19) | -1.8303 (0.22) | -1.8438 (0.06) | -- |
| | | | | Q^2 | 2.4688 (0.38) | 3.6606 (0.44) | 3.625 (0.17) | -- |
| 32 | 218.58 | 0.016 | 0.06 | plaquette | 0.9966 (9.5e-05) | 0.99726 (1.7e-07) | 0.99755 (2.4e-05) | -- |
| | | | | Q | -0.35938 (0.2) | 0.9997 (0.00043) | -0.25 (0.074) | -- |
| | | | | Q^2 | 2.5469 (0.48) | 0.9997 (0.00043) | 0.40625 (0.062) | -- |

Samples drawn from the probability-flow ODE (no charge projection, no
retherm); log q is the density of the ACTUAL samples, so the SNIS and
independence-Metropolis columns are asymptotically exact estimators of
the fine Wilson target. Errors: raw/i-MH naive sem (i-MH ignores chain
autocorrelation), reweighted linearized SNIS error. Low ESS/N or i-MH
acceptance means the exact estimators are noisy, not biased -- raw
columns stay the (biased) high-precision numbers.