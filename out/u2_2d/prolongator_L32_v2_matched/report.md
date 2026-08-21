# Non-learned prolongators, and t_therm against them

$L = 32$, $\beta = 105.651$, 64 chains, 400 trajectories per arm.

Every arm receives IDENTICAL post-processing -- coarse-charge enforcement on $\psi$, 30 conditional SU(2) sweeps, 0 rethermalization sweeps -- so what differs is the lift and only the lift. The SU(2) sampler is exact at frozen $\psi$, which is what makes this ablation clean: the only learned object in the pipeline is the map from coarse $\psi$ to fine $\psi$, and it is the only thing being swapped.

$t_{\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: the first trajectory at which the across-chain $|z|$ against the EXACT value is $\le 2$ for five consecutive trajectories. An arm that never gets there is written `> 400`, against its own budget, never "never".

| arm | $t$ plaquette | $t$ W2x2 | $t$ W4x4 | $t$ W8x8 | slowest | rel err **pre**-retherm | $|\Delta P/P|$ at $t=0$ | build s |
|---|---|---|---|---|---|---|---|---|
| ape | 0 | 302 | 368 | 159 | 368 | -1.78e-04 | 1.78e-04 | 10 |
| smear (10 sweeps) | 3 | 5 | 0 | 0 | 5 | -9.48e-02 | 5.46e-06 | 15 |
| diffusion_raw | 5 | 0 | 5 | 0 | 5 | +8.63e-05 | 8.63e-05 | 31 |
| diffusion_tuned (30 sweeps) | 0 | 0 | 0 | 0 | 0 | +8.63e-05 | 3.90e-06 | 10 |

## What to read off it


`smear` is the arm that matters: `flux` plus heatbath + overrelaxation sweeps, the count chosen per coupling to match the exact plaquette rather than fixed. Its build cost is charged in the last column.

Source: `u2_2d/scripts/17_prolongator_baseline.py`.
