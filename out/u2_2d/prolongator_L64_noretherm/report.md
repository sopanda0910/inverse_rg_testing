# Non-learned prolongators, and t_therm against them

$L = 64$, $\beta = 416.524$, 64 chains, 400 trajectories per arm.

Every arm receives IDENTICAL post-processing -- coarse-charge enforcement on $\psi$, 30 conditional SU(2) sweeps, 0 rethermalization sweeps -- so what differs is the lift and only the lift. The SU(2) sampler is exact at frozen $\psi$, which is what makes this ablation clean: the only learned object in the pipeline is the map from coarse $\psi$ to fine $\psi$, and it is the only thing being swapped.

$t_{\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: the first trajectory at which the across-chain $|z|$ against the EXACT value is $\le 2$ for five consecutive trajectories. An arm that never gets there is written `> 400`, against its own budget, never "never".

| arm | $t$ plaquette | $t$ W2x2 | $t$ W4x4 | $t$ W8x8 | slowest | rel err **pre**-retherm | $|\Delta P/P|$ at $t=0$ | build s |
|---|---|---|---|---|---|---|---|---|
| tile | > 400 | > 400 | > 400 | > 400 | > 400 | -3.64e-03 | 3.64e-03 | 3 |
| halve | > 400 | > 400 | > 400 | > 400 | > 400 | -1.89e-01 | 1.89e-01 | 2 |
| flux | > 400 | > 400 | > 400 | > 400 | > 400 | -9.65e-02 | 9.65e-02 | 2 |
| smear (50 sweeps) | 0 | 0 | 0 | 0 | 0 | -9.65e-02 | 2.51e-06 | 21 |
| hot | > 400 | > 400 | > 400 | > 400 | > 400 | -- | 9.99e-01 | 0 |
| cold | > 400 | > 400 | > 400 | 345 | > 400 | -- | 4.83e-03 | 0 |
| **diffusion** | **0** | **0** | **0** | **0** | **0** | +6.47e-05 | 8.21e-06 | 0 |

## What to read off it

**Pre-rethermalization the learned lift is 56x closer to exact than the best geometric arm** (`tile`): 6.47e-05 against 3.64e-03.
After the identical post-processing every arm receives, that margin is gone: at $t = 0$ the diffusion arm is **3.3x WORSE than `smear`** (8.21e-06 against 2.51e-06). The exact conditional SU(2) sampler repairs a bad determinant sector, so **local observables do not discriminate the lift.** Argue the model on topology and extended loops, not on the plaquette.
For scale the cold start begins at 4.83e-03. It is the control that gives the plot dynamic range, not the comparison that supports the claim.
**tile, halve, flux are no better than a fresh cold start.** Prolonging by an obvious deterministic rule satisfies the coarse constraint while being wrong at short distances, and the chain then has to undo it -- so the advantage is specific to learning, not to having been handed the coarse configuration.

`smear` is the arm that matters: `flux` plus heatbath + overrelaxation sweeps, the count chosen per coupling to match the exact plaquette rather than fixed. Its build cost is charged in the last column.

Source: `u2_2d/scripts/17_prolongator_baseline.py`.
