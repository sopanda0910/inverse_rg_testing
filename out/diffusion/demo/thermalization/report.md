# Diffusion-seeded HMC: thermalization time vs the standard-HMC sampling interval

Action: wilson. All HMC in this report is plain HMC (Omelyan, adapted step size, **no** topological updates).

**Claim.** A raw sample from the conditional-diffusion ladder, used as the starting configuration of an HMC chain, thermalizes within a few tens of trajectories at every coupling. The yardstick is the sampling interval `2 tau_int` -- the trajectories a standard HMC chain needs between two of its own independent configs, i.e. its *marginal* cost per config, charged forever. At the fine rungs the ladder is built for, the ordering is

> t_therm(diffusion seed)  <  2 tau_int(standard HMC)  <  burn-in(fresh chain)

with a margin that grows with beta as standard HMC slides into critical slowing down and topological freezing. At the cheapest rung the seed and the interval are comparable -- where standard HMC is still efficient there is nothing to win on Wilson-loop observables -- but even there the seed starts in the correct topological sector at t = 0, while the chain's topological interval `2 tau_int(Q)` is several times longer than its Wilson-loop one. The fresh-chain burn-in is standard HMC's one-time entry cost and exceeds the interval everywhere.

![timescales](timescales.png)

## The three starting points

- **Diffusion seed** -- the raw output of the conditional-diffusion ladder at this rung (ancestral sampling + the deterministic coarse-charge transport), with **no** rethermalization sweeps applied: every bit of equilibration the seed needs is measured here, in HMC trajectories.
- **Hot start** -- every link angle drawn uniformly from (-pi, pi]: a completely disordered (infinite-temperature) configuration. The standard way to initialize a fresh HMC chain without prior information.
- **Cold start** -- every link angle set to zero: the perfectly ordered (beta -> infinity) configuration, the other standard initialization.

## Summary

| rung | L | beta | t_therm diffusion seed | standard-HMC interval 2 tau_int | margin (interval - t_therm) | burn-in hot / cold | tau_int(Q) |
|---|---|---|---|---|---|---|---|
| rung0_L16_beta4 | 16 | 4 | 13 | 7.4 | -5.6 traj | 53 / 42 | 20.8 |
| rung1_L32_beta14.1464 | 32 | 14.1464 | 3 | 25.0 | 22.0 traj | never / 186 | frozen (0 tunnelings in 321 x 32 traj) |
| rung2_L64_beta55.0237 | 64 | 55.0237 | 11 | 92.0 | 81.0 traj | never / 625 | frozen (0 tunnelings in 321 x 16 traj) |

t_therm and burn-in are the slowest Wilson-loop observable (plaquette, W(2x2), W(4x4)); topology is stricter still for the fresh chains: their Q^2 **never** reaches the exact value at the two frozen rungs, while the diffusion seed inherits the correct topological sector from the coarse ensemble it was generated from (see the Q^2 panels and per-rung tables below).

Thermalization time `t_therm` = first trajectory at which the ensemble-mean z-score vs the exact value satisfies |z| <= 2 and stays there for 5 consecutive trajectories (t = 0: already thermalized before any HMC). For the diffusion seed, t_therm is computed on a random subsample of chains matched to the baseline chain count so all starts are compared at equal statistical power. `tau_int` is Madras-Sokal, measured on the second half of the hot-start chains, averaged over chains. In the per-rung relaxation figures, the blue dotted vertical line marks where the diffusion seed thermalizes and the black dotted vertical line marks the standard-HMC interval `2 tau_int` for that observable.

## What 'never' means, and where the ground truth comes from

'never' = the ensemble mean was still outside |z| <= 2 of the exact value after the full baseline budget; the per-rung sections quote the z-score it plateaued at. For hot starts at the two large-beta rungs this is not a budget problem but a physical one: a random start freezes into a random topological sector (<Q^2> of order tens), plain HMC can never change Q at these couplings (tunneling is suppressed ~exp(-2 beta)), and the wrong sector biases every Wilson loop by an amount that never decays. Cold starts sit in the single sector Q = 0, so their Wilson loops do eventually converge, but <Q^2> stays pinned at 0 forever.

