# AIS-corrected transport

bridge steps 48, 2 HMC updates/step, Q-hops on, n = 96, split fit (fit even / quote odd)

| L | beta_f | fiber std (before) | ESS/N before | R^2_c (coarse) | surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | AIS ESS/N (all) | HMC acc | dF gap (sem) |
|---|--------|--------------------|--------------|----------------|---------------|--------------------|----------------------|-----------------|---------|--------------|
| 16 | 14.1464 | 17.0 | 0.0209 | 0.022 | 0.717 | 30.56 | 0.021 | 0.010 | 0.93 | -894.98 (1.00) |
| 16 | 55.0237 | 17.6 | 0.0150 | 0.006 | 0.332 | 18.58 | 0.024 | 0.011 | 0.99 | -420.92 (0.96) |
| 32 | 55.0237 | 36.4 | 0.0104 | 0.064 | 0.664 | 28.35 | 0.021 | 0.010 | 0.97 | -1636.66 (1.00) |
| 32 | 218.58 | 117.5 | 0.0104 | 0.003 | 0.839 | 44.74 | 0.021 | 0.010 | 0.99 | -1979.97 (1.00) |

## Observables (AIS-weighted vs exact)

| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |
|---|--------|-----|-----|-------|-----|-------|-------|
| 16 | 14.1464 | plaquette | 0.95922 (0.0007) | -6.8 | 0.96382 (1.1e-06) | -- | 0.96398 |
| | | Q^2 | 1.8333 (0.27) | +5.1 | 0.9998 (0.00028) | -- | 0.47451 |
| | | Q | 0.14583 (0.14) | +1.1 | 0.9998 (0.00028) | -- | 0 |
| 16 | 55.0237 | plaquette | 0.98968 (0.00017) | -7.0 | 0.99229 (3.7e-05) | -- | 0.9909 |
| | | Q^2 | 0.96875 (0.13) | +7.4 | 0 (0) | -- | 0.029016 |
| | | Q | -0.072917 (0.1) | -0.7 | 0 (0) | -- | 0 |
| 32 | 55.0237 | plaquette | 0.98961 (9.6e-05) | -13.2 | 0.99073 (6.5e-08) | -- | 0.99087 |
| | | Q^2 | 5.3646 (0.83) | +5.9 | 7.7222e-05 (0.00011) | -- | 0.47428 |
| | | Q | -0.34375 (0.24) | -1.5 | 7.7222e-05 (0.00011) | -- | 0 |
| 32 | 218.58 | plaquette | 0.99282 (6.2e-05) | -79.0 | 0.99769 (1.1e-10) | -- | 0.99771 |
| | | Q^2 | 5.5104 (0.82) | +6.7 | 4.3334e-16 (6.1e-16) | -- | 0.029011 |
| | | Q | -0.40625 (0.24) | -1.7 | -4.3334e-16 (6.1e-16) | -- | 0 |

Weights are valid AIS weights (Neal 2001) from the exact ODE density;
the surrogate fit residual on the held-out half is the irreducible
floor, the bridge increments shrink with more steps. z_AIS suppressed
when effective count < 4. The certificate's exact value here is
2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse
level integrates out of the AIS estimator exactly).