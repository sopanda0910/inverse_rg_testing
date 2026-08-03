# Matching residual vs model error

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