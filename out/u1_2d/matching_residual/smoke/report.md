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
| wilson | 8 | 2 | 14.9 | 0.1162 | 0.290 | 8.0 | 0.071 | 14.11 | 0.1228 | -101.6 (1.0) |

Standardized coefficients (nats of log-weight std absorbed per feature):

* wilson 8:2 coarse: {"sum_cos_P": -1.14, "sum_cos_2P": 0.72, "sum_cos_3P": -2.5, "sum_cos_rect": -0.97, "Q_c": -0.4, "Q_c^2": 2.72}
  fine surrogate: {"S_matched(blocked)": -0.04, "sum_cos_p": 0.14, "sum_cos_2p": 0.23, "sum_cos_3p": 1.01, "sum_cos_rect": -0.27, "sum_cos_2P_blocked": 1.83, "Q_float^2": -0.58}