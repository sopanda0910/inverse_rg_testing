# AIS-corrected transport

basis rich11 (11 features), bridge steps 48, 2 HMC updates/step, Q-hops on, n = 96, split fit (fit even / quote odd)

| L | beta_f | fiber std (before) | ESS/N before | R^2_c (coarse) | surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | AIS ESS/N (all) | HMC acc | dF gap (sem) |
|---|--------|--------------------|--------------|----------------|---------------|--------------------|----------------------|-----------------|---------|--------------|
| 16 | 14.1464 | 17.0 | 0.0209 | 0.022 | 0.793 | 1124.80 | 0.021 | 0.010 | 0.79 | -672.92 (1.00) |
| 16 | 55.0237 | 17.6 | 0.0150 | 0.006 | 0.336 | 18.42 | 0.026 | 0.014 | 0.99 | -424.56 (0.86) |
| 32 | 55.0237 | 36.4 | 0.0104 | 0.064 | 0.709 | 17682.52 | 0.021 | 0.010 | 0.90 | -1652.44 (1.00) |
| 32 | 218.58 | 117.5 | 0.0104 | 0.003 | 0.845 | 45.34 | 0.021 | 0.010 | 0.99 | -2006.81 (1.00) |

## Measured mean density offset (free-energy identity)

E[log w] - dF_exact = -KL(q_eff || p) exactly, so the certificate's
KL fields are a direct unbiased measurement of the bulk offset the
whole ESS program bounds (the `gap` itself only closes at healthy ESS):

| L | beta_f | KL (nats) | sem | KL / site |
|---|--------|-----------|-----|-----------|
| 16 | 14.1464 | 3067.3 | 120.4 | 5.9908 |
| 16 | 55.0237 | 448.0 | 1.6 | 0.8750 |
| 32 | 55.0237 | 10926.7 | 1648.7 | 5.3353 |
| 32 | 218.58 | 2098.2 | 4.5 | 1.0245 |

## Sector-resolved plaquette (within-sector SNIS x exact P(Q))

The global weights degenerate on sector-frequency mismatch; conditioning
on Q removes it and the exactly known finite-volume P(Q) supplies the
sector masses (U(1)-specific -- labeled as the exact-P(Q) crutch).
E[Q^2] through sectors is exact by construction; plaquette is the test.

| L | beta_f | arm | estimate | err | z | covered mass | sectors used |
|---|--------|-----|----------|-----|---|--------------|--------------|
| 16 | 14.1464 | baseline | 0.968552 | 0.00069 | -- | 1.000 | 5 |
| 16 | 14.1464 | ais | 0.948256 | 3.9e-55 | -- | 0.983 | 3 |
| 16 | 55.0237 | baseline | 0.991338 | 0.00014 | -- | 1.000 | 4 |
| 16 | 55.0237 | ais | 0.992222 | 0.00011 | -- | 0.971 | 1 |
| 32 | 55.0237 | baseline | 0.990064 | 1.5e-06 | -- | 1.000 | 7 |
| 32 | 55.0237 | ais | 0.990727 | 2.6e-06 | -- | 0.983 | 3 |
| 32 | 218.58 | baseline | 0.994166 | 1.6e-15 | -- | 1.000 | 5 |
| 32 | 218.58 | ais | 0.997742 | 9.3e-08 | -- | 0.971 | 1 |

## Observables (AIS-weighted vs exact)

| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |
|---|--------|-----|-----|-------|-----|-------|-------|
| 16 | 14.1464 | plaquette | 0.95922 (0.0007) | -6.8 | 0.95354 (0) | -- | 0.96398 |
| | | Q^2 | 1.8333 (0.27) | +5.1 | 1 (0) | -- | 0.47451 |
| | | Q | 0.14583 (0.14) | +1.1 | 1 (0) | -- | 0 |
| 16 | 55.0237 | plaquette | 0.98968 (0.00017) | -7.0 | 0.99222 (0.00011) | -- | 0.9909 |
| | | Q^2 | 0.96875 (0.13) | +7.4 | 0 (0) | -- | 0.029016 |
| | | Q | -0.072917 (0.1) | -0.7 | 0 (0) | -- | 0 |
| 32 | 55.0237 | plaquette | 0.98961 (9.6e-05) | -13.2 | 0.99068 (6e-10) | -- | 0.99087 |
| | | Q^2 | 5.3646 (0.83) | +5.9 | 2.3416e-06 (3.3e-06) | -- | 0.47428 |
| | | Q | -0.34375 (0.24) | -1.5 | -2.3416e-06 (3.3e-06) | -- | 0 |
| 32 | 218.58 | plaquette | 0.99282 (6.2e-05) | -79.0 | 0.99774 (1.4e-07) | -- | 0.99771 |
| | | Q^2 | 5.5104 (0.82) | +6.7 | 1.3072e-17 (1.8e-17) | -- | 0.029011 |
| | | Q | -0.40625 (0.24) | -1.7 | -1.3072e-17 (1.8e-17) | -- | 0 |

Weights are valid AIS weights (Neal 2001) from the exact ODE density;
the surrogate fit residual on the held-out half is the irreducible
floor, the bridge increments shrink with more steps. z_AIS suppressed
when effective count < 4. The certificate's exact value here is
2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse
level integrates out of the AIS estimator exactly).