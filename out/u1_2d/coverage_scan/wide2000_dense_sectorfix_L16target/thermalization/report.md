# Diffusion-seeded HMC across the matched beta scan: thermalization time vs the standard-HMC sampling interval

Action: wilson. All HMC in this report is plain HMC (Omelyan, adapted step size, **no** topological updates).

**Why this scan.** At the ladder's upper rungs the fresh-HMC baselines never thermalize at all (topological freezing plus a metastable local-defect state), so the only comparison available there is 'diffusion seed vs a baseline that never arrives'. This report extends the benchmark to every matched coupling pair of the generalization study -- one inverse-RG step L=16 -> L=32 per case -- including fine couplings low enough that hot- and cold-start HMC *does* thermalize within the budget. There the standard chain's own interval `2 tau_int` and its fresh-start burn-in are honest, measurable yardsticks, and the scan shows where the ordering

> t_therm(diffusion seed)  <  2 tau_int(standard HMC)  <  burn-in(fresh chain)

sets in as beta grows and standard HMC slides into critical slowing down and topological freezing.

![beta scan](beta_scan.png)

![timescales](timescales.png)

## The three starting points

- **Diffusion seed** -- the raw conditional-diffusion output for this coupling: one inverse-RG step from a direct-HMC base ensemble at the matched coarse coupling (ancestral sampling + the deterministic coarse-charge transport), with **no** rethermalization sweeps applied: every bit of equilibration the seed needs is measured here, in HMC trajectories.
- **Hot start** -- every link angle drawn uniformly from (-pi, pi]: a completely disordered (infinite-temperature) configuration. The standard way to initialize a fresh HMC chain without prior information.
- **Cold start** -- every link angle set to zero: the perfectly ordered (beta -> infinity) configuration, the other standard initialization.

## Summary

| rung | L | beta | t_therm diffusion seed | standard-HMC interval 2 tau_int | margin (interval - t_therm) | burn-in hot / cold | tau_int(Q) |
|---|---|---|---|---|---|---|---|
| F_L16_bc75.3776_L16_beta300 | 16 | 300 | never | 88.3 | -- | nan / nan | frozen (0 tunnelings in 321 x 64 traj) |
| F_L16_bc100.377_L16_beta400 | 16 | 400 | 0 | 20.3 | 20.3 traj | nan / nan | frozen (0 tunnelings in 321 x 64 traj) |
| F_L16_bc137.876_L16_beta550 | 16 | 550 | never | 15.1 | -- | nan / nan | frozen (0 tunnelings in 321 x 64 traj) |
| F_L16_bc187.876_L16_beta750 | 16 | 750 | never | 20.7 | -- | nan / nan | frozen (0 tunnelings in 321 x 64 traj) |
| F_L16_bc250.376_L16_beta1000 | 16 | 1000 | 478 | 17.8 | -460.2 traj | nan / 3 | frozen (0 tunnelings in 321 x 64 traj) |
| F_L16_bc375.375_L16_beta1500 | 16 | 1500 | 0 | 17.3 | 17.3 traj | nan / nan | frozen (0 tunnelings in 321 x 64 traj) |
| F_L16_bc500.375_L16_beta2000 | 16 | 2000 | never | 13.4 | -- | nan / nan | frozen (0 tunnelings in 321 x 64 traj) |

## Wall-clock accounting

All timescales above are in HMC trajectories -- the honest *ergodicity* unit. This table converts to seconds on this machine so the economics are explicit. Batched chains produce n_chains configs per trajectory, so per-config costs divide by the chain count; the diffusion sampling cost amortizes over the whole generated batch.

| case | seed: sample s/config | seed: t_therm s (batch) | HMC interval s/config | hot burn-in s (batch) | s/traj (batch) |
|---|---|---|---|---|---|
| F_L16_bc75.3776_L16_beta300 | 0.1 | never | 0.23 | never | 0.17 |
| F_L16_bc100.377_L16_beta400 | 0.1 | 0.0 | 0.06 | never | 0.20 |
| F_L16_bc137.876_L16_beta550 | 0.1 | never | 0.05 | never | 0.22 |
| F_L16_bc187.876_L16_beta750 | 0.1 | never | 0.08 | never | 0.24 |
| F_L16_bc250.376_L16_beta1000 | 0.1 | 141.6 | 0.08 | never | 0.29 |
| F_L16_bc375.375_L16_beta1500 | 0.1 | 0.0 | 0.09 | never | 0.35 |
| F_L16_bc500.375_L16_beta2000 | 0.1 | never | 0.08 | never | 0.40 |

## Fitted relaxation times across starts

Exponential fits C + A exp(-t/tau) to the ensemble-mean plaquette and W(2x2) relaxation curves, per starting point (the cross-start comparison of characteristic times; a start already at its plateau fits no decay, which is the desired outcome for the diffusion seed).

| case | obs | tau: diffusion seed | tau: hot start | tau: cold start |
|---|---|---|---|---|
| F_L16_bc75.3776_L16_beta300 | plaquette | 8.2 +- 1.4 | 1.7 +- 0.0 | 43.0 +- 1.6 |
| F_L16_bc75.3776_L16_beta300 | wilson_2x2 | 18.2 +- 7.6 | 4.0 +- 0.1 | 27.9 +- 1.1 |
| F_L16_bc100.377_L16_beta400 | plaquette | 10.7 +- 2.0 | 1.6 +- 0.0 | 10.4 +- 0.5 |
| F_L16_bc100.377_L16_beta400 | wilson_2x2 | unreliable (tau exceeds window) | 3.4 +- 0.0 | 8.1 +- 0.4 |
| F_L16_bc137.876_L16_beta550 | plaquette | no measurable decay (starts at plateau; tau unconstrained) | 1.6 +- 0.0 | 5.5 +- 0.2 |
| F_L16_bc137.876_L16_beta550 | wilson_2x2 | 3.9 +- 1.7 | 4.5 +- 0.1 | 5.6 +- 0.2 |
| F_L16_bc187.876_L16_beta750 | plaquette | unconstrained fit (tau error exceeds tau) | 1.6 +- 0.0 | 2.2 +- 0.1 |
| F_L16_bc187.876_L16_beta750 | wilson_2x2 | 24.8 +- 24.6 | 3.8 +- 0.1 | 1.4 +- 0.1 |
| F_L16_bc250.376_L16_beta1000 | plaquette | unreliable (tau exceeds window) | 1.7 +- 0.0 | 2.3 +- 0.1 |
| F_L16_bc250.376_L16_beta1000 | wilson_2x2 | no measurable decay (starts at plateau; tau unconstrained) | 3.4 +- 0.1 | 2.9 +- 0.1 |
| F_L16_bc375.375_L16_beta1500 | plaquette | 10.0 +- 1.8 | 1.6 +- 0.0 | 4.7 +- 0.2 |
| F_L16_bc375.375_L16_beta1500 | wilson_2x2 | 0.7 +- 0.3 | 3.6 +- 0.1 | 2.0 +- 0.1 |
| F_L16_bc500.375_L16_beta2000 | plaquette | 3.5 +- 0.3 | 1.5 +- 0.0 | 4.5 +- 0.2 |
| F_L16_bc500.375_L16_beta2000 | wilson_2x2 | 3.5 +- 0.8 | 2.8 +- 0.1 | 4.9 +- 0.2 |

t_therm and burn-in are the slowest Wilson-loop observable (plaquette, W(2x2), W(4x4)); topology is stricter still for the fresh chains: their Q^2 **never** reaches the exact value at the frozen rungs, while the diffusion seed inherits the correct topological sector from the coarse ensemble it was generated from (see the Q^2 panels and per-rung tables below).

Thermalization time `t_therm` = first trajectory at which the ensemble-mean z-score vs the exact value satisfies |z| <= 2 and stays there for 5 consecutive trajectories (t = 0: already thermalized before any HMC). For the diffusion seed, t_therm is computed on a random subsample of chains matched to the baseline chain count so all starts are compared at equal statistical power. `tau_int` is Madras-Sokal, measured on the second half of the hot-start chains, averaged over chains. In the per-rung relaxation figures, triangles mark each start's t_therm, dashed curves are the exponential fits C + A exp(-t/tau) to the ensemble means (tau quoted per panel), and the right-hand panels track the ensemble mean's distance from the exact value in SEM units -- thermalized means inside the shaded |z| <= 2 band; the dotted vertical line there is the standard-HMC interval `2 tau_int`.

