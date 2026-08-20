# Non-learned prolongators, and t_therm against them

$L = 64$, $\beta = 416.524$, 64 chains, 400 trajectories per arm.

Every arm receives IDENTICAL post-processing -- coarse-charge enforcement on $\psi$, 30 conditional SU(2) sweeps, 10 rethermalization sweeps -- so what differs is the lift and only the lift. The SU(2) sampler is exact at frozen $\psi$, which is what makes this ablation clean: the only learned object in the pipeline is the map from coarse $\psi$ to fine $\psi$, and it is the only thing being swapped.

$t_{\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: the first trajectory at which the across-chain $|z|$ against the EXACT value is $\le 2$ for five consecutive trajectories. An arm that never gets there is written `> 400`, against its own budget, never "never".

| arm | $t$ plaquette | $t$ W2x2 | $t$ W4x4 | $t$ W8x8 | slowest | rel err **pre**-retherm | $|\Delta P/P|$ at $t=0$ | build s |
|---|---|---|---|---|---|---|---|---|
| tile | 0 | 0 | 2 | 2 | 2 | -3.64e-03 | 7.24e-06 | 8 |
| halve | 0 | 0 | 1 | 2 | 2 | -1.89e-01 | 1.12e-05 | 4 |
| flux | 0 | 0 | 0 | 0 | 0 | -9.65e-02 | 8.32e-06 | 4 |
| smear (5 sweeps) | 0 | 0 | 0 | 0 | 0 | -9.65e-02 | 1.14e-06 | 5 |
| hot | > 400 | > 400 | > 400 | > 400 | > 400 | -- | 1.00e+00 | 0 |
| cold | > 400 | > 400 | > 400 | > 400 | > 400 | -- | 4.83e-03 | 0 |
| **diffusion** | **0** | **0** | **0** | **0** | **0** | +6.47e-05 | 8.21e-06 | 0 |

## What to read off it

The diffusion arm starts at $|\Delta P/P| = 8.21e-06$ against the cold start's $4.83e-03$.
The geometric prolongators beat a fresh cold start here, so part of the seed's advantage is available without a model. Quote the margin over `flux`, not over `cold`.

`smear` is the arm that matters: `flux` plus heatbath + overrelaxation sweeps, the count chosen per coupling to match the exact plaquette rather than fixed. Its build cost is charged in the last column.

Source: `u2_2d/scripts/17_prolongator_baseline.py`.
