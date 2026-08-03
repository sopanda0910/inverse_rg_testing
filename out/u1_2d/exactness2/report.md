# Exactness follow-up report

## Certificate closure at healthy ESS (8:2)

| L | beta_f | ESS/N (fiber) | i-MH acc | obs | raw | reweighted | i-MH | exact | z(raw) | z(rw) |
|---|--------|---------------|----------|-----|-----|------------|------|---------|--|--|
| 8 | 2 | 0.004 | 0.03 | plaquette | 0.72132 (0.0039) | 0.68562 (0.0002) | 0.69615 (0.029) | 0.69777 | +6.1 | -- |
| | | | | Q | 0.0078125 (0.063) | -0.99851 (0.0057) | -0.24219 (0.55) | 0 | +0.1 | -- |
| | | | | Q^2 | 1 (0.078) | 1.01 (0.015) | 1.1328 (0.61) | 1.2393 | -3.1 | -- |

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
| 8 | 2 | 188.11 | 287.04 | -98.94 | 0.99 |

## AIS with rich basis + sector resolution

bridge steps 48, 2 HMC updates/step, Q-hops on, n = 96, split fit (fit even / quote odd)

| L | beta_f | fiber std (before) | ESS/N before | R^2_c (coarse) | surrogate R^2 | AIS std (held-out) | AIS ESS/N (held-out) | AIS ESS/N (all) | HMC acc | dF gap (sem) |
|---|--------|--------------------|--------------|----------------|---------------|--------------------|----------------------|-----------------|---------|--------------|
| 16 | 14.1464 | 17.0 | 0.0209 | 0.022 | 0.793 | 1120.38 | 0.021 | 0.010 | 0.79 | -663.61 (1.00) |
| 16 | 55.0237 | 17.6 | 0.0150 | 0.006 | 0.336 | 18.44 | 0.026 | 0.014 | 0.99 | -424.56 (0.86) |
| 32 | 55.0237 | 36.4 | 0.0104 | 0.064 | 0.709 | 18650.61 | 0.021 | 0.010 | 0.90 | -1653.28 (1.00) |
| 32 | 218.58 | 117.5 | 0.0104 | 0.003 | 0.845 | 45.35 | 0.021 | 0.010 | 0.99 | -2006.56 (1.00) |

## Measured mean density offset (free-energy identity)

E[log w] - dF_exact = -KL(q_eff || p) exactly, so the certificate's
KL fields are a direct unbiased measurement of the bulk offset the
whole ESS program bounds (the `gap` itself only closes at healthy ESS):

| L | beta_f | KL (nats) | sem | KL / site |
|---|--------|-----------|-----|-----------|
| 16 | 14.1464 | 3056.2 | 120.7 | 5.9692 |
| 16 | 55.0237 | 448.0 | 1.6 | 0.8750 |
| 32 | 55.0237 | 11605.6 | 1780.9 | 5.6668 |
| 32 | 218.58 | 2098.1 | 4.5 | 1.0245 |

## Sector-resolved plaquette (within-sector SNIS x exact P(Q))

The global weights degenerate on sector-frequency mismatch; conditioning
on Q removes it and the exactly known finite-volume P(Q) supplies the
sector masses (U(1)-specific -- labeled as the exact-P(Q) crutch).
E[Q^2] through sectors is exact by construction; plaquette is the test.

| L | beta_f | arm | estimate | err | z | covered mass | sectors used |
|---|--------|-----|----------|-----|---|--------------|--------------|
| 16 | 14.1464 | baseline | 0.968552 | 0.00069 | +6.6 | 1.000 | 5 |
| 16 | 14.1464 | ais | 0.947182 | 3.1e-39 | -5374214465043059817735361913038045184.0 | 0.983 | 3 |
| 16 | 55.0237 | baseline | 0.991338 | 0.00014 | +3.1 | 1.000 | 4 |
| 16 | 55.0237 | ais | 0.992222 | 0.00011 | +11.9 | 0.971 | 1 |
| 32 | 55.0237 | baseline | 0.990064 | 1.5e-06 | -537.7 | 1.000 | 7 |
| 32 | 55.0237 | ais | 0.990711 | 5.6e-07 | -285.3 | 0.983 | 3 |
| 32 | 218.58 | baseline | 0.994166 | 1.6e-15 | -2222963409437.6 | 1.000 | 5 |
| 32 | 218.58 | ais | 0.997724 | 2.2e-08 | +597.2 | 0.971 | 1 |

## Observables (AIS-weighted vs exact)

| L | beta_f | obs | raw | z_raw | AIS | z_AIS | exact |
|---|--------|-----|-----|-------|-----|-------|-------|
| 16 | 14.1464 | plaquette | 0.95922 (0.0007) | -6.8 | 0.95367 (0) | -- | 0.96398 |
| | | Q^2 | 1.8333 (0.27) | +5.1 | 1 (0) | -- | 0.47451 |
| | | Q | 0.14583 (0.14) | +1.1 | 1 (0) | -- | 0 |
| 16 | 55.0237 | plaquette | 0.98968 (0.00017) | -7.0 | 0.99222 (0.00011) | -- | 0.9909 |
| | | Q^2 | 0.96875 (0.13) | +7.4 | 0 (0) | -- | 0.029016 |
| | | Q | -0.072917 (0.1) | -0.7 | 0 (0) | -- | 0 |
| 32 | 55.0237 | plaquette | 0.98961 (9.6e-05) | -13.2 | 0.99065 (1.5e-09) | -- | 0.99087 |
| | | Q^2 | 5.3646 (0.83) | +5.9 | 4.6569e-06 (6.6e-06) | -- | 0.47428 |
| | | Q | -0.34375 (0.24) | -1.5 | -4.6569e-06 (6.6e-06) | -- | 0 |
| 32 | 218.58 | plaquette | 0.99282 (6.2e-05) | -79.0 | 0.99772 (6.1e-08) | -- | 0.99771 |
| | | Q^2 | 5.5104 (0.82) | +6.7 | 1.0241e-17 (1.4e-17) | -- | 0.029011 |
| | | Q | -0.40625 (0.24) | -1.7 | -1.0241e-17 (1.4e-17) | -- | 0 |

Weights are valid AIS weights (Neal 2001) from the exact ODE density;
the surrogate fit residual on the held-out half is the irreducible
floor, the bridge increments shrink with more steps. z_AIS suppressed
when effective count < 4. The certificate's exact value here is
2 L^2 log 2pi + log Z_haar(beta_f, L) -- no coarse term (the coarse
level integrates out of the AIS estimator exactly).

- L=64 burn-in scan: `out\u1_2d\diffusion_vs_instanton\L64\burnin_scan\report.md`