## What 'never' means, and where the ground truth comes from

'never' = the ensemble mean was still outside |z| <= 2 of the exact value after the full baseline budget; the per-rung sections quote the z-score it plateaued at. For hot starts at the large-beta rungs this is not a budget problem but a physical one: a random start freezes into a random topological sector (<Q^2> of order tens), plain HMC can never change Q at these couplings (tunneling is suppressed ~exp(-2 beta)), and the wrong sector biases every Wilson loop by an amount that never decays. Cold starts sit in the single sector Q = 0, so their Wilson loops do eventually converge, but <Q^2> stays pinned at 0 forever.

None of the exact values in this report come from fine-lattice HMC: the ground truth is the character expansion of 2D compact U(1) (`diffusion/lgt/exact.py`), which gives every Wilson loop, P(Q) and chi_top in closed form at finite volume. Each diffusion seed here is one inverse-RG step from a direct-HMC base ensemble at the matched coarse coupling beta_c (L=16), where HMC mixes well -- which is precisely why it can start chains in regions standard HMC cannot reach.

## F_L16_bc75.3776_L16_beta300

HMC: step size 0.0231, 43 leapfrog steps, acceptance seed/hot/cold = 0.989/0.984/0.988. Diffusion-seed batch: 64 chains x 96 trajectories (0.16 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta300/F_L16_bc75.3776_L16_beta300_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 41.70 +- 1.56, wilson_2x2 = 42.92 +- 1.79, wilson_4x4 = 44.14 +- 1.98, wilson_6x6 = 39.73 +- 2.08. Topology: hot-start HMC L=16 beta=300 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 6; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 187.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9985 | 1.37e-05 | 0.9983 | 12.89 | 0.9983 | 1.174e-05 | 10.23 | 1.989e-08 |  |
| wilson_1x1 | 0.9985 | 1.37e-05 | 0.9983 | 12.89 | 0.9983 | 1.174e-05 | 10.23 | 1.989e-08 |  |
| wilson_1x2 | 0.997 | 2.985e-05 | 0.9967 | 8.87 | 0.9966 | 2.808e-05 | 8.17 | 4.265e-07 |  |
| wilson_2x2 | 0.9937 | 9.853e-05 | 0.9934 | 2.059 | 0.9931 | 8.549e-05 | 3.923 | 0.0001523 |  |
| wilson_2x3 | 0.9906 | 0.0001818 | 0.9903 | 1.649 | 0.9898 | 0.0001576 | 3.072 | 0.001695 |  |
| wilson_3x3 | 0.9858 | 0.0003308 | 0.9856 | 0.6335 | 0.9849 | 0.0002727 | 2.024 | 0.1867 |  |
| wilson_3x4 | 0.9811 | 0.0005141 | 0.9811 | -0.01293 | 0.9802 | 0.0003956 | 1.37 | 0.4056 |  |
| wilson_4x4 | 0.9746 | 0.0007602 | 0.9753 | -0.89 | 0.974 | 0.0006338 | 0.5715 | 0.8723 |  |
| wilson_4x5 | 0.9686 | 0.00112 | 0.9697 | -1 | 0.9677 | 0.0008701 | 0.5999 | 0.9433 |  |
| wilson_5x5 | 0.9612 | 0.001453 | 0.963 | -1.28 | 0.9599 | 0.00123 | 0.6704 | 0.8723 |  |
| wilson_5x6 | 0.9539 | 0.001953 | 0.9567 | -1.442 | 0.9523 | 0.001466 | 0.6882 | 0.6123 |  |
| wilson_6x6 | 0.9456 | 0.00239 | 0.9497 | -1.712 | 0.9437 | 0.00204 | 0.5868 | 0.3192 |  |
| wilson_6x7 | 0.9379 | 0.003027 | 0.9431 | -1.693 | 0.9359 | 0.002275 | 0.5369 | 0.2464 |  |
| wilson_7x7 | 0.9296 | 0.003605 | 0.936 | -1.774 | 0.9279 | 0.002938 | 0.3653 | 0.5044 |  |
| wilson_7x8 | 0.9222 | 0.004303 | 0.9296 | -1.72 | 0.9202 | 0.003019 | 0.3656 | 0.4056 |  |
| wilson_8x8 | 0.9149 | 0.004799 | 0.923 | -1.689 | 0.9125 | 0.00367 | 0.3971 | 0.2811 |  |
| creutz_2 | 0.001761 | 5.7e-05 | 0.001611 | 2.634 |  |  |  |  |  |
| creutz_3 | 0.001695 | 0.0001375 | 0.001506 | 1.372 |  |  |  |  |  |
| creutz_4 | 0.001818 | 0.0001908 | 0.00135 | 2.452 |  |  |  |  |  |
| creutz_5 | 0.001456 | 0.0003029 | 0.001141 | 1.04 |  |  |  |  |  |
| creutz_6 | 0.001238 | 0.0004124 | 0.0008804 | 0.8677 |  |  |  |  |  |
| creutz_7 | 0.0008455 | 0.0006937 | 0.0005674 | 0.401 |  |  |  |  |  |
| creutz_8 | -0.0001139 | 0.001052 | 0.0002022 | -0.3004 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 1.872e-10 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 7.311e-13 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.198e-08 | nan | 2 | nan |  |  |  |  | 1 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9983 | 1.414e-05 | 0.9983 | 0.27 | 0.9983 | 1.174e-05 | 0.6335 | 0.6123 |  |
| wilson_1x1 | 0.9983 | 1.414e-05 | 0.9983 | 0.27 | 0.9983 | 1.174e-05 | 0.6335 | 0.6123 |  |
| wilson_1x2 | 0.9967 | 2.754e-05 | 0.9967 | 0.6628 | 0.9966 | 2.808e-05 | 2.245 | 0.07294 |  |
| wilson_2x2 | 0.9935 | 8.319e-05 | 0.9934 | 0.606 | 0.9931 | 8.549e-05 | 3.012 | 0.0002025 |  |
| wilson_2x3 | 0.9903 | 0.0001676 | 0.9903 | -0.006052 | 0.9898 | 0.0001576 | 1.906 | 0.04298 |  |
| wilson_3x3 | 0.9857 | 0.0003139 | 0.9856 | 0.2191 | 0.9849 | 0.0002727 | 1.748 | 0.1614 |  |
| wilson_3x4 | 0.9811 | 0.0004742 | 0.9811 | 0.08188 | 0.9802 | 0.0003956 | 1.513 | 0.1614 |  |
| wilson_4x4 | 0.9754 | 0.0007206 | 0.9753 | 0.1545 | 0.974 | 0.0006338 | 1.41 | 0.1614 |  |
| wilson_4x5 | 0.9697 | 0.0009295 | 0.9697 | 0.02066 | 0.9677 | 0.0008701 | 1.563 | 0.1867 |  |
| wilson_5x5 | 0.9631 | 0.001208 | 0.963 | 0.03252 | 0.9599 | 0.00123 | 1.842 | 0.07294 |  |
| wilson_5x6 | 0.9568 | 0.001544 | 0.9567 | 0.01554 | 0.9523 | 0.001466 | 2.123 | 0.1015 |  |
| wilson_6x6 | 0.9496 | 0.001982 | 0.9497 | -0.03848 | 0.9437 | 0.00204 | 2.061 | 0.05149 |  |
| wilson_6x7 | 0.9429 | 0.002377 | 0.9431 | -0.06376 | 0.9359 | 0.002275 | 2.129 | 0.02956 |  |
| wilson_7x7 | 0.9354 | 0.002886 | 0.936 | -0.2094 | 0.9279 | 0.002938 | 1.818 | 0.01997 |  |
| wilson_7x8 | 0.9296 | 0.003238 | 0.9296 | 0.01874 | 0.9202 | 0.003019 | 2.12 | 0.01326 |  |
| wilson_8x8 | 0.9226 | 0.003749 | 0.923 | -0.09415 | 0.9125 | 0.00367 | 1.935 | 0.008658 |  |
| creutz_2 | 0.001593 | 6.071e-05 | 0.001611 | -0.2955 |  |  |  |  |  |
| creutz_3 | 0.001384 | 0.0001365 | 0.001506 | -0.8979 |  |  |  |  |  |
| creutz_4 | 0.001245 | 0.0002418 | 0.00135 | -0.4333 |  |  |  |  |  |
| creutz_5 | 0.001026 | 0.0003772 | 0.001141 | -0.3058 |  |  |  |  |  |
| creutz_6 | 0.00097 | 0.0005249 | 0.0008804 | 0.1708 |  |  |  |  |  |
| creutz_7 | 0.0009719 | 0.0006703 | 0.0005674 | 0.6035 |  |  |  |  |  |
| creutz_8 | 0.001361 | 0.000772 | 0.0002022 | 1.501 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 1.872e-10 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 7.311e-13 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.198e-08 | nan | 2 | nan |  |  |  |  | 1 |

## F_L16_bc100.377_L16_beta400

HMC: step size 0.0200, 50 leapfrog steps, acceptance seed/hot/cold = 0.989/0.979/0.989. Diffusion-seed batch: 64 chains x 96 trajectories (0.20 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta400/F_L16_bc100.377_L16_beta400_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 10.17 +- 1.03, wilson_2x2 = 4.92 +- 0.72, wilson_4x4 = 1.03 +- 0.05, wilson_6x6 = 0.62 +- 0.03. Topology: hot-start HMC L=16 beta=400 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 6.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9988 | 1.331e-05 | 0.9988 | 6.143 | 0.9987 | 8.634e-06 | 6.192 | 4.659e-05 |  |
| wilson_1x1 | 0.9988 | 1.331e-05 | 0.9988 | 6.143 | 0.9987 | 8.634e-06 | 6.192 | 4.659e-05 |  |
| wilson_1x2 | 0.9976 | 3.403e-05 | 0.9975 | 3.715 | 0.9975 | 1.908e-05 | 4.24 | 0.006949 |  |
| wilson_2x2 | 0.9952 | 8.71e-05 | 0.9951 | 1.631 | 0.9949 | 4.527e-05 | 3.044 | 0.01074 |  |
| wilson_2x3 | 0.9929 | 0.0001659 | 0.9927 | 1.267 | 0.9925 | 9.126e-05 | 1.894 | 0.02956 |  |
| wilson_3x3 | 0.9896 | 0.0003208 | 0.9892 | 1.297 | 0.9889 | 0.0001873 | 2.024 | 0.01997 |  |
| wilson_3x4 | 0.9863 | 0.0004655 | 0.9858 | 1.082 | 0.9853 | 0.0003112 | 1.812 | 0.1015 |  |
| wilson_4x4 | 0.982 | 0.0006672 | 0.9814 | 0.8998 | 0.9807 | 0.0005224 | 1.478 | 0.4535 |  |
| wilson_4x5 | 0.9778 | 0.0008462 | 0.9772 | 0.6641 | 0.9764 | 0.0007607 | 1.151 | 0.5044 |  |
| wilson_5x5 | 0.9729 | 0.001179 | 0.9722 | 0.6293 | 0.9709 | 0.001087 | 1.277 | 0.4056 |  |
| wilson_5x6 | 0.968 | 0.001442 | 0.9674 | 0.4477 | 0.9662 | 0.001412 | 0.8909 | 0.5575 |  |
| wilson_6x6 | 0.9628 | 0.001803 | 0.962 | 0.4408 | 0.9599 | 0.001862 | 1.116 | 0.3607 |  |
| wilson_6x7 | 0.9572 | 0.002169 | 0.957 | 0.1096 | 0.9549 | 0.002198 | 0.754 | 0.4535 |  |
| wilson_7x7 | 0.9518 | 0.002676 | 0.9516 | 0.06046 | 0.9485 | 0.002731 | 0.8486 | 0.6123 |  |
| wilson_7x8 | 0.9466 | 0.003043 | 0.9467 | -0.03542 | 0.9431 | 0.003035 | 0.8232 | 0.5044 |  |
| wilson_8x8 | 0.9415 | 0.003443 | 0.9417 | -0.06338 | 0.9371 | 0.003545 | 0.8867 | 0.5044 |  |
| creutz_2 | 0.001236 | 5.139e-05 | 0.001208 | 0.5615 |  |  |  |  |  |
| creutz_3 | 0.0009894 | 0.0001036 | 0.001129 | -1.351 |  |  |  |  |  |
| creutz_4 | 0.001001 | 0.0001687 | 0.001012 | -0.06447 |  |  |  |  |  |
| creutz_5 | 0.0006308 | 0.0003017 | 0.0008556 | -0.7449 |  |  |  |  |  |
| creutz_6 | 0.0004057 | 0.0003236 | 0.00066 | -0.7858 |  |  |  |  |  |
| creutz_7 | -7.384e-05 | 0.0005006 | 0.0004253 | -0.9971 |  |  |  |  |  |
| creutz_8 | -1.432e-05 | 0.0005496 | 0.0001516 | -0.3018 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 8.168e-14 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 3.191e-16 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 5.227e-12 | nan | 2 | nan |  |  |  |  | 1 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9988 | 1.52e-05 | 0.9988 | -0.2136 | 0.9987 | 8.634e-06 | 0.757 | 0.5044 |  |
| wilson_1x1 | 0.9988 | 1.52e-05 | 0.9988 | -0.2136 | 0.9987 | 8.634e-06 | 0.757 | 0.5044 |  |
| wilson_1x2 | 0.9975 | 2.996e-05 | 0.9975 | -0.4953 | 0.9975 | 1.908e-05 | 0.6799 | 0.9115 |  |
| wilson_2x2 | 0.995 | 7.92e-05 | 0.9951 | -0.4442 | 0.9949 | 4.527e-05 | 1.333 | 0.215 |  |
| wilson_2x3 | 0.9926 | 0.0001267 | 0.9927 | -0.9286 | 0.9925 | 9.126e-05 | 0.1975 | 0.5575 |  |
| wilson_3x3 | 0.989 | 0.0002293 | 0.9892 | -1.044 | 0.9889 | 0.0001873 | 0.3261 | 0.4056 |  |
| wilson_3x4 | 0.9855 | 0.0003432 | 0.9858 | -0.9607 | 0.9853 | 0.0003112 | 0.3923 | 0.119 |  |
| wilson_4x4 | 0.981 | 0.0005448 | 0.9814 | -0.7275 | 0.9807 | 0.0005224 | 0.3389 | 0.3192 |  |
| wilson_4x5 | 0.9767 | 0.0007375 | 0.9772 | -0.6766 | 0.9764 | 0.0007607 | 0.2352 | 0.4056 |  |
| wilson_5x5 | 0.9714 | 0.001045 | 0.9722 | -0.697 | 0.9709 | 0.001087 | 0.3838 | 0.5575 |  |
| wilson_5x6 | 0.9664 | 0.001315 | 0.9674 | -0.7702 | 0.9662 | 0.001412 | 0.07248 | 0.9671 |  |
| wilson_6x6 | 0.9604 | 0.00175 | 0.962 | -0.9419 | 0.9599 | 0.001862 | 0.1758 | 0.8269 |  |
| wilson_6x7 | 0.9548 | 0.002081 | 0.957 | -1.048 | 0.9549 | 0.002198 | -0.02953 | 0.9433 |  |
| wilson_7x7 | 0.9485 | 0.002574 | 0.9516 | -1.217 | 0.9485 | 0.002731 | -0.01294 | 0.9671 |  |
| wilson_7x8 | 0.943 | 0.002891 | 0.9467 | -1.278 | 0.9431 | 0.003035 | -0.01173 | 0.9929 |  |
| wilson_8x8 | 0.9371 | 0.003401 | 0.9417 | -1.346 | 0.9371 | 0.003545 | 0.004636 | 0.9833 |  |
| creutz_2 | 0.001216 | 5.175e-05 | 0.001208 | 0.1711 |  |  |  |  |  |
| creutz_3 | 0.00117 | 9.523e-05 | 0.001129 | 0.4241 |  |  |  |  |  |
| creutz_4 | 0.0009891 | 0.0001686 | 0.001012 | -0.1361 |  |  |  |  |  |
| creutz_5 | 0.0009873 | 0.0002229 | 0.0008556 | 0.5911 |  |  |  |  |  |
| creutz_6 | 0.00103 | 0.0003803 | 0.00066 | 0.9726 |  |  |  |  |  |
| creutz_7 | 0.0008749 | 0.0005699 | 0.0004253 | 0.7889 |  |  |  |  |  |
| creutz_8 | 0.0004984 | 0.00083 | 0.0001516 | 0.4179 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 8.168e-14 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 3.191e-16 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 5.227e-12 | nan | 2 | nan |  |  |  |  | 1 |

## F_L16_bc137.876_L16_beta550

HMC: step size 0.0171, 59 leapfrog steps, acceptance seed/hot/cold = 0.987/0.951/0.987. Diffusion-seed batch: 64 chains x 96 trajectories (0.21 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta550/F_L16_bc137.876_L16_beta550_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 5.44 +- 0.65, wilson_2x2 = 5.52 +- 0.67, wilson_4x4 = 7.53 +- 0.84, wilson_6x6 = 10.47 +- 0.95. Topology: hot-start HMC L=16 beta=550 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 6.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9991 | 9.952e-06 | 0.9991 | 3.992 | 0.9991 | 5.287e-06 | 0.8232 | 0.5044 |  |
| wilson_1x1 | 0.9991 | 9.952e-06 | 0.9991 | 3.992 | 0.9991 | 5.287e-06 | 0.8232 | 0.5044 |  |
| wilson_1x2 | 0.9982 | 2.035e-05 | 0.9982 | 2.123 | 0.9983 | 1.62e-05 | -1.295 | 0.2464 |  |
| wilson_2x2 | 0.9965 | 6.104e-05 | 0.9964 | 1.36 | 0.9966 | 4.052e-05 | -1.592 | 0.2464 |  |
| wilson_2x3 | 0.9949 | 8.661e-05 | 0.9947 | 2.141 | 0.995 | 6.856e-05 | -1.357 | 0.1389 |  |
| wilson_3x3 | 0.9926 | 0.000181 | 0.9921 | 2.593 | 0.9927 | 0.0001273 | -0.2399 | 0.9433 |  |
| wilson_3x4 | 0.9904 | 0.0002478 | 0.9896 | 3.011 | 0.9904 | 0.0001841 | 0.01981 | 0.9671 |  |
| wilson_4x4 | 0.9877 | 0.0003926 | 0.9864 | 3.309 | 0.9874 | 0.0002568 | 0.6326 | 0.7766 |  |
| wilson_4x5 | 0.9853 | 0.0005191 | 0.9834 | 3.652 | 0.9846 | 0.0003466 | 1.035 | 0.2464 |  |
| wilson_5x5 | 0.9825 | 0.000744 | 0.9797 | 3.841 | 0.9812 | 0.0004518 | 1.513 | 0.2811 |  |
| wilson_5x6 | 0.9797 | 0.0009321 | 0.9762 | 3.781 | 0.9781 | 0.0005667 | 1.447 | 0.2464 |  |
| wilson_6x6 | 0.9769 | 0.00118 | 0.9722 | 3.987 | 0.9743 | 0.0007193 | 1.891 | 0.1015 |  |
| wilson_6x7 | 0.9737 | 0.001433 | 0.9686 | 3.593 | 0.9708 | 0.0008489 | 1.723 | 0.02956 |  |
| wilson_7x7 | 0.9707 | 0.001765 | 0.9646 | 3.476 | 0.967 | 0.001058 | 1.8 | 0.04298 |  |
| wilson_7x8 | 0.9672 | 0.002004 | 0.961 | 3.125 | 0.9638 | 0.001173 | 1.492 | 0.08625 |  |
| wilson_8x8 | 0.9641 | 0.002263 | 0.9573 | 3.037 | 0.9601 | 0.001279 | 1.554 | 0.04298 |  |
| creutz_2 | 0.0008414 | 3.796e-05 | 0.0008779 | -0.9622 |  |  |  |  |  |
| creutz_3 | 0.0006376 | 7.573e-05 | 0.0008211 | -2.423 |  |  |  |  |  |
| creutz_4 | 0.0004537 | 0.0001191 | 0.0007358 | -2.368 |  |  |  |  |  |
| creutz_5 | 0.0002439 | 0.0001963 | 0.000622 | -1.926 |  |  |  |  |  |
| creutz_6 | -5.332e-05 | 0.0002659 | 0.0004798 | -2.005 |  |  |  |  |  |
| creutz_7 | -0.0002545 | 0.0003735 | 0.0003092 | -1.509 |  |  |  |  |  |
| creutz_8 | -0.0003894 | 0.0005094 | 0.0001102 | -0.9807 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 2.399e-12 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 9.372e-15 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.706e-11 | nan | 2 | nan |  |  |  |  | 1 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9991 | 1.115e-05 | 0.9991 | 1.757 | 0.9991 | 5.287e-06 | -0.8798 | 0.6123 |  |
| wilson_1x1 | 0.9991 | 1.115e-05 | 0.9991 | 1.757 | 0.9991 | 5.287e-06 | -0.8798 | 0.6123 |  |
| wilson_1x2 | 0.9982 | 3.026e-05 | 0.9982 | 1.497 | 0.9983 | 1.62e-05 | -0.9203 | 0.6679 |  |
| wilson_2x2 | 0.9965 | 7.129e-05 | 0.9964 | 1.225 | 0.9966 | 4.052e-05 | -1.37 | 0.4056 |  |
| wilson_2x3 | 0.9948 | 0.0001201 | 0.9947 | 1.285 | 0.995 | 6.856e-05 | -1.309 | 0.9115 |  |
| wilson_3x3 | 0.9925 | 0.0002086 | 0.9921 | 1.658 | 0.9927 | 0.0001273 | -0.7225 | 0.8723 |  |
| wilson_3x4 | 0.9902 | 0.000322 | 0.9896 | 1.591 | 0.9904 | 0.0001841 | -0.6137 | 0.7231 |  |
| wilson_4x4 | 0.9875 | 0.0004377 | 0.9864 | 2.311 | 0.9874 | 0.0002568 | 0.01839 | 0.9115 |  |
| wilson_4x5 | 0.9846 | 0.0006241 | 0.9834 | 1.982 | 0.9846 | 0.0003466 | -0.01796 | 0.6679 |  |
| wilson_5x5 | 0.9816 | 0.0008006 | 0.9797 | 2.352 | 0.9812 | 0.0004518 | 0.372 | 0.7231 |  |
| wilson_5x6 | 0.9786 | 0.001013 | 0.9762 | 2.41 | 0.9781 | 0.0005667 | 0.4259 | 0.7231 |  |
| wilson_6x6 | 0.9753 | 0.00123 | 0.9722 | 2.519 | 0.9743 | 0.0007193 | 0.7068 | 0.5575 |  |
| wilson_6x7 | 0.9725 | 0.001411 | 0.9686 | 2.804 | 0.9708 | 0.0008489 | 1.02 | 0.215 |  |
| wilson_7x7 | 0.9693 | 0.001637 | 0.9646 | 2.882 | 0.967 | 0.001058 | 1.174 | 0.3607 |  |
| wilson_7x8 | 0.9666 | 0.00182 | 0.961 | 3.104 | 0.9638 | 0.001173 | 1.316 | 0.3192 |  |
| wilson_8x8 | 0.9635 | 0.002072 | 0.9573 | 3.002 | 0.9601 | 0.001279 | 1.391 | 0.1614 |  |
| creutz_2 | 0.0008615 | 3.378e-05 | 0.0008779 | -0.4873 |  |  |  |  |  |
| creutz_3 | 0.0006951 | 7.557e-05 | 0.0008211 | -1.666 |  |  |  |  |  |
| creutz_4 | 0.000397 | 0.000121 | 0.0007358 | -2.8 |  |  |  |  |  |
| creutz_5 | 0.0001903 | 0.0001873 | 0.000622 | -2.305 |  |  |  |  |  |
| creutz_6 | 0.0003698 | 0.0002382 | 0.0004798 | -0.4619 |  |  |  |  |  |
| creutz_7 | 0.0004003 | 0.0002999 | 0.0003092 | 0.3036 |  |  |  |  |  |
| creutz_8 | 0.0004774 | 0.0003514 | 0.0001102 | 1.045 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 2.399e-12 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 9.372e-15 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.706e-11 | nan | 2 | nan |  |  |  |  | 1 |

## F_L16_bc187.876_L16_beta750

HMC: step size 0.0146, 68 leapfrog steps, acceptance seed/hot/cold = 0.986/0.919/0.988. Diffusion-seed batch: 64 chains x 96 trajectories (0.26 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta750/F_L16_bc187.876_L16_beta750_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 10.33 +- 1.28, wilson_2x2 = 8.78 +- 1.27, wilson_4x4 = 0.99 +- 0.04, wilson_6x6 = 0.98 +- 0.03. Topology: hot-start HMC L=16 beta=750 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 6; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 2060.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9993 | 5.721e-06 | 0.9993 | 2.346 | 0.9993 | 7.234e-06 | 1.243 | 0.3192 |  |
| wilson_1x1 | 0.9993 | 5.721e-06 | 0.9993 | 2.346 | 0.9993 | 7.234e-06 | 1.243 | 0.3192 |  |
| wilson_1x2 | 0.9987 | 1.385e-05 | 0.9987 | 1.441 | 0.9987 | 1.625e-05 | 1.223 | 0.5575 |  |
| wilson_2x2 | 0.9974 | 3.835e-05 | 0.9974 | -0.377 | 0.9974 | 3.388e-05 | -0.2867 | 0.7231 |  |
| wilson_2x3 | 0.9961 | 8.18e-05 | 0.9961 | -0.2132 | 0.9961 | 6.144e-05 | -0.2715 | 0.9929 |  |
| wilson_3x3 | 0.9942 | 0.0001258 | 0.9942 | 0.121 | 0.9943 | 0.0001249 | -0.2394 | 0.9671 |  |
| wilson_3x4 | 0.9924 | 0.0002002 | 0.9924 | 0.1181 | 0.9925 | 0.0001851 | -0.1399 | 0.8723 |  |
| wilson_4x4 | 0.9901 | 0.0002837 | 0.99 | 0.02502 | 0.9902 | 0.0002679 | -0.2683 | 0.8723 |  |
| wilson_4x5 | 0.9879 | 0.0003929 | 0.9878 | 0.2287 | 0.9878 | 0.0003652 | 0.09423 | 0.9671 |  |
| wilson_5x5 | 0.9852 | 0.0005776 | 0.9851 | 0.2663 | 0.9853 | 0.0004693 | -0.1269 | 0.8269 |  |
| wilson_5x6 | 0.9829 | 0.0007055 | 0.9825 | 0.6163 | 0.9826 | 0.0005999 | 0.3675 | 0.6679 |  |
| wilson_6x6 | 0.98 | 0.0009467 | 0.9796 | 0.4922 | 0.9801 | 0.0007213 | -0.009996 | 0.5044 |  |
| wilson_6x7 | 0.9777 | 0.001088 | 0.9769 | 0.7473 | 0.9773 | 0.0008309 | 0.2332 | 0.3192 |  |
| wilson_7x7 | 0.9749 | 0.001381 | 0.9739 | 0.7388 | 0.9749 | 0.0009398 | 0.002769 | 0.4535 |  |
| wilson_7x8 | 0.9727 | 0.001506 | 0.9712 | 0.9875 | 0.9723 | 0.001057 | 0.2496 | 0.4056 |  |
| wilson_8x8 | 0.97 | 0.001731 | 0.9685 | 0.8969 | 0.9698 | 0.001125 | 0.1288 | 0.215 |  |
| creutz_2 | 0.0006847 | 3.145e-05 | 0.0006437 | 1.304 |  |  |  |  |  |
| creutz_3 | 0.0005661 | 5.404e-05 | 0.000602 | -0.663 |  |  |  |  |  |
| creutz_4 | 0.0005646 | 9.857e-05 | 0.0005394 | 0.2554 |  |  |  |  |  |
| creutz_5 | 0.0004747 | 0.0001574 | 0.000456 | 0.1186 |  |  |  |  |  |
| creutz_6 | 0.000605 | 0.0002307 | 0.0003518 | 1.098 |  |  |  |  |  |
| creutz_7 | 0.0003691 | 0.0003062 | 0.0002267 | 0.4649 |  |  |  |  |  |
| creutz_8 | 0.0004916 | 0.0003988 | 8.078e-05 | 1.03 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 2.06e-09 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 8.047e-12 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.465e-08 | nan | 2 | nan |  |  |  |  | 1 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9993 | 5.796e-06 | 0.9993 | -0.06653 | 0.9993 | 7.234e-06 | -0.2525 | 0.8723 |  |
| wilson_1x1 | 0.9993 | 5.796e-06 | 0.9993 | -0.06653 | 0.9993 | 7.234e-06 | -0.2525 | 0.8723 |  |
| wilson_1x2 | 0.9987 | 1.498e-05 | 0.9987 | 0.2389 | 0.9987 | 1.625e-05 | 0.4407 | 0.7231 |  |
| wilson_2x2 | 0.9974 | 4.048e-05 | 0.9974 | -0.3988 | 0.9974 | 3.388e-05 | -0.3099 | 0.5044 |  |
| wilson_2x3 | 0.9961 | 6.694e-05 | 0.9961 | -0.2923 | 0.9961 | 6.144e-05 | -0.3291 | 0.5044 |  |
| wilson_3x3 | 0.9942 | 0.0001335 | 0.9942 | -0.3476 | 0.9943 | 0.0001249 | -0.5693 | 0.3607 |  |
| wilson_3x4 | 0.9923 | 0.0001883 | 0.9924 | -0.6783 | 0.9925 | 0.0001851 | -0.7179 | 0.6123 |  |
| wilson_4x4 | 0.9897 | 0.0002887 | 0.99 | -1.043 | 0.9902 | 0.0002679 | -1.048 | 0.5044 |  |
| wilson_4x5 | 0.9873 | 0.0003976 | 0.9878 | -1.197 | 0.9878 | 0.0003652 | -0.9547 | 0.6123 |  |
| wilson_5x5 | 0.9845 | 0.0005233 | 0.9851 | -1.08 | 0.9853 | 0.0004693 | -1.157 | 0.119 |  |
| wilson_5x6 | 0.9818 | 0.0006899 | 0.9825 | -0.9595 | 0.9826 | 0.0005999 | -0.8274 | 0.3607 |  |
| wilson_6x6 | 0.9787 | 0.0008849 | 0.9796 | -1.038 | 0.9801 | 0.0007213 | -1.223 | 0.1867 |  |
| wilson_6x7 | 0.9761 | 0.001061 | 0.9769 | -0.7434 | 0.9773 | 0.0008309 | -0.952 | 0.2811 |  |
| wilson_7x7 | 0.9726 | 0.001216 | 0.9739 | -1.111 | 0.9749 | 0.0009398 | -1.54 | 0.1867 |  |
| wilson_7x8 | 0.97 | 0.001406 | 0.9712 | -0.8774 | 0.9723 | 0.001057 | -1.286 | 0.3607 |  |
| wilson_8x8 | 0.9671 | 0.001528 | 0.9685 | -0.8938 | 0.9698 | 0.001125 | -1.398 | 0.3192 |  |
| creutz_2 | 0.0006674 | 2.52e-05 | 0.0006437 | 0.9419 |  |  |  |  |  |
| creutz_3 | 0.0006255 | 4.852e-05 | 0.000602 | 0.4857 |  |  |  |  |  |
| creutz_4 | 0.0006328 | 8.698e-05 | 0.0005394 | 1.074 |  |  |  |  |  |
| creutz_5 | 0.0003698 | 0.0001254 | 0.000456 | -0.6874 |  |  |  |  |  |
| creutz_6 | 0.0005154 | 0.0001974 | 0.0003518 | 0.8287 |  |  |  |  |  |
| creutz_7 | 0.0009375 | 0.0002958 | 0.0002267 | 2.403 |  |  |  |  |  |
| creutz_8 | 0.0003379 | 0.0003621 | 8.078e-05 | 0.71 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 2.06e-09 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 8.047e-12 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.465e-08 | nan | 2 | nan |  |  |  |  | 1 |

## F_L16_bc250.376_L16_beta1000

HMC: step size 0.0126, 79 leapfrog steps, acceptance seed/hot/cold = 0.986/0.814/0.986. Diffusion-seed batch: 64 chains x 96 trajectories (0.30 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta1000/F_L16_bc250.376_L16_beta1000_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 5.78 +- 1.41, wilson_2x2 = 6.84 +- 1.43, wilson_4x4 = 8.88 +- 1.48, wilson_6x6 = 11.37 +- 1.53. Topology: hot-start HMC L=16 beta=1000 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 5; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 178903.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9995 | 4.184e-06 | 0.9995 | 0.3401 | 0.9995 | 4.186e-06 | 1.933 | 0.3607 |  |
| wilson_1x1 | 0.9995 | 4.184e-06 | 0.9995 | 0.3401 | 0.9995 | 4.186e-06 | 1.933 | 0.3607 |  |
| wilson_1x2 | 0.999 | 1.229e-05 | 0.999 | 0.911 | 0.999 | 1.196e-05 | 1.727 | 0.4056 |  |
| wilson_2x2 | 0.9981 | 2.643e-05 | 0.998 | 1.233 | 0.998 | 2.666e-05 | 1.296 | 0.9115 |  |
| wilson_2x3 | 0.9972 | 4.009e-05 | 0.9971 | 1.958 | 0.9971 | 4.97e-05 | 1.25 | 0.7231 |  |
| wilson_3x3 | 0.9958 | 7.912e-05 | 0.9957 | 1.219 | 0.9957 | 8.624e-05 | 0.3888 | 0.5044 |  |
| wilson_3x4 | 0.9944 | 0.0001291 | 0.9943 | 0.5605 | 0.9944 | 0.0001203 | -0.3707 | 0.6123 |  |
| wilson_4x4 | 0.9926 | 0.0001866 | 0.9925 | 0.3468 | 0.9928 | 0.0001553 | -1.002 | 0.1015 |  |
| wilson_4x5 | 0.9908 | 0.0002646 | 0.9908 | -0.05978 | 0.9913 | 0.0002103 | -1.586 | 0.215 |  |
| wilson_5x5 | 0.9888 | 0.0003327 | 0.9888 | -0.03773 | 0.9896 | 0.0002564 | -2.023 | 0.06142 |  |
| wilson_5x6 | 0.9867 | 0.000432 | 0.9868 | -0.3852 | 0.9881 | 0.0003214 | -2.611 | 0.04298 |  |
| wilson_6x6 | 0.9845 | 0.0005147 | 0.9846 | -0.2673 | 0.9864 | 0.0003629 | -2.966 | 0.004418 |  |
| wilson_6x7 | 0.982 | 0.0006093 | 0.9826 | -1.011 | 0.9847 | 0.0004579 | -3.534 | 0.002168 |  |
| wilson_7x7 | 0.9797 | 0.0007387 | 0.9804 | -0.8983 | 0.983 | 0.0004859 | -3.721 | 0.0003536 |  |
| wilson_7x8 | 0.9772 | 0.0008468 | 0.9784 | -1.398 | 0.9814 | 0.0005688 | -4.149 | 0.0007896 |  |
| wilson_8x8 | 0.9752 | 0.0009732 | 0.9763 | -1.128 | 0.9798 | 0.0006012 | -4.084 | 0.0007896 |  |
| creutz_2 | 0.000471 | 1.694e-05 | 0.0004827 | -0.6879 |  |  |  |  |  |
| creutz_3 | 0.0004793 | 3.687e-05 | 0.0004514 | 0.7574 |  |  |  |  |  |
| creutz_4 | 0.000388 | 5.009e-05 | 0.0004045 | -0.3292 |  |  |  |  |  |
| creutz_5 | 0.0002575 | 8.618e-05 | 0.000342 | -0.9797 |  |  |  |  |  |
| creutz_6 | 7.892e-05 | 0.0001218 | 0.0002638 | -1.518 |  |  |  |  |  |
| creutz_7 | -0.0002668 | 0.000186 | 0.00017 | -2.348 |  |  |  |  |  |
| creutz_8 | -0.0005584 | 0.0002584 | 6.058e-05 | -2.395 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 1.789e-07 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 6.988e-10 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.307e-06 | nan | 2 | nan |  |  |  |  | 1 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9995 | 5.195e-06 | 0.9995 | -0.7784 | 0.9995 | 4.186e-06 | 0.8954 | 0.6123 |  |
| wilson_1x1 | 0.9995 | 5.195e-06 | 0.9995 | -0.7784 | 0.9995 | 4.186e-06 | 0.8954 | 0.6123 |  |
| wilson_1x2 | 0.999 | 1.098e-05 | 0.999 | -0.4899 | 0.999 | 1.196e-05 | 0.8025 | 0.5044 |  |
| wilson_2x2 | 0.998 | 3.414e-05 | 0.998 | -0.8226 | 0.998 | 2.666e-05 | -0.2776 | 0.9929 |  |
| wilson_2x3 | 0.997 | 6.927e-05 | 0.9971 | -0.7077 | 0.9971 | 4.97e-05 | -0.5595 | 0.8723 |  |
| wilson_3x3 | 0.9956 | 0.0001133 | 0.9957 | -0.6246 | 0.9957 | 8.624e-05 | -0.8546 | 0.4056 |  |
| wilson_3x4 | 0.9942 | 0.0001646 | 0.9943 | -0.5339 | 0.9944 | 0.0001203 | -1.107 | 0.5575 |  |
| wilson_4x4 | 0.9926 | 0.0002306 | 0.9925 | 0.1121 | 0.9928 | 0.0001553 | -1.015 | 0.6123 |  |
| wilson_4x5 | 0.991 | 0.0003027 | 0.9908 | 0.4594 | 0.9913 | 0.0002103 | -1.035 | 0.4056 |  |
| wilson_5x5 | 0.9891 | 0.0003807 | 0.9888 | 0.8221 | 0.9896 | 0.0002564 | -1.141 | 0.4056 |  |
| wilson_5x6 | 0.9874 | 0.0004625 | 0.9868 | 1.155 | 0.9881 | 0.0003214 | -1.252 | 0.4056 |  |
| wilson_6x6 | 0.9853 | 0.0005649 | 0.9846 | 1.148 | 0.9864 | 0.0003629 | -1.611 | 0.08625 |  |
| wilson_6x7 | 0.9834 | 0.0006209 | 0.9826 | 1.349 | 0.9847 | 0.0004579 | -1.607 | 0.215 |  |
| wilson_7x7 | 0.9813 | 0.0007344 | 0.9804 | 1.291 | 0.983 | 0.0004859 | -1.906 | 0.1867 |  |
| wilson_7x8 | 0.9794 | 0.0008381 | 0.9784 | 1.306 | 0.9814 | 0.0005688 | -1.929 | 0.1867 |  |
| wilson_8x8 | 0.9775 | 0.000964 | 0.9763 | 1.263 | 0.9798 | 0.0006012 | -2.075 | 0.1015 |  |
| creutz_2 | 0.0005041 | 2.037e-05 | 0.0004827 | 1.051 |  |  |  |  |  |
| creutz_3 | 0.0004523 | 3.949e-05 | 0.0004514 | 0.02313 |  |  |  |  |  |
| creutz_4 | 0.0002728 | 7.167e-05 | 0.0004045 | -1.837 |  |  |  |  |  |
| creutz_5 | 0.0002802 | 0.0001068 | 0.000342 | -0.5785 |  |  |  |  |  |
| creutz_6 | 0.0003712 | 0.0001167 | 0.0002638 | 0.9198 |  |  |  |  |  |
| creutz_7 | 0.0002497 | 0.0001517 | 0.00017 | 0.525 |  |  |  |  |  |
| creutz_8 | 8.357e-05 | 0.0002224 | 6.058e-05 | 0.1034 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 1.789e-07 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 6.988e-10 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 1.307e-06 | nan | 2 | nan |  |  |  |  | 1 |

## F_L16_bc375.375_L16_beta1500

HMC: step size 0.0103, 97 leapfrog steps, acceptance seed/hot/cold = 0.985/0.648/0.987. Diffusion-seed batch: 64 chains x 96 trajectories (0.36 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta1500/F_L16_bc375.375_L16_beta1500_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 8.63 +- 1.61, wilson_2x2 = 4.97 +- 1.43, wilson_4x4 = 4.36 +- 1.37, wilson_6x6 = 4.73 +- 1.37. Topology: hot-start HMC L=16 beta=1500 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 6; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 15953106.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9996 | 3.762e-06 | 0.9997 | -9.96 | 0.9997 | 4.084e-06 | -6.036 | 2.952e-07 |  |
| wilson_1x1 | 0.9996 | 3.762e-06 | 0.9997 | -9.96 | 0.9997 | 4.084e-06 | -6.036 | 2.952e-07 |  |
| wilson_1x2 | 0.9993 | 8.197e-06 | 0.9993 | -9.147 | 0.9993 | 6.854e-06 | -6.662 | 4.265e-07 |  |
| wilson_2x2 | 0.9985 | 2.181e-05 | 0.9987 | -6.833 | 0.9987 | 1.369e-05 | -4.694 | 8.497e-05 |  |
| wilson_2x3 | 0.9978 | 3.814e-05 | 0.998 | -5.497 | 0.998 | 1.843e-05 | -4.632 | 0.000114 |  |
| wilson_3x3 | 0.9968 | 7.581e-05 | 0.9971 | -3.619 | 0.9971 | 3.513e-05 | -2.59 | 0.01074 |  |
| wilson_3x4 | 0.9958 | 0.0001067 | 0.9962 | -3.561 | 0.9961 | 5.233e-05 | -2.731 | 0.01997 |  |
| wilson_4x4 | 0.9945 | 0.000154 | 0.995 | -3.246 | 0.9949 | 8.199e-05 | -2.382 | 0.02435 |  |
| wilson_4x5 | 0.9933 | 0.0002082 | 0.9939 | -2.676 | 0.9938 | 0.0001264 | -1.843 | 0.1867 |  |
| wilson_5x5 | 0.9919 | 0.0002739 | 0.9925 | -2.285 | 0.9924 | 0.000162 | -1.484 | 0.4056 |  |
| wilson_5x6 | 0.9905 | 0.0003504 | 0.9912 | -1.979 | 0.991 | 0.0002206 | -1.268 | 0.7231 |  |
| wilson_6x6 | 0.989 | 0.0004527 | 0.9897 | -1.57 | 0.9895 | 0.0002696 | -0.9235 | 0.6123 |  |
| wilson_6x7 | 0.9876 | 0.0005549 | 0.9884 | -1.436 | 0.9881 | 0.0003556 | -0.7817 | 0.8269 |  |
| wilson_7x7 | 0.9862 | 0.0006562 | 0.9869 | -1.085 | 0.9865 | 0.0004408 | -0.4456 | 0.9671 |  |
| wilson_7x8 | 0.9848 | 0.0007633 | 0.9855 | -0.92 | 0.9852 | 0.0005209 | -0.3811 | 0.8723 |  |
| wilson_8x8 | 0.9835 | 0.0008349 | 0.9841 | -0.7595 | 0.9837 | 0.0006118 | -0.1951 | 0.9115 |  |
| creutz_2 | 0.0003584 | 1.476e-05 | 0.0003217 | 2.486 |  |  |  |  |  |
| creutz_3 | 0.0003052 | 2.96e-05 | 0.0003009 | 0.1447 |  |  |  |  |  |
| creutz_4 | 0.0002846 | 4.861e-05 | 0.0002696 | 0.3082 |  |  |  |  |  |
| creutz_5 | 0.0002403 | 7.857e-05 | 0.0002279 | 0.1571 |  |  |  |  |  |
| creutz_6 | 0.000125 | 9.862e-05 | 0.0001758 | -0.5158 |  |  |  |  |  |
| creutz_7 | -6.051e-05 | 0.000111 | 0.0001133 | -1.565 |  |  |  |  |  |
| creutz_8 | -1.938e-05 | 0.0001464 | 4.038e-05 | -0.4082 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 1.595e-05 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 6.232e-08 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 0.0001391 | nan | 2 | nan |  |  |  |  | 0.9999 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9997 | 4.048e-06 | 0.9997 | 0.4459 | 0.9997 | 4.084e-06 | 1.002 | 0.3607 |  |
| wilson_1x1 | 0.9997 | 4.048e-06 | 0.9997 | 0.4459 | 0.9997 | 4.084e-06 | 1.002 | 0.3607 |  |
| wilson_1x2 | 0.9993 | 9.267e-06 | 0.9993 | 0.06256 | 0.9993 | 6.854e-06 | 0.3794 | 0.9115 |  |
| wilson_2x2 | 0.9987 | 1.871e-05 | 0.9987 | 0.566 | 0.9987 | 1.369e-05 | 1.672 | 0.3607 |  |
| wilson_2x3 | 0.9981 | 2.875e-05 | 0.998 | 0.08122 | 0.998 | 1.843e-05 | 0.4622 | 0.6679 |  |
| wilson_3x3 | 0.9972 | 4.784e-05 | 0.9971 | 1.192 | 0.9971 | 3.513e-05 | 1.937 | 0.1389 |  |
| wilson_3x4 | 0.9963 | 7.514e-05 | 0.9962 | 0.858 | 0.9961 | 5.233e-05 | 1.309 | 0.215 |  |
| wilson_4x4 | 0.9952 | 0.000121 | 0.995 | 1.171 | 0.9949 | 8.199e-05 | 1.547 | 0.3607 |  |
| wilson_4x5 | 0.9941 | 0.0001846 | 0.9939 | 1.146 | 0.9938 | 0.0001264 | 1.429 | 0.3192 |  |
| wilson_5x5 | 0.9928 | 0.000256 | 0.9925 | 1.168 | 0.9924 | 0.000162 | 1.495 | 0.1389 |  |
| wilson_5x6 | 0.9915 | 0.0003441 | 0.9912 | 0.9749 | 0.991 | 0.0002206 | 1.233 | 0.1867 |  |
| wilson_6x6 | 0.9901 | 0.0004482 | 0.9897 | 0.7509 | 0.9895 | 0.0002696 | 1.072 | 0.3607 |  |
| wilson_6x7 | 0.9887 | 0.0005565 | 0.9884 | 0.6855 | 0.9881 | 0.0003556 | 1.004 | 0.2811 |  |
| wilson_7x7 | 0.9872 | 0.0006698 | 0.9869 | 0.5307 | 0.9865 | 0.0004408 | 0.8916 | 0.3192 |  |
| wilson_7x8 | 0.9859 | 0.0007597 | 0.9855 | 0.5542 | 0.9852 | 0.0005209 | 0.8372 | 0.3607 |  |
| wilson_8x8 | 0.9845 | 0.0008467 | 0.9841 | 0.4111 | 0.9837 | 0.0006118 | 0.7469 | 0.1867 |  |
| creutz_2 | 0.0003105 | 1.267e-05 | 0.0003217 | -0.8879 |  |  |  |  |  |
| creutz_3 | 0.0002378 | 2.585e-05 | 0.0003009 | -2.441 |  |  |  |  |  |
| creutz_4 | 0.0001994 | 4.457e-05 | 0.0002696 | -1.574 |  |  |  |  |  |
| creutz_5 | 0.0002096 | 6.824e-05 | 0.0002279 | -0.2685 |  |  |  |  |  |
| creutz_6 | 0.0002112 | 0.0001034 | 0.0001758 | 0.3417 |  |  |  |  |  |
| creutz_7 | 0.000185 | 0.000154 | 0.0001133 | 0.4657 |  |  |  |  |  |
| creutz_8 | 0.0001808 | 0.0002008 | 4.038e-05 | 0.6995 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 1.595e-05 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 6.232e-08 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 0.0001391 | nan | 2 | nan |  |  |  |  | 0.9999 |

## F_L16_bc500.375_L16_beta2000

HMC: step size 0.0089, 112 leapfrog steps, acceptance seed/hot/cold = 0.988/0.097/0.987. Diffusion-seed batch: 64 chains x 96 trajectories (0.42 s/traj for the whole batch); baselines: 64 chains x 640 trajectories.

![relaxation](L16_beta2000/F_L16_bc500.375_L16_beta2000_relaxation.png)

tau_int (hot-start chains, second half): plaquette = 6.71 +- 1.89, wilson_2x2 = 5.51 +- 1.59, wilson_4x4 = 2.12 +- 0.82, wilson_6x6 = 2.16 +- 0.84. Topology: hot-start HMC L=16 beta=2000 -> **frozen** (no tunneling).

Where 'never' stood at the end: the hot start ended the 640-trajectory budget still at Q^2 at |z| ~ 6; the cold start ended the 640-trajectory budget still at Q^2 at |z| ~ 137575904.

### Diagnostics: raw diffusion output (before any HMC)

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9997 | 3.675e-06 | 0.9998 | -11.22 | 0.9998 | 2.774e-06 | -10.34 | 3.375e-15 |  |
| wilson_1x1 | 0.9997 | 3.675e-06 | 0.9998 | -11.22 | 0.9998 | 2.774e-06 | -10.34 | 3.375e-15 |  |
| wilson_1x2 | 0.9994 | 9.143e-06 | 0.9995 | -6.764 | 0.9995 | 6.327e-06 | -6.886 | 4.394e-08 |  |
| wilson_2x2 | 0.9989 | 2.265e-05 | 0.999 | -4.938 | 0.9991 | 1.203e-05 | -5.982 | 9.613e-06 |  |
| wilson_2x3 | 0.9984 | 3.588e-05 | 0.9985 | -3.984 | 0.9986 | 2.374e-05 | -4.48 | 0.0001523 |  |
| wilson_3x3 | 0.9977 | 6.155e-05 | 0.9978 | -2.679 | 0.9979 | 3.992e-05 | -2.972 | 0.002761 |  |
| wilson_3x4 | 0.9969 | 8.698e-05 | 0.9971 | -2.521 | 0.9972 | 5.907e-05 | -2.733 | 0.005553 |  |
| wilson_4x4 | 0.996 | 0.0001195 | 0.9963 | -2.011 | 0.9963 | 8.615e-05 | -1.875 | 0.05149 |  |
| wilson_4x5 | 0.9951 | 0.000151 | 0.9954 | -1.778 | 0.9955 | 0.0001208 | -1.979 | 0.1389 |  |
| wilson_5x5 | 0.9942 | 0.0001959 | 0.9944 | -1.019 | 0.9945 | 0.0001586 | -1.434 | 0.5044 |  |
| wilson_5x6 | 0.9932 | 0.0002502 | 0.9934 | -0.798 | 0.9937 | 0.0002279 | -1.526 | 0.3607 |  |
| wilson_6x6 | 0.9922 | 0.0003002 | 0.9923 | -0.4279 | 0.9927 | 0.0002657 | -1.252 | 0.9671 |  |
| wilson_6x7 | 0.9912 | 0.0003648 | 0.9913 | -0.2967 | 0.9918 | 0.0003529 | -1.182 | 0.8269 |  |
| wilson_7x7 | 0.99 | 0.0004265 | 0.9901 | -0.2318 | 0.9905 | 0.0004017 | -0.8406 | 0.8723 |  |
| wilson_7x8 | 0.989 | 0.000485 | 0.9891 | -0.1797 | 0.9896 | 0.0004898 | -0.7911 | 0.9115 |  |
| wilson_8x8 | 0.988 | 0.0005645 | 0.9881 | -0.1697 | 0.9885 | 0.0005296 | -0.6826 | 0.8269 |  |
| creutz_2 | 0.0002707 | 1.181e-05 | 0.0002413 | 2.492 |  |  |  |  |  |
| creutz_3 | 0.0002166 | 2.277e-05 | 0.0002256 | -0.3979 |  |  |  |  |  |
| creutz_4 | 0.0001689 | 3.702e-05 | 0.0002022 | -0.9005 |  |  |  |  |  |
| creutz_5 | 7.338e-05 | 5.568e-05 | 0.0001709 | -1.752 |  |  |  |  |  |
| creutz_6 | 6.01e-05 | 7.951e-05 | 0.0001319 | -0.9027 |  |  |  |  |  |
| creutz_7 | 9.593e-05 | 0.0001091 | 8.498e-05 | 0.1003 |  |  |  |  |  |
| creutz_8 | 5.088e-05 | 0.0001417 | 3.028e-05 | 0.1453 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 0.0001376 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 5.374e-07 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 0.001256 | nan | 2 | nan |  |  |  |  | 0.9994 |

### Diagnostics: the same configs after 96 HMC trajectories

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9997 | 2.893e-06 | 0.9998 | -2.13 | 0.9998 | 2.774e-06 | -3.138 | 0.02956 |  |
| wilson_1x1 | 0.9997 | 2.893e-06 | 0.9998 | -2.13 | 0.9998 | 2.774e-06 | -3.138 | 0.02956 |  |
| wilson_1x2 | 0.9995 | 7.683e-06 | 0.9995 | -1.56 | 0.9995 | 6.327e-06 | -2.682 | 0.01326 |  |
| wilson_2x2 | 0.999 | 2.068e-05 | 0.999 | -1.821 | 0.9991 | 1.203e-05 | -3.312 | 0.0006067 |  |
| wilson_2x3 | 0.9985 | 3.961e-05 | 0.9985 | -1.737 | 0.9986 | 2.374e-05 | -2.568 | 0.02956 |  |
| wilson_3x3 | 0.9977 | 7.619e-05 | 0.9978 | -1.16 | 0.9979 | 3.992e-05 | -1.645 | 0.1015 |  |
| wilson_3x4 | 0.997 | 0.0001099 | 0.9971 | -1.173 | 0.9972 | 5.907e-05 | -1.579 | 0.07294 |  |
| wilson_4x4 | 0.9961 | 0.0001623 | 0.9963 | -1.143 | 0.9963 | 8.615e-05 | -1.205 | 0.4535 |  |
| wilson_4x5 | 0.9951 | 0.0002209 | 0.9954 | -1.182 | 0.9955 | 0.0001208 | -1.491 | 0.1389 |  |
| wilson_5x5 | 0.994 | 0.000299 | 0.9944 | -1.181 | 0.9945 | 0.0001586 | -1.521 | 0.3607 |  |
| wilson_5x6 | 0.993 | 0.0003676 | 0.9934 | -1.092 | 0.9937 | 0.0002279 | -1.661 | 0.1614 |  |
| wilson_6x6 | 0.9918 | 0.0004645 | 0.9923 | -1.084 | 0.9927 | 0.0002657 | -1.639 | 0.3607 |  |
| wilson_6x7 | 0.9908 | 0.0005554 | 0.9913 | -0.8681 | 0.9918 | 0.0003529 | -1.48 | 0.1867 |  |
| wilson_7x7 | 0.9895 | 0.0006667 | 0.9901 | -0.9701 | 0.9905 | 0.0004017 | -1.337 | 0.4535 |  |
| wilson_7x8 | 0.9885 | 0.0007764 | 0.9891 | -0.7753 | 0.9896 | 0.0004898 | -1.155 | 0.6679 |  |
| wilson_8x8 | 0.9873 | 0.0008867 | 0.9881 | -0.8345 | 0.9885 | 0.0005296 | -1.135 | 0.6679 |  |
| creutz_2 | 0.0002612 | 9.926e-06 | 0.0002413 | 2.003 |  |  |  |  |  |
| creutz_3 | 0.0002141 | 2.166e-05 | 0.0002256 | -0.5314 |  |  |  |  |  |
| creutz_4 | 0.0002183 | 3.271e-05 | 0.0002022 | 0.4933 |  |  |  |  |  |
| creutz_5 | 0.0001875 | 4.828e-05 | 0.0001709 | 0.3436 |  |  |  |  |  |
| creutz_6 | 0.0001863 | 6.237e-05 | 0.0001319 | 0.8721 |  |  |  |  |  |
| creutz_7 | 0.0002728 | 8.015e-05 | 8.498e-05 | 2.343 |  |  |  |  |  |
| creutz_8 | 0.0002154 | 0.0001182 | 3.028e-05 | 1.566 |  |  |  |  |  |
| Q | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |  |
| Q^2 | 0 | 0 | 0.0001376 | inf | 0 | 0 | 0 | 1 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0 | 0 | 5.374e-07 | inf | 0 | 0 | 0 |  |  |
| Q histogram vs exact P(Q) | 0.001256 | nan | 2 | nan |  |  |  |  | 0.9994 |
