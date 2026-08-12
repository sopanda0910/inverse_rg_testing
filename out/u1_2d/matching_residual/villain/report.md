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
| villain | 16 | 14.1464 | 13.2 | 0.0257 | 0.023 | 2.0 | 0.627 | 9.33 | 0.0200 | -451.7 (0.9) |
| villain | 16 | 55.0237 | 18.7 | 0.0366 | 0.016 | 2.3 | 0.602 | 12.05 | 0.0266 | -468.5 (1.0) |
| villain | 32 | 55.0237 | 38.4 | 0.0187 | 0.106 | 12.5 | 0.644 | 25.94 | 0.0139 | -1947.2 (1.0) |

Standardized coefficients (nats of log-weight std absorbed per feature):

* villain 16:14.1464 coarse: {"sum_cos_P": 0.38, "sum_cos_2P": 0.31, "sum_cos_3P": 0.69, "sum_cos_rect": -0.15, "Q_c": 0.55, "Q_c^2": 0.36}
  fine surrogate: {"S_matched(blocked)": -2.77, "sum_cos_p": -11.99, "sum_cos_2p": -0.96, "sum_cos_3p": 7.99, "sum_cos_rect": -3.02, "sum_cos_2P_blocked": -0.68, "Q_float^2": -6.46}
* villain 16:55.0237 coarse: {"sum_cos_P": -0.44, "sum_cos_2P": -0.34, "sum_cos_3P": -0.16, "sum_cos_rect": -0.37, "Q_c": 0.28, "Q_c^2": -0.97}
  fine surrogate: {"S_matched(blocked)": 7.39, "sum_cos_p": -30.19, "sum_cos_2p": -11.55, "sum_cos_3p": 29.63, "sum_cos_rect": -0.52, "sum_cos_2P_blocked": -12.45, "Q_float^2": -3.66}
* villain 32:55.0237 coarse: {"sum_cos_P": 1.96, "sum_cos_2P": 2.25, "sum_cos_3P": 2.74, "sum_cos_rect": 2.37, "Q_c": -1.61, "Q_c^2": -2.4}
  fine surrogate: {"S_matched(blocked)": -13.53, "sum_cos_p": -67.5, "sum_cos_2p": -6.55, "sum_cos_3p": 48.57, "sum_cos_rect": -0.64, "sum_cos_2P_blocked": 1.83, "Q_float^2": -4.52}