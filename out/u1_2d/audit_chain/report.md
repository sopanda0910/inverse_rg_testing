# Audit chain report

## Matching residual -- Wilson

R^2_c = fiber log-weight variance explained by COARSE-only observables
(upper bound on the matching-residual floor: c-dependent model error
lands here too). R^2_x = variance of [log q + S_f] explained by the
differentiable fine-feature surrogate -- the floor of the AIS bridge
(script 28). For `villain`, coarse matching is exact, so its fiber
spread is pure model error; Wilson minus Villain at matched cases
isolates the matching floor.

| action | L | beta_f | log-w std | /site | R^2_c | c-explained std | R^2_x | surrogate resid std | resid /site | dF gap (sem) |
|--------|---|--------|-----------|-------|-------|-----------------|-------|---------------------|-------------|--------------|
| wilson | 16 | 14.1464 | 10.7 | 0.0209 | 0.062 | 2.7 | 0.564 | 8.10 | 0.0171 | -456.3 (0.7) |
| wilson | 16 | 55.0237 | 21.5 | 0.0419 | 0.005 | 1.5 | 0.739 | 11.24 | 0.0253 | -482.0 (0.9) |
| wilson | 32 | 55.0237 | 35.9 | 0.0175 | 0.023 | 5.4 | 0.594 | 24.49 | 0.0126 | -1951.0 (0.9) |

Standardized coefficients (nats of log-weight std absorbed per feature):

* wilson 16:14.1464 coarse: {"sum_cos_P": 0.03, "sum_cos_2P": 0.01, "sum_cos_3P": 0.08, "sum_cos_rect": 0.01, "Q_c": -1.06, "Q_c^2": -1.02}
  fine surrogate: {"S_matched(blocked)": -1.99, "sum_cos_p": -15.27, "sum_cos_2p": 0.9, "sum_cos_3p": 5.53, "sum_cos_rect": 1.9, "sum_cos_2P_blocked": -2.27, "Q_float^2": -2.14}
* wilson 16:55.0237 coarse: {"sum_cos_P": -0.36, "sum_cos_2P": -0.31, "sum_cos_3P": -0.21, "sum_cos_rect": 0.58, "Q_c": 0.33, "Q_c^2": 0.33}
  fine surrogate: {"S_matched(blocked)": 3.07, "sum_cos_p": -37.09, "sum_cos_2p": 1.51, "sum_cos_3p": 17.69, "sum_cos_rect": 2.48, "sum_cos_2P_blocked": -9.53, "Q_float^2": -2.56}
* wilson 32:55.0237 coarse: {"sum_cos_P": 0.6, "sum_cos_2P": 0.9, "sum_cos_3P": 1.37, "sum_cos_rect": -0.89, "Q_c": -1.89, "Q_c^2": 1.6}
  fine surrogate: {"S_matched(blocked)": -7.43, "sum_cos_p": -21.07, "sum_cos_2p": -8.75, "sum_cos_3p": 12.13, "sum_cos_rect": -8.36, "sum_cos_2P_blocked": -3.62, "Q_float^2": -10.83}

## Matching residual -- Villain control

R^2_c = fiber log-weight variance explained by COARSE-only observables
(upper bound on the matching-residual floor: c-dependent model error
lands here too). R^2_x = variance of [log q + S_f] explained by the
differentiable fine-feature surrogate -- the floor of the AIS bridge
(script 28). For `villain`, coarse matching is exact, so its fiber
spread is pure model error; Wilson minus Villain at matched cases
isolates the matching floor.

| action | L | beta_f | log-w std | /site | R^2_c | c-explained std | R^2_x | surrogate resid std | resid /site | dF gap (sem) |
|--------|---|--------|-----------|-------|-------|-----------------|-------|---------------------|-------------|--------------|
| villain | 16 | 14.1464 | 14.7 | 0.0287 | 0.174 | 6.1 | 0.627 | 9.77 | 0.0204 | -445.8 (1.0) |
| villain | 16 | 55.0237 | 23.5 | 0.0459 | 0.031 | 4.1 | 0.782 | 11.31 | 0.0267 | -480.5 (0.8) |
| villain | 32 | 55.0237 | 54.8 | 0.0268 | 0.048 | 12.0 | 0.851 | 22.56 | 0.0122 | -1944.8 (1.0) |

Standardized coefficients (nats of log-weight std absorbed per feature):

* villain 16:14.1464 coarse: {"sum_cos_P": -19.16, "sum_cos_2P": 13.39, "sum_cos_3P": -0.48, "sum_cos_rect": 9.39, "Q_c": -0.56, "Q_c^2": 0.67}
  fine surrogate: {"S_matched(blocked)": -1.84, "sum_cos_p": -39.64, "sum_cos_2p": 27.8, "sum_cos_3p": 0.2, "sum_cos_rect": 3.07, "sum_cos_2P_blocked": -2.58, "Q_float^2": -4.99}
* villain 16:55.0237 coarse: {"sum_cos_P": -11.62, "sum_cos_2P": -1.8, "sum_cos_3P": 10.41, "sum_cos_rect": 5.0, "Q_c": 1.12, "Q_c^2": 1.12}
  fine surrogate: {"S_matched(blocked)": -1.19, "sum_cos_p": -40.39, "sum_cos_2p": -2.79, "sum_cos_3p": 24.65, "sum_cos_rect": 1.5, "sum_cos_2P_blocked": -4.63, "Q_float^2": -1.72}
* villain 32:55.0237 coarse: {"sum_cos_P": 2.77, "sum_cos_2P": 2.9, "sum_cos_3P": 3.25, "sum_cos_rect": -0.23, "Q_c": -0.46, "Q_c^2": -1.26}
  fine surrogate: {"S_matched(blocked)": 20.58, "sum_cos_p": -100.42, "sum_cos_2p": 0.27, "sum_cos_3p": 67.34, "sum_cos_rect": -3.81, "sum_cos_2P_blocked": -35.93, "Q_float^2": -11.65}

## AIS-corrected transport

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

## Wilson minus Villain (matching floor by construction)

| L | beta_f | wilson std/site | villain std/site | difference |
|---|--------|-----------------|------------------|------------|
| 16 | 14.146 | 0.0209 | 0.0287 | -0.0079 |
| 16 | 55.024 | 0.0419 | 0.0459 | -0.0040 |
| 32 | 55.024 | 0.0175 | 0.0268 | -0.0092 |

- Validation report (tau_int-aware, raw pass): `out\u1_2d\validation\report.md`
- Campaign verdict (rerun): `out\u1_2d\verdict\verdict.md`
- L=64 head-to-head: `out\u1_2d\diffusion_vs_instanton\L64\report.md`