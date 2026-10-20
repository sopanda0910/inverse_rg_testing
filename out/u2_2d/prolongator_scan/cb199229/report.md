# Non-learned prolongators, and t_therm against them

$L = 32$, $\beta = 790.874$, 64 chains, 200 trajectories per arm.

Every arm receives IDENTICAL post-processing -- coarse-charge enforcement on $\psi$, 30 conditional SU(2) sweeps, 0 rethermalization sweeps -- so what differs is the lift and only the lift. The SU(2) sampler is exact at frozen $\psi$, which is what makes this ablation clean: the only learned object in the pipeline is the map from coarse $\psi$ to fine $\psi$, and it is the only thing being swapped.

$t_{\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: the first trajectory at which the across-chain $|z|$ against the EXACT value is $\le 2$ for five consecutive trajectories. An arm that never gets there is written `> 200`, against its own budget, never "never".

Cost is reported in LINK TOUCHES, `44_sweeps_vs_trajectories.py`'s convention: one retherm sweep touches every link 3 times and one trajectory touches it 50 times at this coupling. Without a common currency the sweep column and the $t_{\rm therm}$ column cannot be added, and an arm that saves sweeps while spending trajectories looks cheaper when it is not. The reverse-diffusion sampler is NOT expressible in link touches and is charged in `build s` instead.

`gap/SEM` is the plaquette's distance from exact in units of the across-chain standard error at the moment the arm was handed to HMC. Two arms within about one SEM of each other are not separated by this measurement however different their sweep counts look.

| arm | sweeps | $t$ plaquette | $t$ W2x2 | $t$ W4x4 | $t$ W8x8 | slowest | link touches | gap/SEM | rel err **pre**-retherm | $|\Delta P/P|$ at $t=0$ | build s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| smear | 10 | 0 | 0 | 0 | 5 | 5 | 280 | 0.8 | -9.87e-02 | 4.81e-06 | 5 |
| smear_fixed | 25 | 0 | 5 | 1 | 0 | 5 | 325 | 0.3 | -9.87e-02 | 2.00e-06 | 7 |
| cold_tuned | 2 | 0 | 0 | 1 | 5 | 5 | 256 | 0.9 | +6.47e-04 | 6.07e-06 | 3 |
| cold_fixed | 25 | 0 | 0 | 0 | 0 | 0 | 75 | 0.8 | +6.30e-04 | 5.41e-06 | 7 |
| cold | 0 | > 200 | > 200 | > 200 | 178 | > 200 | -- | -- | -- | 2.54e-03 | 0 |
| diffusion_raw | 0 | > 200 | > 200 | > 200 | > 200 | > 200 | -- | -- | -2.06e-03 | 2.06e-03 | 14 |
| diffusion_tuned | 3 | 0 | 0 | 0 | 0 | 0 | 9 | 1.1 | -2.06e-03 | 6.42e-06 | 2 |
| diffusion_fixed | 25 | 0 | 6 | 4 | 6 | 6 | 375 | 0.2 | -2.06e-03 | 9.85e-07 | 4 |

## What to read off it


`smear` is the arm that matters: `flux` plus heatbath + overrelaxation sweeps, the count chosen per coupling to match the exact plaquette rather than fixed. Its build cost is charged in the last column.

Source: `u2_2d/scripts/17_prolongator_baseline.py`.
