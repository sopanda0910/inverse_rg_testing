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