None of the exact values in this report come from fine-lattice HMC: the ground truth is the character expansion of 2D compact U(1) (`diffusion/lgt/exact.py`), which gives every Wilson loop, P(Q) and chi_top in closed form at finite volume. The diffusion ladder itself is anchored at a cheap coarse rung (L=8, beta ~ 1.35) where HMC mixes well, and transports that ensemble to fine rungs -- which is precisely why it can start chains in regions standard HMC cannot reach.

## rung0_L16_beta4

HMC: step size 0.1000, 10 leapfrog steps, acceptance seed/hot/cold = 0.995/0.995/0.994. Diffusion-seed batch: 192 chains x 96 trajectories (0.07 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](rung0_L16_beta4_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 3.69 +- 0.26, wilson_2x2 = 2.44 +- 0.14, wilson_4x4 = 1.19 +- 0.09. Topology: hot-start HMC L=16 beta=4 -> tau_int(Q) = 20.8.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.8609 | 0.001231 | 0.8635 | -2.127 | 0.8643 | 0.000538 | -2.538 | 0.003675 |  |
| wilson_1x1 | 0.8609 | 0.001231 | 0.8635 | -2.127 | 0.8643 | 0.000538 | -2.538 | 0.003675 |  |
| wilson_1x2 | 0.7411 | 0.002008 | 0.7457 | -2.269 | 0.7475 | 0.001245 | -2.703 | 0.005557 |  |
| wilson_2x2 | 0.5564 | 0.003442 | 0.556 | 0.1045 | 0.5584 | 0.002318 | -0.4922 | 0.02997 |  |
| wilson_2x3 | 0.4157 | 0.004229 | 0.4146 | 0.2539 | 0.414 | 0.003147 | 0.3111 | 0.2336 |  |
| wilson_3x3 | 0.2724 | 0.005757 | 0.267 | 0.9513 | 0.2671 | 0.004546 | 0.7303 | 0.05784 |  |
| wilson_3x4 | 0.1789 | 0.006909 | 0.1719 | 1.018 | 0.1675 | 0.004284 | 1.409 | 0.07866 |  |
| wilson_4x4 | 0.1024 | 0.006694 | 0.09558 | 1.014 | 0.09008 | 0.004552 | 1.519 | 0.1215 |  |
| wilson_4x5 | 0.06523 | 0.006235 | 0.05315 | 1.937 | 0.04848 | 0.004107 | 2.243 | 0.06757 |  |
| wilson_5x5 | 0.03899 | 0.005911 | 0.02552 | 2.279 | 0.01909 | 0.003582 | 2.879 | 0.05784 |  |
| wilson_5x6 | 0.02105 | 0.005348 | 0.01225 | 1.645 | 0.009674 | 0.002905 | 1.869 | 0.2064 |  |
| wilson_6x6 | 0.009032 | 0.005088 | 0.00508 | 0.7769 | 0.006118 | 0.003684 | 0.4639 | 0.9775 |  |
| wilson_6x7 | 0.003882 | 0.003558 | 0.002106 | 0.499 | 0.0001118 | 0.002541 | 0.8622 | 0.3308 |  |
| wilson_7x7 | 0.001169 | 0.004313 | 0.0007541 | 0.09614 | 0.0006575 | 0.002865 | 0.09874 | 0.9775 |  |
| wilson_7x8 | -0.002593 | 0.005092 | 0.00027 | -0.5621 | -0.005573 | 0.002671 | 0.5184 | 0.409 |  |
| wilson_8x8 | 0.003927 | 0.004533 | 8.347e-05 | 0.8478 | -0.003129 | 0.002933 | 1.307 | 0.1215 |  |
| creutz_2 | 0.1369 | 0.003848 | 0.1467 | -2.564 |  |  |  |  |  |
| creutz_3 | 0.131 | 0.01104 | 0.1467 | -1.429 |  |  |  |  |  |
| creutz_4 | 0.138 | 0.03001 | 0.1467 | -0.2922 |  |  |  |  |  |
| creutz_5 | 0.0638 | 0.08193 | 0.1467 | -1.012 |  |  |  |  |  |
| creutz_6 | 0.2295 | 0.3714 | 0.1467 | 0.2229 |  |  |  |  |  |
| creutz_7 | 0.3559 | 3.18 | 0.1467 | 0.06577 |  |  |  |  |  |
| Q | -0.07292 | 0.1 | 0 | -0.7289 | -0.1276 | 0.09796 | 0.3906 | 0.9996 |  |
| Q^2 | 1.771 | 0.2274 | 1.934 | -0.7169 | 1.992 | 0.2405 | -0.6688 | 0.9887 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.006897 | 0.0008879 | 0.007554 | -0.7407 | 0.007718 | 0.0008656 | -0.6628 | 3.027e-12 |  |
| Q histogram vs exact P(Q) | 5.423 | nan | 6 | nan |  |  |  |  | 0.4908 |

![generated](rung0_L16_beta4_generated.png)

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.8623 | 0.0007591 | 0.8635 | -1.619 | 0.8643 | 0.000538 | -2.172 | 0.3686 |  |
| wilson_1x1 | 0.8623 | 0.0007591 | 0.8635 | -1.619 | 0.8643 | 0.000538 | -2.172 | 0.3686 |  |
| wilson_1x2 | 0.7429 | 0.001633 | 0.7457 | -1.719 | 0.7475 | 0.001245 | -2.258 | 0.05784 |  |
| wilson_2x2 | 0.5548 | 0.003348 | 0.556 | -0.3729 | 0.5584 | 0.002318 | -0.8964 | 0.7411 |  |
| wilson_2x3 | 0.4154 | 0.004567 | 0.4146 | 0.1806 | 0.414 | 0.003147 | 0.2508 | 0.6425 |  |
| wilson_3x3 | 0.2657 | 0.005218 | 0.267 | -0.2372 | 0.2671 | 0.004546 | -0.1961 | 0.8729 |  |
| wilson_3x4 | 0.1731 | 0.006934 | 0.1719 | 0.1693 | 0.1675 | 0.004284 | 0.6871 | 0.6425 |  |
| wilson_4x4 | 0.09494 | 0.007327 | 0.09558 | -0.08735 | 0.09008 | 0.004552 | 0.5636 | 0.4972 |  |
| wilson_4x5 | 0.05153 | 0.007069 | 0.05315 | -0.228 | 0.04848 | 0.004107 | 0.3737 | 0.6922 |  |
| wilson_5x5 | 0.02428 | 0.006314 | 0.02552 | -0.1957 | 0.01909 | 0.003582 | 0.7153 | 0.2336 |  |
| wilson_5x6 | 0.01009 | 0.005636 | 0.01225 | -0.3835 | 0.009674 | 0.002905 | 0.06566 | 0.9607 |  |
| wilson_6x6 | 0.004046 | 0.004549 | 0.00508 | -0.2272 | 0.006118 | 0.003684 | -0.354 | 0.7411 |  |
| wilson_6x7 | 0.001212 | 0.004211 | 0.002106 | -0.2123 | 0.0001118 | 0.002541 | 0.2237 | 0.5444 |  |
| wilson_7x7 | 0.00241 | 0.004251 | 0.0007541 | 0.3896 | 0.0006575 | 0.002865 | 0.3419 | 0.9376 |  |
| wilson_7x8 | -0.002582 | 0.003675 | 0.00027 | -0.7761 | -0.005573 | 0.002671 | 0.6586 | 0.5444 |  |
| wilson_8x8 | -0.005304 | 0.003236 | 8.347e-05 | -1.665 | -0.003129 | 0.002933 | -0.4981 | 0.9951 |  |
| creutz_2 | 0.1429 | 0.003524 | 0.1467 | -1.098 |  |  |  |  |  |
| creutz_3 | 0.1576 | 0.0101 | 0.1467 | 1.076 |  |  |  |  |  |
| creutz_4 | 0.1717 | 0.03022 | 0.1467 | 0.8266 |  |  |  |  |  |
| creutz_5 | 0.1415 | 0.1272 | 0.1467 | -0.04118 |  |  |  |  |  |
| creutz_6 | 0.03565 | 0.7607 | 0.1467 | -0.146 |  |  |  |  |  |
| creutz_7 | -1.893 | 8.41 | 0.1467 | -0.2425 |  |  |  |  |  |
| Q | 0.1302 | 0.1198 | 0 | 1.087 | -0.1276 | 0.09796 | 1.666 | 0.06757 |  |
| Q^2 | 2.172 | 0.1919 | 1.934 | 1.24 | 1.992 | 0.2405 | 0.584 | 0.5444 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.008418 | 0.0007541 | 0.007554 | 1.145 | 0.007718 | 0.0008656 | 0.6091 | 1.137e-11 |  |
| Q histogram vs exact P(Q) | 1.926 | nan | 6 | nan |  |  |  |  | 0.9264 |

![after_hmc](rung0_L16_beta4_after_hmc.png)

## rung1_L32_beta14.1464

HMC: step size 0.0532, 19 leapfrog steps, acceptance seed/hot/cold = 0.996/0.994/0.996. Diffusion-seed batch: 192 chains x 96 trajectories (0.17 s/traj for the whole batch); baselines: 32 chains x 640 trajectories.

![relaxation](rung1_L32_beta14.1464_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 7.13 +- 1.01, wilson_2x2 = 12.49 +- 1.75, wilson_4x4 = 7.83 +- 1.33. Topology: hot-start HMC L=32 beta=14.1464 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at plaquette at |z| ~ 2, wilson_2x2 at |z| ~ 4, wilson_4x4 at |z| ~ 4, Q^2 at |z| ~ 5; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 1903997747200.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9648 | 0.0001028 | 0.964 | 7.951 | 0.9614 | 0.0001402 | 19.47 | 0 |  |
| wilson_1x1 | 0.9648 | 0.0001028 | 0.964 | 7.951 | 0.9614 | 0.0001402 | 19.47 | 0 |  |
| wilson_1x2 | 0.9302 | 0.0001989 | 0.9293 | 4.846 | 0.9213 | 0.000405 | 19.78 | 0 |  |
| wilson_2x2 | 0.8641 | 0.0004334 | 0.8635 | 1.273 | 0.841 | 0.0009662 | 21.83 | 0 |  |
| wilson_2x3 | 0.8026 | 0.0007438 | 0.8024 | 0.208 | 0.7659 | 0.001538 | 21.46 | 0 |  |
| wilson_3x3 | 0.7178 | 0.001018 | 0.7188 | -0.9717 | 0.664 | 0.002141 | 22.72 | 0 |  |
| wilson_3x4 | 0.643 | 0.001676 | 0.6439 | -0.5338 | 0.575 | 0.002713 | 21.32 | 0 |  |
| wilson_4x4 | 0.5564 | 0.002353 | 0.556 | 0.1504 | 0.4744 | 0.00314 | 20.89 | 0 |  |
| wilson_4x5 | 0.4818 | 0.00302 | 0.4801 | 0.5472 | 0.3947 | 0.003102 | 20.11 | 6.237e-39 |  |
| wilson_5x5 | 0.4031 | 0.003694 | 0.3997 | 0.9216 | 0.3174 | 0.003199 | 17.53 | 1.244e-35 |  |
| wilson_5x6 | 0.3376 | 0.004356 | 0.3327 | 1.121 | 0.2589 | 0.002877 | 15.08 | 1.157e-21 |  |
| wilson_6x6 | 0.2697 | 0.004975 | 0.267 | 0.5494 | 0.2058 | 0.002737 | 11.25 | 6.522e-15 |  |
| wilson_6x7 | 0.2186 | 0.004785 | 0.2142 | 0.9062 | 0.1623 | 0.002752 | 10.19 | 2.177e-10 |  |
| wilson_7x7 | 0.1682 | 0.004956 | 0.1657 | 0.5069 | 0.1204 | 0.003196 | 8.111 | 5.058e-09 |  |
| wilson_7x8 | 0.1316 | 0.004855 | 0.1282 | 0.6996 | 0.08863 | 0.003453 | 7.209 | 1.825e-06 |  |
| wilson_8x8 | 0.09821 | 0.004455 | 0.09558 | 0.5903 | 0.05757 | 0.003438 | 7.223 | 4.569e-08 |  |
| wilson_8x10 | 0.05837 | 0.004845 | 0.05315 | 1.078 | 0.02434 | 0.003404 | 5.746 | 5.028e-07 |  |
| wilson_10x10 | 0.02695 | 0.004632 | 0.02552 | 0.3092 | 0.005284 | 0.002791 | 4.007 | 0.001228 |  |
| wilson_10x12 | 0.01153 | 0.004894 | 0.01225 | -0.1469 | 0.0006368 | 0.003192 | 1.865 | 0.05784 |  |
| wilson_12x12 | 0.000342 | 0.004843 | 0.00508 | -0.9783 | -0.001509 | 0.002667 | 0.3348 | 0.8326 |  |
| creutz_2 | 0.03727 | 0.0004352 | 0.03668 | 1.351 |  |  |  |  |  |
| creutz_3 | 0.03781 | 0.0009033 | 0.03668 | 1.244 |  |  |  |  |  |
| creutz_4 | 0.03464 | 0.00163 | 0.03668 | -1.252 |  |  |  |  |  |
| creutz_5 | 0.03444 | 0.002648 | 0.03668 | -0.8491 |  |  |  |  |  |
| creutz_6 | 0.04716 | 0.004507 | 0.03668 | 2.324 |  |  |  |  |  |
| creutz_7 | 0.05153 | 0.008283 | 0.03668 | 1.792 |  |  |  |  |  |
| creutz_8 | 0.0468 | 0.01513 | 0.03668 | 0.6687 |  |  |  |  |  |
| Q | -0.03646 | 0.09547 | 0 | -0.3819 | 0.0625 | 0.05149 | -0.9123 | 0.0006097 |  |
| Q^2 | 1.776 | 0.1569 | 1.904 | -0.8157 | 6.438 | 0.1463 | -21.73 | 7.485e-14 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.001733 | 0.0001529 | 0.001859 | -0.826 | 0.006283 | 0.0001452 | -21.58 | 2.44e-19 |  |
| Q histogram vs exact P(Q) | 6.621 | nan | 6 | nan |  |  |  |  | 0.3574 |

![generated](rung1_L32_beta14.1464_generated.png)

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9641 | 0.0001268 | 0.964 | 0.6712 | 0.9614 | 0.0001402 | 14.03 | 5.045e-44 |  |
| wilson_1x1 | 0.9641 | 0.0001268 | 0.964 | 0.6712 | 0.9614 | 0.0001402 | 14.03 | 5.045e-44 |  |
| wilson_1x2 | 0.9292 | 0.0002029 | 0.9293 | -0.2952 | 0.9213 | 0.000405 | 17.45 | 0 |  |
| wilson_2x2 | 0.8633 | 0.0004192 | 0.8635 | -0.5981 | 0.841 | 0.0009662 | 21.19 | 0 |  |
| wilson_2x3 | 0.8019 | 0.0006004 | 0.8024 | -0.8374 | 0.7659 | 0.001538 | 21.81 | 0 |  |
| wilson_3x3 | 0.7175 | 0.00122 | 0.7188 | -1.059 | 0.664 | 0.002141 | 21.74 | 0 |  |
| wilson_3x4 | 0.6413 | 0.001687 | 0.6439 | -1.524 | 0.575 | 0.002713 | 20.75 | 0 |  |
| wilson_4x4 | 0.5522 | 0.002091 | 0.556 | -1.836 | 0.4744 | 0.00314 | 20.62 | 0 |  |
| wilson_4x5 | 0.4751 | 0.002503 | 0.4801 | -2.023 | 0.3947 | 0.003102 | 20.15 | 5.456e-36 |  |
| wilson_5x5 | 0.3937 | 0.003042 | 0.3997 | -1.963 | 0.3174 | 0.003199 | 17.28 | 6.378e-29 |  |
| wilson_5x6 | 0.3247 | 0.003346 | 0.3327 | -2.376 | 0.2589 | 0.002877 | 14.93 | 7.65e-19 |  |
| wilson_6x6 | 0.2589 | 0.003492 | 0.267 | -2.305 | 0.2058 | 0.002737 | 11.97 | 7.342e-12 |  |
| wilson_6x7 | 0.2055 | 0.003528 | 0.2142 | -2.465 | 0.1623 | 0.002752 | 9.656 | 6.508e-08 |  |
| wilson_7x7 | 0.1577 | 0.003731 | 0.1657 | -2.134 | 0.1204 | 0.003196 | 7.605 | 6.246e-06 |  |
| wilson_7x8 | 0.1214 | 0.003801 | 0.1282 | -1.772 | 0.08863 | 0.003453 | 6.39 | 0.0001766 |  |
| wilson_8x8 | 0.08966 | 0.003846 | 0.09558 | -1.541 | 0.05757 | 0.003438 | 6.22 | 1.513e-05 |  |
| wilson_8x10 | 0.04808 | 0.003534 | 0.05315 | -1.433 | 0.02434 | 0.003404 | 4.839 | 3.545e-05 |  |
| wilson_10x10 | 0.02071 | 0.003825 | 0.02552 | -1.256 | 0.005284 | 0.002791 | 3.259 | 0.008284 |  |
| wilson_10x12 | 0.008546 | 0.004833 | 0.01225 | -0.7668 | 0.0006368 | 0.003192 | 1.366 | 0.2957 |  |
| wilson_12x12 | -0.0002278 | 0.004755 | 0.00508 | -1.116 | -0.001509 | 0.002667 | 0.235 | 0.3308 |  |
| creutz_2 | 0.03676 | 0.0004 | 0.03668 | 0.183 |  |  |  |  |  |
| creutz_3 | 0.03752 | 0.0008205 | 0.03668 | 1.018 |  |  |  |  |  |
| creutz_4 | 0.03741 | 0.001541 | 0.03668 | 0.4716 |  |  |  |  |  |
| creutz_5 | 0.03747 | 0.002504 | 0.03668 | 0.3157 |  |  |  |  |  |
| creutz_6 | 0.03398 | 0.004833 | 0.03668 | -0.559 |  |  |  |  |  |
| creutz_7 | 0.03365 | 0.008321 | 0.03668 | -0.3648 |  |  |  |  |  |
| creutz_8 | 0.04196 | 0.01636 | 0.03668 | 0.3227 |  |  |  |  |  |
| Q | -0.03646 | 0.09547 | 0 | -0.3819 | 0.0625 | 0.05149 | -0.9123 | 0.0006097 |  |
| Q^2 | 1.776 | 0.1569 | 1.904 | -0.8157 | 6.438 | 0.1463 | -21.73 | 7.485e-14 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.001733 | 0.0001529 | 0.001859 | -0.826 | 0.006283 | 0.0001452 | -21.58 | 2.44e-19 |  |
| Q histogram vs exact P(Q) | 6.621 | nan | 6 | nan |  |  |  |  | 0.3574 |

![after_hmc](rung1_L32_beta14.1464_after_hmc.png)

## rung2_L64_beta55.0237

HMC: step size 0.0270, 37 leapfrog steps, acceptance seed/hot/cold = 0.992/0.992/0.991. Diffusion-seed batch: 192 chains x 96 trajectories (1.09 s/traj for the whole batch); baselines: 16 chains x 640 trajectories.

![relaxation](rung2_L64_beta55.0237_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 39.79 +- 2.01, wilson_2x2 = 46.02 +- 1.31, wilson_4x4 = 39.85 +- 2.19. Topology: hot-start HMC L=64 beta=55.0237 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at plaquette at |z| ~ 17, wilson_2x2 at |z| ~ 16, wilson_4x4 at |z| ~ 10, Q^2 at |z| ~ 3; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 1903086010368.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9915 | 1.932e-05 | 0.9909 | 34.88 | 0.9881 | 5.383e-05 | 61.07 | 0 |  |
| wilson_1x1 | 0.9915 | 1.932e-05 | 0.9909 | 34.88 | 0.9881 | 5.383e-05 | 61.07 | 0 |  |
| wilson_1x2 | 0.9827 | 4.447e-05 | 0.9818 | 19.46 | 0.9737 | 0.0001559 | 55.65 | 0 |  |
| wilson_2x2 | 0.965 | 8.771e-05 | 0.964 | 11.46 | 0.9402 | 0.0004374 | 55.52 | 0 |  |
| wilson_2x3 | 0.9474 | 0.0001405 | 0.9465 | 6.66 | 0.907 | 0.0007573 | 52.48 | 0 |  |
| wilson_3x3 | 0.9211 | 0.0002265 | 0.9208 | 1.439 | 0.8566 | 0.001242 | 51.07 | 0 |  |
| wilson_3x4 | 0.8959 | 0.0003286 | 0.8958 | 0.2723 | 0.8116 | 0.001736 | 47.7 | 0 |  |
| wilson_4x4 | 0.8636 | 0.000431 | 0.8635 | 0.285 | 0.755 | 0.002344 | 45.59 | 0 |  |
| wilson_4x5 | 0.8317 | 0.0005856 | 0.8324 | -1.293 | 0.7054 | 0.002918 | 42.43 | 0 |  |
| wilson_5x5 | 0.7932 | 0.0008189 | 0.7951 | -2.285 | 0.6482 | 0.003544 | 39.87 | 0 |  |
| wilson_5x6 | 0.7568 | 0.001065 | 0.7595 | -2.531 | 0.5984 | 0.004034 | 37.95 | 0 |  |
| wilson_6x6 | 0.715 | 0.001406 | 0.7188 | -2.735 | 0.5439 | 0.004484 | 36.4 | 0 |  |
| wilson_6x7 | 0.6743 | 0.001739 | 0.6803 | -3.459 | 0.4916 | 0.004916 | 35.04 | 0 |  |
| wilson_7x7 | 0.6296 | 0.00228 | 0.638 | -3.694 | 0.4363 | 0.00512 | 34.49 | 0 |  |
| wilson_7x8 | 0.5882 | 0.002688 | 0.5984 | -3.776 | 0.3852 | 0.00524 | 34.46 | 0 |  |
| wilson_8x8 | 0.5455 | 0.00314 | 0.556 | -3.365 | 0.3343 | 0.005149 | 35 | 0 |  |
| wilson_8x10 | 0.4645 | 0.004049 | 0.4801 | -3.872 | 0.2402 | 0.004598 | 36.61 | 0 |  |
| wilson_10x10 | 0.3801 | 0.004918 | 0.3997 | -3.974 | 0.1587 | 0.003938 | 35.14 | 0 |  |
| wilson_10x12 | 0.3085 | 0.005554 | 0.3327 | -4.364 | 0.1196 | 0.003512 | 28.75 | 0 |  |
| wilson_12x12 | 0.2423 | 0.006219 | 0.267 | -3.959 | 0.0885 | 0.003271 | 21.89 | 0 |  |
| creutz_2 | 0.009212 | 4.944e-05 | 0.009171 | 0.8202 |  |  |  |  |  |
| creutz_3 | 0.009751 | 0.0001198 | 0.009171 | 4.844 |  |  |  |  |  |
| creutz_4 | 0.008875 | 0.000196 | 0.009171 | -1.512 |  |  |  |  |  |
| creutz_5 | 0.009565 | 0.0003005 | 0.009171 | 1.312 |  |  |  |  |  |
| creutz_6 | 0.009778 | 0.0004256 | 0.009171 | 1.425 |  |  |  |  |  |
| creutz_7 | 0.01005 | 0.0006263 | 0.009171 | 1.41 |  |  |  |  |  |
| creutz_8 | 0.007431 | 0.0007661 | 0.009171 | -2.272 |  |  |  |  |  |
| Q | 0 | 0.07825 | 0 | 0 | -0.5 | 0.1088 | 3.732 | 2.854e-14 |  |
| Q^2 | 1.969 | 0.1536 | 1.903 | 0.4275 | 27.25 | 1.042 | -24.01 | 7.006e-45 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.0004807 | 3.75e-05 | 0.0004646 | 0.4275 | 0.006592 | 0.0002345 | -25.74 | 0 |  |
| Q histogram vs exact P(Q) | 8.105 | nan | 6 | nan |  |  |  |  | 0.2305 |

![generated](rung2_L64_beta55.0237_generated.png)

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9909 | 1.662e-05 | 0.9909 | 3.406 | 0.9881 | 5.383e-05 | 51.04 | 0 |  |
| wilson_1x1 | 0.9909 | 1.662e-05 | 0.9909 | 3.406 | 0.9881 | 5.383e-05 | 51.04 | 0 |  |
| wilson_1x2 | 0.9819 | 4.298e-05 | 0.9818 | 2.07 | 0.9737 | 0.0001559 | 50.98 | 0 |  |
| wilson_2x2 | 0.9641 | 8.258e-05 | 0.964 | 1.479 | 0.9402 | 0.0004374 | 53.66 | 0 |  |
| wilson_2x3 | 0.9465 | 0.0001444 | 0.9465 | 0.5445 | 0.907 | 0.0007573 | 51.32 | 0 |  |
| wilson_3x3 | 0.9208 | 0.0002235 | 0.9208 | -0.0587 | 0.8566 | 0.001242 | 50.82 | 0 |  |
| wilson_3x4 | 0.8957 | 0.0003019 | 0.8958 | -0.3552 | 0.8116 | 0.001736 | 47.72 | 0 |  |
| wilson_4x4 | 0.8635 | 0.0004599 | 0.8635 | -0.06325 | 0.755 | 0.002344 | 45.42 | 0 |  |
| wilson_4x5 | 0.8325 | 0.0006512 | 0.8324 | 0.1385 | 0.7054 | 0.002918 | 42.52 | 0 |  |
| wilson_5x5 | 0.7951 | 0.0008836 | 0.7951 | -0.006289 | 0.6482 | 0.003544 | 40.21 | 0 |  |
| wilson_5x6 | 0.7594 | 0.001142 | 0.7595 | -0.06439 | 0.5984 | 0.004034 | 38.39 | 0 |  |
| wilson_6x6 | 0.7183 | 0.001334 | 0.7188 | -0.4091 | 0.5439 | 0.004484 | 37.26 | 0 |  |
| wilson_6x7 | 0.6796 | 0.001601 | 0.6803 | -0.4502 | 0.4916 | 0.004916 | 36.36 | 0 |  |
| wilson_7x7 | 0.6367 | 0.001747 | 0.638 | -0.7722 | 0.4363 | 0.00512 | 37.04 | 0 |  |
| wilson_7x8 | 0.5968 | 0.001888 | 0.5984 | -0.8191 | 0.3852 | 0.00524 | 37.99 | 0 |  |
| wilson_8x8 | 0.5534 | 0.002024 | 0.556 | -1.304 | 0.3343 | 0.005149 | 39.59 | 0 |  |
| wilson_8x10 | 0.4771 | 0.002373 | 0.4801 | -1.301 | 0.2402 | 0.004598 | 45.79 | 0 |  |
| wilson_10x10 | 0.395 | 0.002836 | 0.3997 | -1.636 | 0.1587 | 0.003938 | 48.69 | 0 |  |
| wilson_10x12 | 0.3267 | 0.003471 | 0.3327 | -1.738 | 0.1196 | 0.003512 | 41.94 | 0 |  |
| wilson_12x12 | 0.2594 | 0.004054 | 0.267 | -1.867 | 0.0885 | 0.003271 | 32.81 | 0 |  |
| creutz_2 | 0.009168 | 5.322e-05 | 0.009171 | -0.04969 |  |  |  |  |  |
| creutz_3 | 0.009225 | 0.0001116 | 0.009171 | 0.4811 |  |  |  |  |  |
| creutz_4 | 0.008979 | 0.0001857 | 0.009171 | -1.032 |  |  |  |  |  |
| creutz_5 | 0.009428 | 0.0002858 | 0.009171 | 0.9001 |  |  |  |  |  |
| creutz_6 | 0.009744 | 0.0004151 | 0.009171 | 1.38 |  |  |  |  |  |
| creutz_7 | 0.009927 | 0.0005044 | 0.009171 | 1.498 |  |  |  |  |  |
| creutz_8 | 0.01087 | 0.0006862 | 0.009171 | 2.478 |  |  |  |  |  |
| Q | 0 | 0.07825 | 0 | 0 | -0.5 | 0.1088 | 3.732 | 2.854e-14 |  |
| Q^2 | 1.969 | 0.1536 | 1.903 | 0.4275 | 27.25 | 1.042 | -24.01 | 7.006e-45 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.0004807 | 3.75e-05 | 0.0004646 | 0.4275 | 0.006592 | 0.0002345 | -25.74 | 0 |  |
| Q histogram vs exact P(Q) | 8.105 | nan | 6 | nan |  |  |  |  | 0.2305 |

![after_hmc](rung2_L64_beta55.0237_after_hmc.png)
