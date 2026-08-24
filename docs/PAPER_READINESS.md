# Paper readiness assessment (2026-08-24)

Written in answer to three questions: is the project valid, what should the
claim be if freezing-avoidance will not carry it, and is there enough here to
publish. Sources are the repo itself plus `docs/PAPER_REFERENCES.md`.

---

## 1. Verdict, up front

**U(1) is publishable.** Not as "a diffusion sampler for lattice gauge theory"
-- that is taken four times over -- but as the paper `docs/u1_2d/PAPER_OUTLINE.md`
already describes: a **learned prolongator**, scored on trajectories to
equilibrium, with exactness supplied by the HMC chain rather than the model.
Two of its three contributions are solid. The third (contribution 1, the seed's
margin over the classical prolongator) **needs restating** -- see section 3.

**U(2) is not yet publishable as an advantage claim.** It is publishable as a
feasibility-plus-negative result, and Alharazin et al. (arXiv:2602.09045,
PRD 114, 014522) makes that negative result *more* valuable, not less. See
section 5.

**The project's methodology is unusually sound.** Three statistics bugs found
and fixed in one day, an `N_eff` correction that retracted three of its own
claims, a retracted "actionable defect", a verdict-calibration harness. The
self-correction record is better than most published work. What follows is not
a challenge to that; it is the next layer down.

---

## 2. What is valid

Verified by reading the artefacts, not the summaries:

* **The transport identity.** `36_transport_check.py` (100% of fine charges
  equal their coarse charge, configuration by configuration, at two couplings)
  and `45_multi_lift_compounding.py` (100% under 1, 2 and 3 lifts). This is the
  load-bearing claim and it is measured, not asserted.
* **The ladder fixed point.** Exact `<Q^2> ~ V/(4 pi^2 beta)` invariant under
  `(V, beta) -> (4V, 4beta)`; Villain 1.20271 -> 1.20334 over four rungs.
* **The generation-vs-transport ablation** (u1 NARRATIVE 21.6). Raw pre-projection
  output lands in the coarse partner's sector 4.7-29% of the time, falling to
  11.5% at L = 64 and 6.2% at L = 128; raw `<Q^2>/exact` runs to 2.5x, 4.6x,
  5.4x, 2.65x. **This is the paper's thesis, already measured.**
* **The external corroboration.** Zhu et al.'s own published histograms give
  `<Q^2>` 2.36x exact (`46_/47_zhu_*`); Komijani et al. (arXiv:2605.06134) need
  an HMD corrector at large beta in SU(3). Independent, same direction.
* **The division of labour.** Repair factor 64x / 14x / 3.9x / 1.6x / 0.99x
  across W(1x1)..W(8x8), and exactly 0 for Q. Resolved at the first four scales.
* **The sector-distribution ablation** (`out/u2_2d/sector_experiment/`), with an
  honestly weak stated bound after the `N_eff` correction.

---

## 3. What is NOT valid as stated -- one item, and it matters

### Table S6b's classical baseline is not the strongest classical arm

Table S6b concludes: *"the learned map still wins by an order of magnitude...
4-40x over a working competitor."* The competitor is `ape` -- **deterministic**
APE smearing. `u2_2d/scripts/17_prolongator_baseline.py` carries a second arm,
`smear` = `flux` + **heatbath + overrelaxation** sweeps, which u2's own
narrative calls *"the strongest thing available"*. Compact U(1) has exactly the
same exact local updates (`u1_2d.lgt.local_updates.heatbath_sweep`,
`overrelaxation_sweep`) and **u1 never ran that arm**. `docs/PARITY_U1_U2.md`
does not list the prolongator ablation at all, so the gap was untracked.

Measured today (`37_tiling_baseline.py`, new `smear` arm, L = 32, 64 configs,
640 trajectories, same coarse ensemble for both arms):

| beta_f | `ape` (S6b, 2000 traj) | `ape` (today) | **`smear`** | diffusion seed |
|---|---|---|---|---|
| 4.44 | 49 | -- | **0** (5 sweeps) | 8 |
| 14.15 | 149 | 136 | **10** (10 sweeps) | 0 |
| 55.02 | 321 | 252 | **> 640** (10 sweeps) | 0 |
| 218.58 | 150 | *(see run)* | *(see run)* | 7 |

Three things follow, and they do not all point the same way:

1. **At beta_f = 4.44 the classical arm BEATS the seed** -- t_therm 0 in five
   sweeps against the seed's 8. The margin claimed at that coupling (6.1x for
   the model) reverses.
2. **At beta_f = 14.15 the classical baseline was understated by 13.6x**
   (10, not 136). The model still wins, but by "0 against 10", not "0 against
   149".
