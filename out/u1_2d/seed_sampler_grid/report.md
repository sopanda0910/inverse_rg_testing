# Seed x sampler grid

{plain HMC, instanton HMC} x {diffusion seed, cold, hot}. Within a sampler block only the starting configuration varies; **read by row, never diagonally**. Comparing the diffusion seed under plain HMC against a cold start under instanton HMC changes the seed and the algorithm at once and isolates neither.

## $L = 32$, $\beta$ = 14.1464

Seed ensemble `A_bc4_raw_wilson_L32_beta14.1464.pt`. Exact $\langle Q^2\rangle$ = 1.9040.

| sampler | seed | $t_{\rm therm}$ | acceptance | $\langle Q^2\rangle$ start | end | $Q$ changes |
|---|---|---|---|---|---|---|
| plain | **diffusion** | 1 | 0.984 | 1.719 | 1.719 | 0 |
| plain | cold | 262 | 0.986 | 0.000 | 0.000 | 0 |
| plain | hot | > 400 | 0.984 | 79.000 | 12.312 | 225 |
| instanton | **diffusion** | 6 | 0.987 | 1.719 | 1.438 | 18254 |
| instanton | cold | 244 | 0.987 | 0.000 | 2.031 | 18164 |
| instanton | hot | > 400 | 0.985 | 97.234 | 1.219 | 18238 |

The `Q changes` column is the point of the instanton block: under plain HMC at these couplings the charge never moves, so that row cannot certify a seed's $P(Q)$ -- it can only report where the seed started. Under instanton HMC the charge is free, so a seed whose $\langle Q^2\rangle$ holds steady had the distribution right, and one that drifts did not.

## $L = 64$, $\beta$ = 14.1464

Seed ensemble `C_L64_raw_wilson_L64_beta14.1464.pt`. Exact $\langle Q^2\rangle$ = 7.6160.

| sampler | seed | $t_{\rm therm}$ | acceptance | $\langle Q^2\rangle$ start | end | $Q$ changes |
|---|---|---|---|---|---|---|
| plain | **diffusion** | 11 | 0.971 | 8.656 | 8.656 | 0 |
| plain | cold | > 400 | 0.972 | 0.000 | 0.000 | 0 |
| plain | hot | > 400 | 0.968 | 416.344 | 40.750 | 296 |
| instanton | **diffusion** | 8 | 0.970 | 8.656 | 6.234 | 21759 |
| instanton | cold | > 400 | 0.973 | 0.000 | 5.828 | 21953 |
| instanton | hot | > 400 | 0.972 | 315.594 | 8.078 | 21878 |

The `Q changes` column is the point of the instanton block: under plain HMC at these couplings the charge never moves, so that row cannot certify a seed's $P(Q)$ -- it can only report where the seed started. Under instanton HMC the charge is free, so a seed whose $\langle Q^2\rangle$ holds steady had the distribution right, and one that drifts did not.

Source: `u1_2d/scripts/58_seed_sampler_grid.py`.
