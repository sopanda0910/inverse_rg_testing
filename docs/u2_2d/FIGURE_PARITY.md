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
| 1 | `44_pipeline.png` | schematic | **`fig28_pipeline`** | **CLOSED 2026-08-21** -- `41_pipeline_schematic.py`, drawn once for BOTH studies (the SU(2) box is dashed and labelled `u2 only`). Makes three things visual that a reader would otherwise reconstruct from prose: where P(Q) is sampled, that the charge branch runs AROUND the network, and that exactness lives in the HMC tail. |
| 2 | `29_seed_quality.png` **lead** | `t_therm` vs beta, 5 arms, 586x coupling range | `fig21_seed_quality` -- 14 couplings, beta_f 11-1623, SIX arms | **CLOSED 2026-08-21** |
| 3 | `31_frozen_traces.png` | Q traces showing HMC frozen | `fig19_freezing` | OK |
| 4 | `33_ladder_fixed_point.png` | exact <Q^2> is a ladder fixed point | `fig11_ladder_accuracy` | OK |
| 5 | `34_match_rate_volume.png` | raw Q-match rate vs volume | **`fig26_transport_exactness`** | **CLOSED 2026-08-21 -- and stronger than u1's: 100% CONFIG BY CONFIG at 10 couplings, both volumes, model beta 5.97-327** |
| 6 | `15_relaxation_high.png` | relaxation from a diffusion seed | `fig06_seed_quality` | OK |
| 7 | `36_sector_tail.png` | sector-tail recovery | `fig20_honest_distributions` (unseeded arms, PRE/POST split) | OK |
| 8 | `13_beta_scan.png` | observable agreement across beta | **`fig29_observable_scan`** | **CLOSED 2026-08-21** -- `43_observable_scan.py`, 12 couplings, raw lift and after 10 retherm sweeps, against the closed form. Shows the coverage story on OBSERVABLES rather than inferred from a thermalization count. |
| 9 | `38_z_vs_loop_area.png` | std(z) grows with loop area | `fig18_z_vs_loop_area_*` | OK |
| 10 | `28_dissociation.png` | observables sharp, density off | `fig23_dissociation` | **CLOSED 2026-08-21** |
| 11 | `39_kl_per_site.png` | KL per site across cases | `fig24_kl_per_site` | **CLOSED 2026-08-21** |
| 12 | `40_cost_per_config.png` | s per independent configuration | `fig13_cost` | OK |
| 13 | `30_volume_scan.png` | does the advantage survive volume | **`fig27_volume_scan`** | **CLOSED 2026-08-21.** Data complete 2026-08-21; needs one appendix panel. The result to draw: coverage ORDERING transfers, but at model beta ~45 and the same gap `t_therm` is 6 at L=32 and `inf` at L=64. |

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


---

## Publication readiness, 2026-08-21

Assessed against `docs/u1_2d/PAPER_OUTLINE.md` section 8, which now carries the
u2 material as a five-figure section of the U(1) paper.

**Main-text five, all existing and all regenerable from tracked scripts:**
`fig07_topological_reach` (strongest panel), `fig06_seed_quality` (lead),
`fig09_parity_mobility`, `fig13_cost`, `fig26_transport_exactness` (new).

**Required edits, both DONE 2026-08-21:**
* `fig21_seed_quality` now marks its IN-SAMPLE coupling (`beta_f = 414.90`, whose
  fine side is the `L=32 beta=416.524` training rung). `30_seed_quality_figure.py`
  gained `TRAIN_RUNGS` and `in_sample()` for this. Anything marked must be
  excluded from a coverage-vs-quality correlation.
* `fig26` created from `36_transport_check.py` + `37_transport_figure.py`.

**RESOLVED 2026-08-21, and it is a RETRACTION.** `fig22_division_of_labour`
was held back because its companion analysis reported rethermalization making
W(8x8) four times worse at L=64, beta=416.5 while `33_retherm_scan.py` found the
same loop IMPROVING 2.3x across the same ten sweeps. `42_retherm_reconcile.py`
measured both statistics on the SAME configurations and the answer is that
NEITHER WAS EVER RESOLVED: sigma at W(8x8) is 19500 ppm, so 256 configurations
give a standard error of 1219 ppm, and the two disputed numbers are 378 ppm
(z = 0.31) and 1581 ppm (z = 1.30). Both scripts are arithmetically right and
neither result exists. The metric-artefact hypothesis is refuted directly --
sigma moves only x0.93 across the tail, far too little to carry a 4x
disagreement. Full write-up: `out/u2_2d/retherm_reconcile/RECONCILIATION.md`.

Consequences:

* **The "ACTIONABLE DEFECT" (post-retherm `N* = 137` at W(8x8) against a
  256-configuration ensemble) is WITHDRAWN.** `N* = (sigma/bias)^2` on a bias
  consistent with zero is unbounded. No basis for retuning `n_retherm`.
* **`fig22` MAY enter the paper**, with panels restricted to the scales that
  are resolved. W(1x1) is z = 18.6 raw and W(2x2) is z = 3.2, and ten sweeps
  remove both; W(4x4) and larger are already indistinguishable from exact at
  256 configurations RAW, so the figure must say so rather than plot a trend
  through them.
* The flatness claim (62 / 67 / 69 ppm across three scales) stands on two
  resolved points plus a consistent 2-sigma bound of ~290 ppm at the third.

**ALL THIRTEEN PARITY ITEMS ARE NOW CLOSED (2026-08-21).** #1 with
`fig28_pipeline`, #5 with `fig26_transport_exactness`, #8 with
`fig29_observable_scan`, #10/#11 with `fig23`/`fig24`, #13 with
`fig27_volume_scan`. Parity #13 closed with `fig27_volume_scan`
(`38_volume_figure.py`), which is the two-sided answer: the coverage ORDERING
transfers -- best point stays best, past-the-rung stays dead -- while quality
degrades with volume at fixed coverage, catastrophically at model beta ~45
(t_therm 6 at L=32, never at L=64).
