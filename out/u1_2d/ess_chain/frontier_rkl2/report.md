# Reweighted observables via probability-flow ODE sampling

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 2 | 0.004 | 0.03 | plaquette | 0.72132 (0.0039) | 0.68562 (0.0002) | 0.69615 (0.029) | 0.69777 | +6.1 | -- |
| | | | | Q | 0.0078125 (0.063) | -0.99851 (0.0057) | -0.24219 (0.55) | 0 | +0.1 | -- |
| | | | | Q^2 | 1 (0.078) | 1.01 (0.015) | 1.1328 (0.61) | 1.2393 | -3.1 | -- |
| 8 | 4 | 0.004 | 0.02 | plaquette | 0.86533 (0.0025) | 0.89885 (2.4e-05) | 0.87943 (0.0078) | 0.86353 | +0.7 | -- |
| | | | | Q | -0.082031 (0.052) | -0.99901 (0.0012) | -0.33594 (0.3) | 0 | -1.6 | -- |
| | | | | Q^2 | 0.68359 (0.057) | 0.99913 (0.0011) | 0.33594 (0.3) | 0.48202 | +3.5 | -- |
| 8 | 8 | 0.006 | 0.02 | plaquette | 0.92416 (0.0016) | 0.94845 (0.0025) | 0.94107 (0.0093) | 0.93548 | -7.3 | -- |
| | | | | Q | 0.0039062 (0.04) | -0.12585 (0.13) | -0.25391 (0.26) | 0 | +0.1 | -- |
| | | | | Q^2 | 0.41797 (0.043) | 0.16542 (0.15) | 0.27734 (0.26) | 0.16777 | +5.8 | -- |
| 8 | 14.1464 | 0.009 | 0.05 | plaquette | 0.95844 (0.00092) | 0.95814 (0.004) | 0.9644 (0.0037) | 0.96441 | -6.5 | -- |
| | | | | Q | 0.039062 (0.035) | 0.05066 (0.095) | 0.20703 (0.23) | 0 | +1.1 | -- |
| | | | | Q^2 | 0.3125 (0.035) | 0.12663 (0.11) | 0.36328 (0.19) | 0.029101 | +8.1 | -- |
| 16 | 4 | 0.004 | 0.02 | plaquette | 0.8617 (0.0013) | 0.86387 (0.00042) | 0.87395 (0.0047) | 0.86352 | -1.4 | -- |
| | | | | Q | -0.015625 (0.1) | -0.95793 (0.055) | 0.57031 (0.84) | 0 | -0.2 | -- |
| | | | | Q^2 | 2.6797 (0.21) | 0.96143 (0.052) | 2.0859 (1.8) | 1.9339 | +3.5 | -- |
| 16 | 8 | 0.006 | 0.02 | plaquette | 0.92353 (0.00082) | 0.94853 (0.0039) | 0.94855 (0.0053) | 0.93524 | -14.3 | -- |
| | | | | Q | 0.050781 (0.084) | 0.79627 (0.21) | 0.80859 (0.29) | 0 | +0.6 | -- |
| | | | | Q^2 | 1.8086 (0.15) | 0.85893 (0.18) | 0.90234 (0.24) | 0.87006 | +6.4 | -- |
| 16 | 14.1464 | 0.008 | 0.02 | plaquette | 0.95789 (0.00047) | 0.96035 (0.0018) | 0.96118 (0.0022) | 0.96398 | -13.0 | -- |
| | | | | Q | 0.085938 (0.073) | -0.3729 (0.29) | -0.30859 (0.35) | 0 | +1.2 | -- |
| | | | | Q^2 | 1.3672 (0.12) | 0.39254 (0.3) | 0.46484 (0.36) | 0.47451 | +7.3 | -- |
| 16 | 25 | 0.008 | 0.03 | plaquette | 0.97824 (0.00025) | 0.97709 (0.00041) | 0.978 (0.00092) | 0.9798 | -6.1 | -- |
| | | | | Q | -0.12891 (0.064) | -0.44967 (0.47) | -0.61328 (0.26) | 0 | -2.0 | -- |
| | | | | Q^2 | 1.0508 (0.09) | 0.85567 (0.14) | 0.62109 (0.26) | 0.23539 | +9.1 | -- |
| 16 | 55.0237 | 0.004 | 0.02 | plaquette | 0.9896 (0.00012) | 0.99204 (2.1e-05) | 0.99203 (0.00039) | 0.9909 | -11.1 | -- |
| | | | | Q | -0.14062 (0.062) | -0.0031443 (0.0047) | -0.13672 (0.33) | 0 | -2.3 | -- |
| | | | | Q^2 | 1.0078 (0.1) | 0.0038543 (0.0052) | 0.30078 (0.29) | 0.029016 | +9.5 | -- |

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