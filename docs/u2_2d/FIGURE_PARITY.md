# Figure parity: u1 main text vs u2

The u1 paper's figure economy (`docs/u1_2d/PAPER_OUTLINE.md`, "Figure economy")
names 13 main-text figures. This table asks, for each, whether u2 has a figure
making the *same* argument — not merely a figure about the same topic.

**The claim both papers carry:** a diffusion-generated configuration is a good
HMC starting seed. u2's emphasis is narrower and stronger than u1's: it targets
the regime where **standard HMC is frozen**, which in 2D U(2) means large beta.
Figures that do not speak to that regime are lower priority here than they were
in u1.

Status key: **OK** = exists and makes the argument. **PARTIAL** = a figure exists
but does not carry the same claim. **GAP** = nothing equivalent.

| # | u1 figure | claim it carries | u2 equivalent | status |
|---|---|---|---|---|
| 1 | `44_pipeline.png` | schematic | — | GAP (cosmetic; draw once for both) |
| 2 | `29_seed_quality.png` **lead** | `t_therm` vs beta, 5 arms, 586x coupling range | `fig21_seed_quality` -- 14 couplings, beta_f 11-1623, SIX arms | **CLOSED 2026-08-21** |
| 3 | `31_frozen_traces.png` | Q traces showing HMC frozen | `fig19_freezing` | OK |
| 4 | `33_ladder_fixed_point.png` | exact <Q^2> is a ladder fixed point | `fig11_ladder_accuracy` | OK |
| 5 | `34_match_rate_volume.png` | raw Q-match rate vs volume | `parity_transport/` data, no figure | PARTIAL |
| 6 | `15_relaxation_high.png` | relaxation from a diffusion seed | `fig06_seed_quality` | OK |
| 7 | `36_sector_tail.png` | sector-tail recovery | `fig20_honest_distributions` (unseeded arms, PRE/POST split) | OK |
| 8 | `13_beta_scan.png` | observable agreement across beta | `fig12_area_law` at 2 couplings | PARTIAL |
| 9 | `38_z_vs_loop_area.png` | std(z) grows with loop area | `fig18_z_vs_loop_area_*` | OK |
| 10 | `28_dissociation.png` | observables sharp, density off | — | GAP |
| 11 | `39_kl_per_site.png` | KL per site across cases | `density_gap/` data, no figure | GAP (data exists) |
| 12 | `40_cost_per_config.png` | s per independent configuration | `fig13_cost` | OK |
| 13 | `30_volume_scan.png` | does the advantage survive volume | — | GAP |

## The three that matter for u2's specific claim

### (a) Lead figure — `t_therm` vs beta. CLOSED 2026-08-21.

`28_crossover_scan.py` + `30_seed_quality_figure.py`. 14 couplings, beta_f = 11
to 1623 (a 148x range), at L_f = 32 lifted from L_c = 16.

**Six arms, not three, and this was the point of running it twice.** Every
coupling is scanned under PLAIN HMC and again under HMC + the marginal odd
winding move, with the same seed so cold and hot starts are PAIRED. Against
plain HMC the seed's advantage is partly that HMC cannot do topology at all --
a weaker and different claim. Against the winding round the comparison is
like-for-like. The figure draws both and lets the paper choose.

Three things had to be ported from u1 rather than reinvented, and each was
load-bearing:

  * `t_therm` on LOCAL observables only (plaquette / W2x2 / W4x4), slowest of
    them, first trajectory whose across-chain |z| vs EXACT holds <= 2 for five
    consecutive records. Topology is excluded ON PURPOSE and tracked separately:
    a chain can be perfectly thermalized locally and never tunnel.
  * The yardstick is `interval` = 2 tau_int, NOT the cold arm. A ratio against a
    cold start flatters the seed everywhere and means nothing.
  * The three REGIMES (`HMC healthy` / `Q frozen` / `HMC dead`), because a
    speed-up only means anything while the baseline still finishes.

