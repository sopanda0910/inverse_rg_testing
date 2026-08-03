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
| villain | 16 | 14.1464 | 15.3 | 0.0298 | 0.075 | 4.2 | 0.540 | 10.10 | 0.0223 | -617.8 (0.8) |
| villain | 16 | 55.0237 | 46.8 | 0.0914 | 0.003 | 2.7 | 0.947 | 10.82 | 0.0255 | -622.2 (1.0) |
| villain | 32 | 55.0237 | 83.1 | 0.0406 | 0.077 | 23.0 | 0.941 | 19.83 | 0.0109 | -2584.3 (1.0) |

Standardized coefficients (nats of log-weight std absorbed per feature):

* villain 16:14.1464 coarse: {"sum_cos_P": -0.93, "sum_cos_2P": -0.84, "sum_cos_3P": -0.46, "sum_cos_rect": -0.55, "Q_c": 0.2, "Q_c^2": 1.12}
  fine surrogate: {"S_matched(blocked)": -2.64, "sum_cos_p": -20.21, "sum_cos_2p": 6.83, "sum_cos_3p": 16.07, "sum_cos_rect": -9.2, "sum_cos_2P_blocked": 0.66, "Q_float^2": -1.86}
* villain 16:55.0237 coarse: {"sum_cos_P": 0.13, "sum_cos_2P": -0.3, "sum_cos_3P": -0.96, "sum_cos_rect": -0.28, "Q_c": -0.56, "Q_c^2": 0.56}
  fine surrogate: {"S_matched(blocked)": -0.92, "sum_cos_p": -37.56, "sum_cos_2p": 10.88, "sum_cos_3p": 40.03, "sum_cos_rect": -52.57, "sum_cos_2P_blocked": 0.35, "Q_float^2": -8.8}
* villain 32:55.0237 coarse: {"sum_cos_P": -2.69, "sum_cos_2P": -2.76, "sum_cos_3P": -2.94, "sum_cos_rect": -5.63, "Q_c": 6.78, "Q_c^2": 4.79}
  fine surrogate: {"S_matched(blocked)": -22.65, "sum_cos_p": -108.3, "sum_cos_2p": 34.62, "sum_cos_3p": 66.64, "sum_cos_rect": -64.41, "sum_cos_2P_blocked": 19.02, "Q_float^2": -9.51}