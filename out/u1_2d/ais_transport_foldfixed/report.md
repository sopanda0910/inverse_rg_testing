# AIS-corrected transport

basis final7 (7 features), bridge steps 48, 2 HMC updates/step, Q-hops on, n = 96, split fit (fit even / quote odd)

| L | beta_f | fiber std (before) | ESS/N before | R^2_c (coarse) | surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | AIS ESS/N (all) | HMC acc | dF gap (sem) |
|---|--------|--------------------|--------------|----------------|---------------|--------------------|----------------------|-----------------|---------|--------------|
| 16 | 14.1464 | 17.3 | 0.0105 | 0.071 | 0.748 | 117.10 | 0.021 | 0.010 | 0.96 | -2327.14 (1.00) |
| 16 | 55.0237 | 30.0 | 0.0110 | 0.007 | 0.877 | 228.53 | 0.021 | 0.010 | 0.98 | -581.88 (1.00) |
| 32 | 55.0237 | 78.0 | 0.0104 | 0.034 | 0.941 | 6439.08 | 0.021 | 0.010 | 0.82 | -2743.60 (1.00) |
| 32 | 218.58 | 118.6 | 0.0104 | 0.011 | 0.879 | 2131.73 | 0.023 | 0.011 | 0.98 | -2638.52 (0.96) |

## Measured mean density offset (free-energy identity)

E[log w] - dF_exact = -KL(q_eff || p) exactly, so the certificate's
KL fields are a direct unbiased measurement of the bulk offset the
whole ESS program bounds (the `gap` itself only closes at healthy ESS):

| L | beta_f | KL (nats) | sem | KL / site |
|---|--------|-----------|-----|-----------|
| 16 | 14.1464 | 2797.9 | 13.5 | 5.4646 |
| 16 | 55.0237 | 983.2 | 21.0 | 1.9204 |
| 32 | 55.0237 | 11669.8 | 645.3 | 5.6981 |
| 32 | 218.58 | 3216.8 | 175.3 | 1.5707 |

## Sector-resolved plaquette (within-sector SNIS x exact P(Q))

The global weights degenerate on sector-frequency mismatch; conditioning
on Q removes it and the exactly known finite-volume P(Q) supplies the
sector masses (U(1)-specific -- labeled as the exact-P(Q) crutch).
E[Q^2] through sectors is exact by construction; plaquette is the test.

| L | beta_f | arm | estimate | err | z | covered mass | sectors used |
|---|--------|-----|----------|-----|---|--------------|--------------|
| 16 | 14.1464 | baseline | 0.964161 | 0.0012 | -- | 1.000 | 5 |
| 16 | 14.1464 | ais | 0.964496 | 4.7e-24 | -- | 0.983 | 3 |
| 16 | 55.0237 | baseline | 0.993324 | 1.8e-05 | -- | 1.000 | 3 |
| 16 | 55.0237 | ais | 0.989385 | 9.6e-24 | -- | 0.971 | 1 |
| 32 | 55.0237 | baseline | 0.992088 | 1e-06 | -- | 0.991 | 5 |
| 32 | 55.0237 | ais | 0.98998 | 1.8e-44 | -- | 0.983 | 3 |
| 32 | 218.58 | baseline | 0.997112 | 2.8e-18 | -- | 1.000 | 5 |
| 32 | 218.58 | ais | 0.997613 | 3.7e-06 | -- | 0.971 | 1 |

## Observables (AIS-weighted vs exact)

| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |
|---|--------|-----|-----|-------|-----|-------|-------|
| 16 | 14.1464 | plaquette | 0.96551 (0.00072) | +2.1 | 0.96533 (0) | -- | 0.96398 |
| | | Q^2 | 1.3646 (0.2) | +4.6 | 1 (0) | -- | 0.47451 |
| | | Q | -0.13542 (0.12) | -1.1 | 1 (0) | -- | 0 |
| 16 | 55.0237 | plaquette | 0.99117 (0.00027) | +1.0 | 0.98939 (0) | -- | 0.9909 |
| | | Q^2 | 0.58333 (0.081) | +6.9 | 0 (0) | -- | 0.029016 |
| | | Q | -0.125 (0.077) | -1.6 | 0 (0) | -- | 0 |
| 32 | 55.0237 | plaquette | 0.99112 (0.00017) | +1.4 | 0.99035 (0) | -- | 0.99087 |
| | | Q^2 | 3.6979 (0.51) | +6.4 | 1 (0) | -- | 0.47428 |
| | | Q | -0.63542 (0.19) | -3.4 | 1 (0) | -- | 0 |
| 32 | 218.58 | plaquette | 0.99655 (6.2e-05) | -18.7 | 0.99761 (3.6e-06) | -- | 0.99771 |
| | | Q^2 | 3.0833 (0.4) | +7.5 | 3.2732e-29 (0) | -- | 0.029011 |
| | | Q | -0.5625 (0.17) | -3.3 | 3.2732e-29 (0) | -- | 0 |

Weights are valid AIS weights (Neal 2001) from the exact ODE density;
the surrogate fit residual on the held-out half is the irreducible
floor, the bridge increments shrink with more steps. z_AIS suppressed
when effective count < 4. The certificate's exact value here is
2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse
level integrates out of the AIS estimator exactly).