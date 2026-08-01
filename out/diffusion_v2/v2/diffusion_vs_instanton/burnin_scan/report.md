# Instanton-HMC burn-in scan (entry cost vs quality)

Same instanton-HMC arm as the head-to-head; only the burn-in varies.
Quality pass = all Wilson-observable |z| <= 2.5 vs exact. The diffusion
pipeline's per-config cost at the same coupling is shown for contrast:
it has no burn-in and does not grow with beta.

| beta | burn-in traj | max Wilson |z| | Q^2 z | quality | burn-in s (entry cost) | diffusion s/config |
|---|---|---|---|---|---|---|
| 4.44 | 500 | 2.5 | +0.8 | pass | 8.39 | 2.28 |
| 14.1464 | 500 | 1.7 | -0.5 | pass | 15.79 | 2.39 |
| 55.0237 | 500 | 7.1 | -0.5 | FAIL | 30.63 | 2.37 |
| 55.0237 | 2000 | 3.3 | -1.6 | FAIL | 328.2 | -- |
| 55.0237 | 8000 | 1.1 | -2.5 | pass | 1676.7 | -- |
| 118.5 | 500 | 9.4 | +0.2 | FAIL | 42.2 | 2.76 |
| 218.58 | 500 | 16.6 | +1.6 | FAIL | 58.28 | 2.55 |
| 218.58 | 2000 | 7.8 | -0.2 | FAIL | 604.8 | -- |
| 218.58 | 8000 | 7.2 | +0.3 | FAIL | 2533.7 | -- |

Production window: 640 trajectories x 32 chains in every row; per-chain time-average statistics, first 25% discarded.