# Non-learned prolongators, and t_therm against them

$L = 32$, $\beta = 105.651$, 64 chains, 400 trajectories per arm.

Every arm receives IDENTICAL post-processing -- coarse-charge enforcement on $\psi$, 30 conditional SU(2) sweeps, 0 rethermalization sweeps -- so what differs is the lift and only the lift. The SU(2) sampler is exact at frozen $\psi$, which is what makes this ablation clean: the only learned object in the pipeline is the map from coarse $\psi$ to fine $\psi$, and it is the only thing being swapped.

$t_{\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: the first trajectory at which the across-chain $|z|$ against the EXACT value is $\le 2$ for five consecutive trajectories. An arm that never gets there is written `> 400`, against its own budget, never "never".

| arm | $t$ plaquette | $t$ W2x2 | $t$ W4x4 | $t$ W8x8 | slowest | rel err **pre**-retherm | $|\Delta P/P|$ at $t=0$ | build s |
|---|---|---|---|---|---|---|---|---|
| smear (20 sweeps) | 0 | 0 | 0 | 0 | 0 | -9.47e-02 | 6.91e-06 | 8 |
| **diffusion** | **3** | **0** | **0** | **0** | **3** | +1.02e-04 | 3.27e-05 | 0 |
| diffusion_raw | 0 | 0 | 0 | 0 | 0 | +7.97e-05 | 7.96e-05 | 36 |

## What to read off it


`smear` is the arm that matters: `flux` plus heatbath + overrelaxation sweeps, the count chosen per coupling to match the exact plaquette rather than fixed. Its build cost is charged in the last column.

Source: `u2_2d/scripts/17_prolongator_baseline.py`.
