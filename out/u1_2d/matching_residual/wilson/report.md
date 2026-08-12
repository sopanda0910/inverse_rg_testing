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
| wilson | 16 | 14.1464 | 12.2 | 0.0238 | 0.045 | 2.6 | 0.683 | 8.05 | 0.0182 | -451.9 (1.0) |
| wilson | 16 | 55.0237 | 18.6 | 0.0364 | 0.105 | 6.0 | 0.584 | 12.69 | 0.0261 | -468.7 (0.9) |
| wilson | 32 | 55.0237 | 35.4 | 0.0173 | 0.085 | 10.3 | 0.548 | 27.27 | 0.0141 | -1963.5 (1.0) |

Standardized coefficients (nats of log-weight std absorbed per feature):

* wilson 16:14.1464 coarse: {"sum_cos_P": 1.0, "sum_cos_2P": -0.17, "sum_cos_3P": -0.76, "sum_cos_rect": 0.6, "Q_c": 0.47, "Q_c^2": 0.58}
  fine surrogate: {"S_matched(blocked)": -7.36, "sum_cos_p": -21.0, "sum_cos_2p": 16.84, "sum_cos_3p": 0.41, "sum_cos_rect": -3.7, "sum_cos_2P_blocked": 3.26, "Q_float^2": -6.49}
* wilson 16:55.0237 coarse: {"sum_cos_P": 0.25, "sum_cos_2P": 0.23, "sum_cos_3P": 0.2, "sum_cos_rect": 0.33, "Q_c": 2.28, "Q_c^2": -2.52}
  fine surrogate: {"S_matched(blocked)": -2.28, "sum_cos_p": -18.11, "sum_cos_2p": -3.17, "sum_cos_3p": 13.62, "sum_cos_rect": -5.62, "sum_cos_2P_blocked": -2.92, "Q_float^2": -4.15}
* wilson 32:55.0237 coarse: {"sum_cos_P": 2.36, "sum_cos_2P": 2.2, "sum_cos_3P": 1.9, "sum_cos_rect": 1.51, "Q_c": 1.43, "Q_c^2": -1.29}
  fine surrogate: {"S_matched(blocked)": -1.85, "sum_cos_p": -38.81, "sum_cos_2p": -11.03, "sum_cos_3p": 33.63, "sum_cos_rect": -3.14, "sum_cos_2P_blocked": -12.94, "Q_float^2": -3.31}