3. **At beta_f = 55.02 the tuner betrays the arm.** `smear` starts **50x closer
   to exact than `ape`** (2.15e-05 against 1.09e-03) and still reports
   t_therm > 640. Cause: `tune_smear` stops when the *plaquette* crosses exact,
   which is the correct protocol for APE (monotone, overshoots) and the **wrong**
   one for heatbath (an exact sampler, which cannot overshoot -- more sweeps are
   never worse, only costlier). A `--smear-sweeps` flag now runs a fixed
   generous count instead; that rerun is required before any number here is
   quoted.

**This does not sink the paper, but it changes contribution 1 from "an order of
magnitude over the best classical prolongator" to something narrower and more
honest**, and it is exactly the objection a lattice referee raises first:
*why not just run ten heatbath sweeps on a geometric prolongation?*

The defensible answer is u2's, and it is a **matched-budget** answer rather than
a margin: put the diffusion seed through the identical tuning procedure and
compare how much local repair each start needs. u2 does this
(`diffusion_tuned` 5 sweeps against `smear`'s 35 and 15 -- 7x and 3x less
repair). **u1 has no matched-budget arm at all.** That is the single most
important missing experiment and it is listed as T2 below.

### Two smaller items

* **`t_therm` had never been calibrated** (`docs/PARITY_U1_U2.md` item 10, open
  for u1). Measured today, `65_therm_criterion_calibration.py`, 1500 synthetic
  replicas at the deployed 64-chain shape: a **perfectly thermalized** ensemble
  reports t_therm = 0 only **79-85%** of the time, with a 90th percentile of
  **3-4**. So **t_therm <= 3 is the resolution floor** and differences inside it
  are not measurements. Consequences: PAPER_OUTLINE's "median 4 across 35
  couplings" is *at the floor* -- the correct claim is "the seed arrives already
  at equilibrium, within the resolution of the metric", which is stronger and
  cleaner than a number; and the seed's 7 at beta_f = 218.58 is only weakly
  resolved. Power is fine where it matters: a 2-SEM offset gives median 41 and a
  4-SEM offset never converges, so cold starts are separated decisively.
* **`default.yaml` no longer describes the deployed u2 checkpoint** (it has
  grown a `random_rungs` block the deployed net was not trained with). A
  reproducibility hazard for a submission.

---

## 4. What to claim instead of freezing-avoidance

The instinct behind the question is right: freezing-avoidance is where most of
the work went, and it is also the most crowded claim in the field as of 2026.
But **the crowded claim and this project's claim are not the same sentence**,
and the distinction is the paper.

**Do not claim:** "our sampler does not suffer topological freezing."
Albandea et al. (exact winding HMC, cheap), Bonanno et al. (arXiv:2601.20708,
exact SNF, 4D SU(3)), Singha et al. (Q-shift bijection, ESS/N 0.5-0.7 flat in
volume) and Zhu et al. all have some version of this, several of them exactly
and at larger scale. Competing there is competing on their ground and losing.

**Claim instead, in this order:**

### (a) Topology is never sampled at the target coupling at all

This is an *architectural* statement, not a performance one, and nobody else
makes it. The ladder fixed point means the coarse ensemble's P(Q) **is** the
fine theory's P(Q) -- not approximately, identically -- and transport is an
identity verified configuration by configuration through three composed lifts.
So the sector is drawn once, at a coupling where HMC still mixes, and carried
up. **No move at the target coupling ever has to tunnel, because no move at the
target coupling ever touches Q.** Everyone else manufactures a topological move
and pays for it; this pipeline removes the need for one.

That is a claim about *where the ergodicity comes from*, and it is orthogonal to
whether someone else's global move is cheap.

### (b) Generative models manufacture topology, and it is invisible without an exact reference

The negative result, and it now has external support:
* your raw lift over-produces charge 2.5-5.4x at large beta, **degrading with
  volume** (29% -> 11.5% -> 6.2% sector match at L = 32 -> 64 -> 128);
* Zhu et al.'s own published figures give `<Q^2>` 2.36x exact, while their paper
  reports the wider histogram as the success;
* Komijani et al. need an HMD corrector at large beta in SU(3);
* Alharazin et al. validate 2D SU(2) diffusion on the **average plaquette only**
  -- and 2D SU(2) has no topology to get wrong.

**"Width is not correctness, and here is the reference that decides it."** This
is the strongest sentence the project can write, it is supported by three
independent groups' numbers rather than only your own, and §24.3 already
identified it.

### (c) The accuracy the model owes is scale-dependent, and that is why transport is a requirement

The rethermalization tail is a **low-pass repair**: 64x at W(1x1), 1.0x at
W(8x8), and exactly 0x for Q, because retherm runs `topological_updates=False`.
So the model may be wrong in the ultraviolet, must be accurate in the infrared,
and must be **exact** in topology -- which is a *derivation* of the architecture
rather than a description of it. Transport is not a convenience; it is the only
place in the pipeline where nothing downstream can fix an error.

