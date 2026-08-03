# Instanton-HMC burn-in scan (entry cost vs quality)

Same instanton-HMC arm as the head-to-head; only the burn-in varies.
Quality pass = all Wilson-observable |z| <= 2.5 vs exact. The diffusion
pipeline's per-config cost at the same coupling is shown for contrast:
it has no burn-in and does not grow with beta.

| beta | burn-in traj | max Wilson |z| | Q^2 z | quality | burn-in s (entry cost) | diffusion s/config |
|---|---|---|---|---|---|---|
| 55.0237 | 500 | 10.0 | +0.4 | FAIL | 27.22 | 8.56 |
| 55.0237 | 1600 | 6.5 | +1.3 | FAIL | 111.5 | -- |
| 55.0237 | 6400 | 6.3 | +0.6 | FAIL | 472.0 | -- |
| 218.58 | 500 | 24.8 | -1.2 | FAIL | 52.53 | 9.53 |

Production window: 640 trajectories x 32 chains in every row; per-chain time-average statistics, first 25% discarded.