**One thing u1 did not have to solve.** u1 takes tau_int from the cold chain's
tail. In the regime u2 targets the cold chain has not equilibrated by the end of
its budget, so that tail is a DRIFT and an autocorrelation time fitted to a
drift is not a decorrelation time. tau_int is a property of the sampler at that
(L, beta), not of the starting configuration, so the equilibrated diffusion-
seeded chain measures the same quantity. The scan computes tau_int for every
arm, prefers the cold chain where it converged with room to spare, and RECORDS
which it used (`interval_source`). At beta_f = 183.6 and 414.9 it has already
had to fall back.

Cost, after two rounds of tuning: ~1 h, not the 3-5 h first estimated. Three
things bought that. (i) The `_cov` retrain left 65 ready-made L = 16 bases in
`data_v2`, so no base generation is needed -- a payoff from an experiment that
was otherwise a regression. (ii) A per-coupling trajectory budget, since
`n_steps` scales as sqrt(beta) and a flat budget puts one round at 4.7 h; u1
sets the precedent by drawing two budget ceilings on its own lead figure.
(iii) **All three arms in ONE batched sampler.** U(2) HMC here is
kernel-launch bound -- 192 chains cost 9.8% more than 64 -- so three sequential
64-chain arms were issuing 3x the launches for arithmetic that rides along free.
Batching is exact: momenta, accept/reject and winding proposals are all
per-chain.

### (b) Frozen traces — CLOSED as fig19.

The data already exists in `seed_benchmark/`: arm B is plain HMC (0 sector
changes, <Q^2> = 0.000), arm D is +even winding (1334 changes, 0 parity flips),
arm G is +marginal odd winding (3557 changes, 2587 parity flips), arm A is the
diffusion seed (0 changes because it starts correct). Drawing the Q traces of
those four is the u2 analogue of `31_frozen_traces.png` and needs no new compute.

### (c) Distribution comparison against a HONEST reference. CLOSED as fig20.

`fig2_sectors_*` and `fig16_*` compare the generated P(Q) against the ensemble in
`data/`, whose sectors are **installed** by `seed_exact_sectors`, not sampled.
Above the parity boundary that ensemble cannot show freezing, so the comparison
proves nothing about topology -- the config comment at the L=64 rung says exactly
this. `06_figures.py` now hatches and relabels that bar.

`26_freezing_arms.py` generates the honest arms: cold start, unseeded, at
`frozen` / `winding` / `winding_odd`. The distribution figures should use those.

## Two limitations to state in the paper rather than paper over

**CORRECTED 2026-08-21 — the density gap is FLAT in beta, and the earlier claim
here was wrong.** This section used to read "the density gap is worst at the
low-beta cases (KL/site 1.11 at 8:3.5:14 rising monotonically)", which is
self-contradictory: 1.11 IS the low-beta case and the series rises from there.
Measured, KL/site is 1.1099 / 1.1172 / 1.1362 / 1.1467 as beta_f goes 14 -> 28
-> 105.7 -> 416.5 — a 3.3% spread over a 30x range, drifting slightly UPWARD.
So the gap is essentially beta-independent and is marginally WORSE in the regime
this study targets, not better (`fig24_kl_per_site`).

Do not argue that the density gap shrinks where the method is used. The
defensible position is the harder one: the gap is real, roughly constant, and
does not bear on the seeding claim, which is graded on observables and on
topology (TRANSPORTED, not modelled) rather than on the density.

**What DOES hold about low beta is the sampling argument, not the density one.**
The coverage retrain's regressions were concentrated at low beta, and at low beta
HMC is *not frozen* --
`15_base_parity.py` measures 4919 parity flips at L=16 beta=14 -- so there is no
sampling problem to solve and no reason to prefer a learned seed. The method is
being asked to help exactly where the classical sampler fails, and it is at large
beta that it does.

**The honest classical baseline is now HMC + the marginal odd move, not plain
HMC.** Before 2026-08-20 the odd move was accepted essentially never, so "the
classical arm cannot reach odd sectors" looked like a property of the theory. It
was a property of the proposal. Any figure that compares the diffusion seed
against plain HMC alone overstates the case; the comparison must include
`winding_odd`, which is genuinely ergodic. What survives is a COST claim -- the
classical arm must manufacture the sectors the seed arrives with -- and that is
weaker but true, which is the trade worth making.
