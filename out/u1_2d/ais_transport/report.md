# AIS-corrected transport

basis final7 (7 features), bridge steps 48, 2 HMC updates/step, Q-hops on, n = 96, split fit (fit even / quote odd)

| L | beta_f | fiber std (before) | ESS/N before | R^2_c (coarse) | surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | AIS ESS/N (all) | HMC acc | dF gap (sem) |
|---|--------|--------------------|--------------|----------------|---------------|--------------------|----------------------|-----------------|---------|--------------|
| 16 | 14.1464 | 23.7 | 0.0105 | 0.025 | 0.905 | 612.18 | 0.021 | 0.010 | 0.55 | -652.89 (1.00) |
| 16 | 55.0237 | 16.4 | 0.0104 | 0.100 | 0.526 | 43.63 | 0.021 | 0.010 | 0.98 | -386.67 (1.00) |
| 32 | 55.0237 | 43.9 | 0.0104 | 0.013 | 0.781 | 2540.21 | 0.021 | 0.010 | 0.76 | -2609.44 (1.00) |
| 32 | 218.58 | 121.1 | 0.0104 | 0.006 | 0.926 | 525.89 | 0.021 | 0.010 | 0.96 | -19876.64 (1.00) |

## Measured mean density offset (free-energy identity)

E[log w] - dF_exact = -KL(q_eff || p) exactly, so the certificate's
KL fields are a direct unbiased measurement of the bulk offset the
whole ESS program bounds (the `gap` itself only closes at healthy ESS):

| L | beta_f | KL (nats) | sem | KL / site |
|---|--------|-----------|-----|-----------|
| 16 | 14.1464 | 1839.4 | 64.5 | 3.5927 |
| 16 | 55.0237 | 437.2 | 4.1 | 0.8538 |
| 32 | 55.0237 | 6247.1 | 258.7 | 3.0503 |
| 32 | 218.58 | 20460.3 | 58.6 | 9.9904 |

## Sector-resolved plaquette (within-sector SNIS x exact P(Q))

The global weights degenerate on sector-frequency mismatch; conditioning
on Q removes it and the exactly known finite-volume P(Q) supplies the
sector masses (U(1)-specific -- labeled as the exact-P(Q) crutch).
E[Q^2] through sectors is exact by construction; plaquette is the test.

| L | beta_f | arm | estimate | err | z | covered mass | sectors used |
|---|--------|-----|----------|-----|---|--------------|--------------|
| 16 | 14.1464 | baseline | 0.966728 | 0.00073 | -- | 0.991 | 4 |
| 16 | 14.1464 | ais | 0.934881 | 3.6e-46 | -- | 0.991 | 4 |
| 16 | 55.0237 | baseline | 0.991951 | 3.3e-06 | -- | 1.000 | 4 |
| 16 | 55.0237 | ais | 0.990096 | 8.1e-07 | -- | 0.971 | 1 |
| 32 | 55.0237 | baseline | 0.990363 | 3.4e-05 | -- | 1.000 | 8 |
| 32 | 55.0237 | ais | 0.990663 | 2.3e-17 | -- | 0.983 | 3 |
| 32 | 218.58 | baseline | 0.993602 | 2.6e-16 | -- | 1.000 | 5 |
| 32 | 218.58 | ais | 0.997578 | 1.7e-31 | -- | 0.971 | 1 |

## Observables (AIS-weighted vs exact)

| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |
|---|--------|-----|-----|-------|-----|-------|-------|
| 16 | 14.1464 | plaquette | 0.95745 (0.00089) | -7.3 | 0.94225 (0) | -- | 0.96398 |
| | | Q^2 | 1.5104 (0.26) | +4.0 | 0 (0) | -- | 0.47451 |
| | | Q | -0.052083 (0.13) | -0.4 | 0 (0) | -- | 0 |
| 16 | 55.0237 | plaquette | 0.98984 (0.00018) | -5.9 | 0.9901 (7.9e-07) | -- | 0.9909 |
| | | Q^2 | 1.1354 (0.15) | +7.4 | 5.0832e-24 (0) | -- | 0.029016 |
| | | Q | -0.11458 (0.11) | -1.1 | -5.0832e-24 (0) | -- | 0 |
| 32 | 55.0237 | plaquette | 0.98966 (0.0001) | -11.8 | 0.98984 (1.2e-08) | -- | 0.99087 |
| | | Q^2 | 5.1667 (0.63) | +7.4 | 0.99999 (1.3e-05) | -- | 0.47428 |
| | | Q | -0.5625 (0.23) | -2.5 | 0.99999 (1.3e-05) | -- | 0 |
| 32 | 218.58 | plaquette | 0.99287 (6.3e-05) | -76.6 | 0.99758 (0) | -- | 0.99771 |
| | | Q^2 | 4.5625 (0.5) | +9.0 | 0 (0) | -- | 0.029011 |
| | | Q | -0.52083 (0.21) | -2.5 | 0 (0) | -- | 0 |

Weights are valid AIS weights (Neal 2001) from the exact ODE density;
the surrogate fit residual on the held-out half is the irreducible
floor, the bridge increments shrink with more steps. z_AIS suppressed
when effective count < 4. The certificate's exact value here is
2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse
level integrates out of the AIS estimator exactly).