### (d) The cost claim, stated honestly

Do **not** lead with speed. `13_cost_comparison.py` measures the ladder at
3.87x SLOWER than HMC+winding at L = 64 (1.38x faster at 25 sampler steps). The
honest cost statement is the one that survives: the diffusion seed plus the
*cheap even* move reaches full P(Q) coverage in 379 s with zero parity flips,
where the classical arm needs the expensive odd move and 1100 s -- same
endpoint, 2.9x less cost, and every odd sector the seed occupies was inherited
rather than manufactured.

---

## 5. Where U(2) stands

U(2) currently demonstrates **feasibility and a negative**, not an advantage:

* the machinery ports, the `Z_2` monodromy is understood and handled, transport
  is exact in a genuinely non-abelian theory;
* but the capacity retrain came back "TRADE, NOT AN IMPROVEMENT", the ladder is
  slower, and `21_prolongator_observables.py` finds **no measured observable on
  which the learned lift beats a geometric map** at the top rung (extended-loop
  mean |z| 1.54 against `flux`'s 0.13).

**Alharazin et al. changes how to frame this, favourably.** They published 2D
SU(2) diffusion validated on the average plaquette alone. u2's prolongator
ablation is a direct, independent demonstration that *plaquette-level agreement
cannot discriminate the lift at all* -- "local observables do not discriminate",
in its own words. So u2's contribution becomes:

> the first non-abelian gauge diffusion test in a theory where topology exists,
> and a demonstration that the validation standard used in the non-abelian
> diffusion literature is uninformative.

That is a real contribution built out of the negative result, and it needs no
speed or accuracy win. It also gives U(2) a clean reason to exist: **U(2) is the
smallest 2D gauge group that is simultaneously non-abelian and topologically
non-trivial, and its topology is carried entirely by an abelian determinant
sector -- which is what makes exact transport possible at all.**

---

## 5b. Bringing u2 to publishable shape (started 2026-08-24)

Focused on **thermalization and autocorrelation**, which is what the extension
is scored on. Three findings reshaped the plan before any new chain was run.

### The two audits that came from u1, and both land on u2's headline

**(i) `t_therm` has a resolution floor of 3-4.** Calibrated at this study's own
64-chain shape (`out/u2_2d/therm_calibration/`): a *perfectly thermalized*
ensemble reports `t_therm = 0` only 78-85% of the time, 90th percentile 3-4.
NARRATIVE's prolongator claim -- `diffusion_tuned` thermalizing in **0-1
trajectories against `smear`'s 5-6** -- sits almost entirely inside that band.
**That half of the claim is not resolved.**

**(ii) `t_therm` divides by the arm's own spread, so a wrongly-dispersed arm
gets the wrong score.** In u1, against the exact per-configuration sigma, `ape`
is over-dispersed 1.8-5.1x and the geometric maps up to 310x; an inflated
spread inflates the SEM and *shrinks* |z|, so an arm can pass by having error
bars that are too wide. u2 uses the same arms and the same criterion, so the
same audit is required there --  `50_therm_autocorr.py` now reports the
dispersion ratio beside every `t_therm`.

**(iii) The surviving half may not survive either.** With (i) in hand, the
ablation rests on the **tuned sweep count** (5 against 35 and 15, "3-7x less
repair"), which is not a `t_therm`. But `50_therm_autocorr.py` seeds differently
from `17` (`seed` against `seed + 1717`) and is therefore an independent draw --
and at the top rung it returned **`diffusion_tuned` = 15 sweeps, identical to
`smear`'s 15**, where 17 reported 5 against 15. Two structural reasons the count
is fragile: `tune_smear` checks every 5 sweeps, so "5 vs 15" is two check-points
rather than a smooth 3x; and it is a first-passage time on a stochastic
quantity, so it has a heavy right tail by construction.
`52_tuned_sweep_stability.py` re-runs it across seeds (and at `--check-every 1`,
which removes the quantization). **If the ranges overlap, the "3-7x less repair"
claim must be restated as a spread or dropped**, and u2's prolongator ablation
would then support no advantage claim at all -- consistent with
`21_prolongator_observables.py`, which already finds no observable where the
learned lift beats a geometric map.

### RESULT 1 -- the thesis test, and it is the strongest number in either study

`51_transport_ablation.py` + `configs/transport_off.yaml`. Same checkpoint, same
data, same schedule, one switch. Full write-up in
`out/u2_2d/transport_ablation/REPORT.md`.

| rung | L | beta | exact `<Q^2>` | TRANSPORTED | GENERATED | ratio | raw sector match |
|---|---|---|---|---|---|---|---|
| 0 | 32 | 105.651 | 1.0012 | 1.0156 (z +0.32) | 4.2881 (z **+17.67**) | **4.28x** | 0.229 |
| 1 | 64 | 416.524 | 1.0012 | 1.0156 (z +0.32) | 17.0410 (z **+21.16**) | **17.02x** | 0.082 |

* **Charge conjugation is violated at 5.4 sigma** with transport off (+0.28 with
  it on). P(Q) must be exactly even in Q, so this test needs **no closed form**
  and **ports to 4D SU(3)**. It is the answer to "your method depends on exact
  solvability" and is the most transferable line in the study.
* 27 occupied sectors against 7. "Explores a wider range of topological sectors"
  is Zhu et al.'s stated success criterion; against the exact answer it is a 17x
  overshoot.
* The transported `<Q^2>` is **identical to four digits at both rungs** -- the
  same charges carried up -- which is the transport identity visible in the
  table itself.
* Per-lift decomposition: `<d^2> ~ 12` at L = 64 regardless of the coarse input,
  so the ladder's 17.0x is 4.29 inherited + 12.0 from the final lift, against a
  single clean lift's 14.7x. **Compounding is real but modest; the error is
  dominated by the LAST lift**, consistent with `45_multi_lift_compounding.py`.

### RESULT 2 -- stronger guidance cannot replace the projection

`53_consistency_weight_scan.py`, report in
`out/u2_2d/consistency_scan_L32/REPORT.md`. Raising `consistency_weight`
degrades topology MONOTONICALLY (std(dQ) 1.68 -> 9.87, `<Q^2>`/exact 3.7 -> 97
from w = 1 to 30) and collapses into `flux` at w = 30. **w = 1 is optimal, and
optimal for LOCAL physics** (plaquette +4.1e-05, sigma/exact 1.00) -- the
`lambda = 8 sigma^2` Bayesian weight confirmed empirically.

Mechanism, from decomposing the telescope residual (`sum_cells residual =
2 pi (Q_f - Q_c)` exactly): guidance suppresses the INCOHERENT part
(0.1365 -> 0.0452) and leaves the COHERENT part untouched (0.0321 -> 0.0316),
and the coherent part is what moves Q -- `0.0316 x 256 / 2 pi = 1.11` of the
observed std(dQ) = 1.68. **A local reconstruction term cannot reach a global
zero-mode.** That is a structural argument for the projection, not an empirical
one, and it is the form the paper should use.

### RESULT 3 -- the freezing contrast, measured rather than asserted

Same arm, same rung, only the winding move differing (`50_therm_autocorr.py`):

| | tau_int(Q^2) | parity flips | tau_int(plaq) | sigma(tail)/exact |
|---|---|---|---|---|
| no winding | **inf** | **0** | 4.81 | 1.00 |
| winding | 3.78-4.92 | 2358-3142 | 3.24-3.27 | 0.98-0.99 |

A frozen chain now returns `inf` rather than being dropped from the chain
average -- the coding form of the `tau_int(Q^2)`-looks-healthy-on-a-frozen-chain
trap.

### RESULT 4 -- u2's prolongator advantage does NOT survive a matched budget

Measured at BOTH rungs, `50_therm_autocorr.py`, 300 trajectories, 64 chains,
`n_retherm = 0`, with the matched-budget arm present (`diffusion_tuned` = the
learned lift put through the identical `tune_smear` procedure `smear` gets):

| rung | arm | t_therm plaq | tau_int plaq | sigma(t0)/exact | tuned sweeps |
|---|---|---|---|---|---|
| L=32 | diffusion_raw | 6 | 2.70 | 0.95 | -- |
| L=32 | diffusion_tuned | **0** | 2.67 | 0.96 | 15 |
| L=32 | smear | **0** | 2.60 | 0.95 | 15 |
| L=64 | diffusion_raw | 70 | 4.81 | 0.88 | -- |
| L=64 | diffusion_tuned | **0** | 5.27 | 0.98 | 15 |
| L=64 | smear | **0** | 4.96 | 0.88 | 15 |

**Tied on every measure at both volumes.** Three consequences:

* NARRATIVE's "thermalizes in 0-1 trajectories against 5-6" is inside the
  calibrated `t_therm` floor of 3-4 and is not a measurement.
* Its companion, "5 tuned sweeps against 35 and 15", did NOT reproduce: four
  independent invocations at the top rung all returned **15 for BOTH arms**.
* `tau_int` cannot discriminate starting points at all -- it is a property of
  the sampler, identical to ~1% across every arm including `cold`. Any seeding
  claim must rest on `t_therm`, which has the floor above.

**A dispersion edge was floated and then withdrawn.** At L = 64 the learned arm
sat at `sigma(t0)/exact = 0.98` against `smear`'s 0.88, which looked like a real
advantage on a quantity `t_therm` cannot see. It does not survive: the SAME
`smear` arm reads 1.03 in the winding round (a 17% seed spread that brackets
0.98), and at L = 32 all three arms read 0.95-0.96. Withdrawn.

**What this means for the claim.** In PURE GAUGE theory an exact, cheap local
heatbath exists, so a learned prolongator faces a very high bar: `flux` is
exactly blocking-consistent (it inherits Q for free, with no network and no
projection) and heatbath sweeps equilibrate it. u2 cannot demonstrate an
advantage over that, and should not claim one. The regime where a learned map
must win is where local updates are NOT cheap -- dynamical fermions -- which
this study does not cover.

**The one place a properly-tuned classical arm actually FAILS** is u1 at
`beta_f = 218.58`: `smear` with 285 tuned sweeps does not thermalize within 640
trajectories (and sits 9.4 sigma from exact on the plaquette against the exact
per-configuration sigma), while the diffusion seed needs 7. If that survives a
fixed 200-sweep re-run, it is the whole positive claim: **the learned map earns
its place exactly where cheap local repair stops working.** If it does not
survive, neither study demonstrates a prolongator advantage anywhere, and the
paper is the transport result plus the baseline-construction service.

### RESULT 5 -- THE POSITIVE CLAIM, and it survives the strongest classical arm

u1, L = 32, 640 trajectories, 64 configurations. `smear` = `flux` + heatbath and
overrelaxation sweeps, run at a FIXED 200 sweeps (20x what the greedy
plaquette tuner used), so this is not a tuning artifact:

| beta_f | smear: plaquette | smear: W2x2 | smear: W4x4 | diffusion seed (slowest) |
|---|---|---|---|---|
| 14.15 | 0 | 8 | 10 | 0 |
| 55.02 | 44 | **> 640** | **> 640** | **0** |
| 218.58 | **> 640** | **> 640** | **> 640** | **6** |

**The strongest classical prolongator in this theory fails at beta >= 55, and it
fails in the INFRARED.** It fixes the plaquette and never reaches W(2x2) or
larger. The diffusion seed arrives already equilibrated at every scale.

`ape` behaves oppositely -- 39-42 at the plaquette but it DOES reach the loops
(148-252), because staple blending propagates over ~n_iter sites while heatbath
at stiff coupling barely moves. **The diffusion seed is the only arm correct at
both scales at once.**

**The mechanism is the project's own division-of-labour result, and three
independent measurements now agree:**

* the retherm repair factor falls 64x / 14x / 3.9x / 1.6x / 0.99x from W(1x1) to
  W(8x8) and is exactly 0 for Q (`59_pre_post_retherm.py`);
* u2's `diffusion_raw` has t_therm 70 at the plaquette and **0** at W(4x4) and
  W(8x8) -- the raw lift is already right in the infrared;
* `smear` has t_therm 0-44 at the plaquette and **> 640** beyond it.

Local updates are a LOW-PASS repair. What the model supplies is exactly what
they cannot.

**So the claim to publish is not "faster".** It is:

> A learned prolongator supplies long-wavelength structure that cheap exact
> local updates cannot, and at stiff coupling that is the difference between an
> ensemble that equilibrates and one that does not.

This also reframes RESULT 4 correctly rather than apologetically: at u2's
couplings local repair is still sufficient, so no advantage is visible there.
The advantage appears where repair fails.

**Caveat that must travel with it:** in PURE GAUGE theory a cheap exact local
heatbath exists, which is why the advantage only appears at stiff coupling. The
regime where a learned map must win generally is where local updates are not
cheap -- dynamical fermions -- and neither study covers that. Two follow-ups, in
order of cost: (i) an action with NO exact heatbath (Symanzik/rectangle, forcing
Metropolis) as a cheap proxy, testable in days; (ii) dynamical fermions in 2D
U(2), where at L <= 32 `det D` is a ~2048x2048 LU and needs no pseudofermions --
the right experiment, but a separate project.

### RESULT 6 -- two negatives from 2026-08-24 that must be recorded

**(a) The "exact local sampler" proxy came back NEGATIVE, and the experiment was
mis-sold when proposed.** `smear_mh` is `smear` with the exact heatbath replaced
by Metropolis -- same action, same references, same overrelaxation, 200 sweeps
each. At beta_f = 14.1464:

| arm | local move | t_therm |
|---|---|---|
| `smear` | exact heatbath | 19 |
| `smear_mh` | Metropolis | **0** |

Metropolis is if anything better. So the classical arm's mid-beta advantage does
NOT depend on having an exact local sampler.

**And the proxy answers a narrower question than it was proposed as answering.**
It was pitched as a cheap stand-in for dynamical fermions. It is not: heatbath
and Metropolis are both LOCAL moves reading a local plaquette weight, whereas a
fermion determinant is NON-LOCAL and admits no local update at all. The proxy
tests EXACTNESS of the local sampler; the fermion question is LOCALITY of the
action. The honest conclusion is that exactness is not what makes `smear`
strong, and testing the locality claim needs the real fermion implementation.

**(b) The tuned sweep count is noise.** `52_tuned_sweep_stability.py`,
L = 64, one lift per seed:

**FINAL, 5 seeds** (`out/u2_2d/tuned_sweep_stability/`):

| arm | counts | median | min-max |
|---|---|---|---|
| diffusion_tuned | [15, 35, 10, 5, 10] | **10** | **5-35** |
| smear | [35, 15, 20, 15, 15] | **15** | **15-35** |

Ratios by seed: 2.33, **0.43**, 2.00, 3.00, 1.50. The ranges overlap almost
entirely and one seed runs backwards. The defensible statement is a median
**1.5x with overlapping ranges** -- not "7x and 3x less repair". `tune_smear` is a first-passage time on a
stochastic quantity, quantized to multiples of `check_every = 5`, so it has a
heavy right tail by construction. **NARRATIVE's "5 tuned sweeps against 35 and
15 -- 7x and 3x less repair" is not supported**, and the contrary reading
recorded earlier on 2026-08-24 ("four consecutive observations of 15 vs 15") was
equally worthless, since those four shared one RNG stream rather than being four
seeds. Neither direction was evidence. Quote a median and range from this script
or drop the claim.

### RESULT 7 -- the beta boundary, both classical arms at their strongest

`37_tiling_baseline.py`, L = 32, 64 configurations, `smear` at a FIXED 200
sweeps. Seed column from the 34-coupling scan already in
`out/u1_2d/thermalization/`.

| beta_f | ape | smear | **diffusion seed** |
|---|---|---|---|
| 14.15 | 136 | 10-19 | **0** |
| 55.02 | 301 | **> 500** | **0** |
| 78.46 | **> 500** | **> 500** | **11** |
| 118.47 | **> 500** | **> 500** | **1** |
| 218.58 | 148 | **> 640** | **6** |
| 398.49 | -- | -- | **1** |
| 872.82 | -- | -- | **3** |

**THIS TABLE IS SUPERSEDED -- `smear` IS NOT THE STRONGEST CLASSICAL ARM.**
See RESULT 8. It was built on the assumption that an exact local sampler
(heatbath) must dominate a random-walk one (Metropolis). That assumption is
false at stiff coupling, and the `smear_mh` arm added for the fermion proxy
beats it decisively. The beta boundary must be re-measured against `smear_mh`;
a re-run is in `out/u1_2d/smear_mh_beta_scan/`.

**Also note `ape` is RUGGED in beta, not monotone**: 301 at beta = 55, > 500 at
78 and 118, then **429** at 178. That is the known t_therm ruggedness
(`PARITY_U1_U2.md` item 6: 59 / 51 / 6 / 50 at adjacent couplings). **Do not
quote a sharp boundary from single t_therm points** -- report the trend across
the scan.

### RESULT 8 -- THE STRONGEST CLASSICAL ARM USES METROPOLIS, NOT HEATBATH

Found 2026-08-24 by accident: the `smear_mh` arm was built as a
dynamical-fermion proxy (RESULT 6a), and it inverted the baseline instead.
Identical in every respect to `smear` -- same `flux` start, same 200 sweeps,
same two overrelaxations, same action, same references -- differing only in the
ergodic move:

| beta_f | `smear` (heatbath) | **`smear_mh` (Metropolis)** | diffusion seed |
|---|---|---|---|
| 14.15 | 19 | **0** | 0 |
| 55.02 | **> 640** | **24** | 0 |
| 218.58 | **> 640** | **0** | 6 |

And the dispersion audit (`out/u1_2d/dispersion_mh/`) says the Metropolis arm is
not merely passing a metric -- it is genuinely an excellent configuration:

| beta_f | arm | rel err | std/exact sigma | \|z\| vs EXACT sigma | build |
|---|---|---|---|---|---|
| 218.58 | `smear` | -1.32e-04 | 2.08 | 10.41 | 41.6 s |
| 218.58 | **`smear_mh`** | **-8.7e-07** | **0.92** | **0.07** | **4.2 s** |

Correct in the mean to **0.07 sigma**, correct in width to 8%, thermalizes
instantly at the stiffest coupling, and **10x cheaper to build** than the
heatbath arm.

**IT IS NOT A SAMPLER BUG.** `heatbath_sweep` draws from
`torch.distributions.VonMises`, and high concentration is where rejection
samplers get fragile, so it was checked: `E[cos theta]` matches
`I1(k)/I0(k)` to ~1e-6 at every concentration from k = 50 to 4000, and the
standard deviation matches `1/sqrt(k)` to 0.1%. Both arms are correct samplers;
they differ in RELAXATION RATE from a `flux` start, which is an algorithmic
property, not a correctness one. The mechanism is not established -- plausibly
heatbath's sharply-peaked conditional at stiff coupling reproduces the local
weight while leaving the smooth long-wavelength structure `flux` handed it,
where a diffusive random walk moves collective modes -- but that is a hypothesis
and is NOT measured.

**THE CONSEQUENCE FOR THE PAPER: there is no demonstrated LOCAL-observable
advantage for the learned prolongator.** u2 ties at both volumes (RESULT 4);
u1's apparent win at stiff coupling does not survive `smear_mh`, which beats the
diffusion seed outright at beta = 218.58 on `t_therm`.

**READ RESULT 9 BEFORE ACTING ON THIS.** `t_therm` scores local observables
only, and on topology every classical arm collapses. The comparison above is
real but partial.

### RESULT 9 -- THE CLASSICAL PROLONGATORS HAVE NO TOPOLOGY, AND THAT IS THE PAPER

`u1_2d/scripts/67_prolongator_topology.py` (new, 2026-08-24),
`out/u1_2d/prolongator_topology/`. `<Q^2>` divided by the exact value from the
character expansion, 64 configurations, 200 sweeps for the repaired arms:

| beta_f | tile | halve | flux | ape | smear (heatbath) | **smear_mh** | **diffusion** |
|---|---|---|---|---|---|---|---|
| 14.15 | 14.44 | 0.00 | 0.00 | 0.07 | 3.14 | **0.09** | **1.00** |
| 55.02 | 11.60 | 0.00 | 0.00 | 0.00 | 9.03 | **0.00** | **1.00** |
| 218.58 | 25.85 | 0.00 | 0.00 | 0.00 | **217.05** | **0.00** | **1.00** |

**Every classical arm is wrong by a factor between 0 and 217.** `smear_mh` --
the arm that beats the diffusion seed on `t_therm`, sits 0.07 sigma from the
exact plaquette and has correct per-configuration dispersion -- produces
**identically zero topological charge** at beta >= 55. The classical
prolongator REINTRODUCES the freezing the method exists to remove. The diffusion
pipeline is 1.00 by construction because Q is TRANSPORTED, not produced by the
map, and that transport is verified configuration-by-configuration.

**The error this corrects.** It was argued repeatedly on 2026-08-24 that `flux`
is blocking-consistent and therefore "carries Q_coarse for free": spreading a
coarse plaquette over four fine ones should give each `Theta/4 < pi/4`, so
nothing wraps and the telescope holds. Measured, `flux`'s fine plaquettes reach
**2.99 rad** and the cell sum misses its coarse plaquette by up to **4 pi**. It
is consistent at the LINK level while its PLAQUETTES wrap, which sets Q to zero
in every configuration. The telescope was reasoned about instead of measured --
on the same day that lesson was being applied to everything else.

**So the arms divide cleanly, on exactly the axis this study is about:**

| | classical prolongation + local repair | learned lift + transport |
|---|---|---|
| local observables | **excellent** (0.07 sigma, correct dispersion) | good, not better |
| cost | **10x cheaper** | one forward pass |
| **topology** | **0.00x to 217x wrong** | **exact** |

This is the study's own "observable-level agreement does not certify the
measure" result, now turned on the CLASSICAL baselines rather than on
generative ones -- and it is a stronger statement than the version aimed at Zhu
et al., because these arms are not merely imprecise, they are topologically
trivial.

**RESULTS 7 and 8 are superseded as conclusions** (their measurements stand):
they scored `t_therm`, which never looks at topology.

**Why the intuition failed.** Heatbath samples each link exactly from its
conditional given the staples. At stiff coupling that conditional is very
sharply peaked, so heatbath reproduces the LOCAL weight faithfully while barely
moving -- it locks in whatever long-wavelength structure `flux` handed it.
Random-walk Metropolis at width `1/sqrt(2 beta + 1)` is diffusive and moves
collective modes over many sweeps. Exactness of the local sampler and mixing of
the infrared are different properties, and only the second one matters here.
That is the same UV/IR split as everywhere else in this study, arriving from a
third direction.

**Consequences.**
* Every "the classical arm fails" claim must be re-checked against `smear_mh`.
* RESULT 6a's negative stands but reads differently: Metropolis is not a
  DEGRADED stand-in for heatbath, it is BETTER, so it was never a fermion proxy
  at all.
* **The general lesson: "strongest baseline" is an empirical claim, not a
  theoretical one.** `smear` was introduced on 2026-08-24 precisely because
  `ape` was not the strongest arm; the same error was then repeated one level
  down.

### New scripts and runs

| what | script | status |
|---|---|---|
| t_therm floor at u2 shapes | `u1_2d/scripts/65_therm_criterion_calibration.py` | **done**, `out/u2_2d/therm_calibration/` |
| t_therm + tau_int + dispersion, per arm | `u2_2d/scripts/50_therm_autocorr.py` | **running**, 3 rounds |
| transport vs generation (the thesis) | `u2_2d/scripts/51_transport_ablation.py` + `configs/transport_off.yaml` | **ladder running** |
| tuned-sweep seed stability | `u2_2d/scripts/52_tuned_sweep_stability.py` | queued (GPU) |

The three `50_` rounds are: top rung with the marginal odd winding move (the
honest classical baseline), rung 0 with it, and the top rung *without* it so the
freezing contrast is measured rather than asserted. 2000 trajectories, 64
chains, `n_retherm = 0` -- the ladder's ten rethermalization sweeps saturate
`t_therm` at 0 for every arm and destroy the comparison's resolution, a trap
`17`'s own docstring records.

`tau_int` is reported per observable and for `Q^2`, with **parity flips counted
beside it**, because CLAUDE.md establishes that `tau_int(Q^2)` reports *healthy*
on a parity-frozen chain -- the joint move shuffles Q by +-2 inside one parity
class, so a small `tau_int(Q^2)` with zero flips is a frozen chain, not a fast
one. A chain whose `Q^2` never moves now returns `inf` rather than being
silently dropped from the average, which is the coding form of the same trap.

## 6. Tests

### Done today

* **T0 -- the missing classical arm** (`37_tiling_baseline.py`, new `smear` arm,
  `--arms`, `--smear-sweeps`; also fixes a latent crash in the
  no-cached-base path, which the 2026-08-18 prune had made reachable).
  Result in section 3. **Changes what contribution 1 may claim.**
* **T1 -- `t_therm` calibration** (`65_therm_criterion_calibration.py`, new).
  Closes `PARITY_U1_U2.md` item 10 for u1. Resolution floor is t_therm ~ 3-4.

### Required before submission, in priority order

* **T2 -- the matched-budget prolongator comparison in u1.** Put the diffusion
  seed through the identical `tune_smear`/`fixed_smear` procedure `smear` gets
  and compare **sweeps of local repair needed**, as u2 does. This is the
  experiment that answers "why not just run heatbath sweeps", and u1 -- the
  paper being written first -- does not have it. Needs the raw diffusion seeds
  regenerated at the S6b couplings (they are not cached; only the hot/cold
  baselines are).
* **T3 -- rerun `smear` at a fixed generous sweep count** at all five S6b
  couplings and rebuild Table S6b with both classical arms. The tuned numbers
  above understate the arm at beta_f = 55.02.
* **T4 -- the transport-off A/B in u2.** `enforce_coarse_charge` is already a
  config flag and no run has ever set it false. u1 has this ablation (21.6);
  u2, the non-abelian setting that is the novelty, does not. One config change.
* **T5 -- charge every arm in one cost currency** (link touches, as
  `44_/61_sweeps_vs_trajectories.py` already do) including the model's own
  forward passes and the coarse ensemble. Any prolongator comparison that
  charges the classical arm for its sweeps and not the model for its 200
  reverse-diffusion steps is not a comparison.
* **T6 -- settle `odd_z = +2.61`** at L = 16, beta = 28 with 5-10x statistics.
  Low paper value; nothing downstream depends on it. Do it last or scope it out.

### Explicitly worth NOT doing

* Re-opening PTBC, retraining a Villain checkpoint, or widening coverage again
  without raising capacity -- all closed with converged negatives.
* `physics_blend_coef` -- measured dead end.
* Chasing a speed claim. The cost measurement is what it is; frame around
  reachability and correctness instead.

---

## 7. So: enough to publish?

**Yes for U(1), conditional on T2 and T3.** The paper is
`docs/u1_2d/PAPER_OUTLINE.md`'s reframing, with contribution 1 restated around
matched-budget local repair instead of a raw t_therm margin, and with the
falsification program (contributions 2-3) carrying the weight. The transport
identity, the density-gap measurement, the division-of-labour decomposition and
the Zhu head-to-head are all done, all resolved, and all novel enough.

**Yes for U(2) as an extension**, framed as feasibility + the validation-standard
negative, not as an advantage.

The thing that would most improve the paper's standing is not another
experiment. It is that **the two strongest results are both negatives** -- the
density gap and the manufactured-topology finding -- and the field has just
handed you two independent confirmations of the second (Zhu's own numbers,
Komijani's corrector). Lead with that.
