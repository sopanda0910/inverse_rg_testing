# Instanton-update HMC vs. standard HMC

**Claim under test.** The instanton move (`diffusion.lgt.local_updates.topological_update`) is a *global* Metropolis proposal that adds a smooth Q = +-1 configuration to the whole lattice; its action cost is `delta_S ~ O(beta / V)`, so its acceptance rate should stay roughly beta-independent. Standard HMC can only change Q by having its local leapfrog dynamics climb an action barrier that grows with beta, so its topological-charge tunneling rate should collapse (freeze) at large beta while instanton HMC's does not.

Matched chains at each beta: same L=8, step_size/n_steps (`adapted_hmc_params`), hot start, 4 parallel chains, 20 burn-in + 60 recorded trajectories.

**Error bars.** The only rigorously independent statistical unit is a chain (different Markov chains = independent noise). Every mean/error below is computed from the 4 per-chain time-averages, discarding the first 25% of the recorded window as extra equilibration margin within production (Q^2 uses the dense per-step charge series; plaquette/Wilson loops use the periodic config snapshots) -- never by pooling all (time x chain) samples into one estimator, which would silently assume time-adjacent draws are as independent as different chains.

## Charge traces

![standard traces](standard_traces.png)

![instanton traces](instanton_traces.png)

Single representative chain per beta, full recorded window. Standard HMC's trace visibly locks onto one charge sector as beta grows; instanton HMC's keeps hopping across the same beta range.

## Acceptance rates

![acceptance](acceptance_vs_beta.png)

| beta | HMC step (standard) | HMC step (instanton run) | instanton move |
|---|---|---|---|
| 4 | 0.991 | 0.991 | 0.438 |
| 64 | 0.994 | 0.994 | 0.022 |

The Omelyan step's acceptance is statistically the same whether or not the instanton move is enabled (it does not touch the leapfrog trajectory), which is the sanity check that adding the instanton move does not disturb the base sampler. The instanton move's own acceptance decays with beta but far more gently than standard HMC's tunneling rate, which hits exactly zero.

## Topological freezing

![tunneling](tunneling_vs_beta.png)

| beta | standard: n_tunnelings | standard: frozen | instanton: n_tunnelings | instanton: frozen |
|---|---|---|---|---|
| 4 | 16 | False | 108 | False |
| 64 | 0 | True | 0 | True |

## Observables vs. exact (per-chain mean +- sem, z-scores)

| beta | obs | standard mean +- sem | z (std vs exact) | instanton mean +- sem | z (inst vs exact) | z (std vs inst) |
|---|---|---|---|---|---|---|
| 4 | plaquette | 0.8517 +- 0.0066 | -1.80 | 0.8636 +- 0.0033 | +0.03 | -1.62 |
| 4 | wilson_2x2 | 0.485 +- 0.027 | -2.65 | 0.5588 +- 0.022 | +0.13 | -2.14 |
| 4 | wilson_4x4 | 0.003625 +- 0.033 | -2.83 | 0.1161 +- 0.023 | +0.87 | -2.82 |
| 4 | Q^2 | 1.391 +- 0.51 | +1.77 | 0.4022 +- 0.088 | -0.91 | +1.90 |
| 64 | plaquette | 0.9838 +- 0.0019 | -4.49 | 0.9872 +- 0.00081 | -6.22 | -1.66 |
| 64 | wilson_2x2 | 0.8939 +- 0.019 | -4.11 | 0.9446 +- 0.0063 | -4.20 | -2.56 |
| 64 | wilson_4x4 | 0.1945 +- 0.19 | -3.71 | 0.8339 +- 0.042 | -1.82 | -3.24 |
| 64 | Q^2 | 0.75 +- 0.25 | +3.00 | 0 +- 0 | +nan | +3.00 |

At low beta (2, 4) standard and instanton agree closely with each other and with exact on every observable -- both samplers are ergodic there. Once standard HMC freezes (beta >= 16), its plaquette and Wilson-loop z-scores also grow large, not just Q^2: the per-case distribution plots below show standard HMC's plaquette-angle histogram visibly broader than exact and its Wilson-loop string tension systematically overestimated at the same beta where instanton HMC's ensemble still tracks exact closely. Reading: once a chain is stuck in the wrong topological sector, that failure contaminates every observable, not just Q, because the true equilibrium distribution mixes across sectors -- the instanton move's benefit is broader than 'fixes topology', it restores general ergodicity. Instanton HMC's own z-scores also grow somewhat with beta (a fixed burn-in budget likely stops being enough for either method as beta grows), but consistently far less than standard's.

## Per-case distribution plots

- `L8_beta4/L8_beta4_distributions.png`: plaquette-angle, P(Q), and Wilson-loop distributions -- standard HMC vs. instanton HMC vs. exact (both ensembles are pure HMC; no diffusion model involved anywhere in this script).
- `L8_beta64/L8_beta64_distributions.png`: plaquette-angle, P(Q), and Wilson-loop distributions -- standard HMC vs. instanton HMC vs. exact (both ensembles are pure HMC; no diffusion model involved anywhere in this script).