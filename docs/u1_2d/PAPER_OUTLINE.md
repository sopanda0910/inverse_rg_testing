# Paper Outline — Learned Prolongation for 2D Compact U(1)

**Reframed 2026-08-19.** The previous outline was built around two claims: a
diffusion sampler validated on observables, and a demonstration that observable
validation does not certify the measure. That framing put the model forward as a
*standalone sampler* and treated the density gap as a negative result about it.

This version states the claim the project actually establishes: **the diffusion
model is a learned prolongator — it produces HMC starting configurations, and
exactness comes from the HMC chain, not from the model.** The density gap stops
being a failure and becomes a *specification*: it says precisely how much work
the rethermalization tail is being asked to do.

The previous outline is recoverable with
`git show HEAD:docs/PAPER_OUTLINE.md`. Figure references in `[brackets]` are
existing files in `out/u1_2d/paper_appendix/figures/`; `[NEW]` marks a panel that
must be assembled (all from data already in `out/u1_2d/`, except where flagged).

> **Status, 2026-08-20: every `[NEW]` panel below now exists** as figures 31-45,
> each produced by a tracked script and covered by
> `30_assemble_appendix_figures.py --check`. Each has a caption section in the
> figure roster of `out/u1_2d/paper_appendix/appendix.md`. Three things moved in
> the process and are flagged inline where they appear: **§5.2's std(z) growth**
> and **§6.1's cost row** were both superseded, and **§4.3's tail-vs-volume
> panel is the one figure still not drawn**, because its run directory was
> pruned.

**Suggested title framing:** the deliverable is a starting configuration, not an
ensemble. Something like *"Learned prolongation for lattice gauge theory:
diffusion-generated starting configurations that thermalize in O(1)
trajectories."*

**What this reframing buys, and it is substantial:**

1. **The correctness claim becomes clean.** Exactness is supplied by HMC, which
   is exact by detailed balance regardless of where it starts. Nothing rests on
   the model's density. The awkward "asymptotically exact only in the
   retherm → ∞ limit" hedge disappears, because a finite tail from a good start
   is the whole method rather than an approximation to it.
2. **The priority problem largely dissolves.** Zhu et al. do standalone
   diffusion sampling for this theory with a MALA exactness claim; Bauer et al.
   do coarse→fine flows. Neither asks *how good a starting configuration is
   this, measured in trajectories to equilibrium, against the classical
   prolongator that is the incumbent*. §23.2 records that comparison as the
   most important omitted one, and Table S6b now runs it.
3. **The strongest table in the study moves to the front.** Table S6b is
   currently appendix C.

---

## 1. Introduction

- Critical slowing down and topological freezing as the cost wall. The specific
  failure: at large β, generating a *thermalized* configuration is what costs,
  and cold/hot starts stop converging entirely.
- **The incumbent remedy is classical multiscale thermalization** (Endres,
  Brower, Detmold, Orginos, Pochinsky, PRD 92, 114516) — RG-matched coarse
  action, equilibrate cheaply at the coarse level, **prolongate to fine**,
  **rethermalize in parallel**. Their prolongator is a geometric map plus
  smearing, and it preserves topological charge per configuration. Detmold and
  Endres conjecture the rethermalization cost *vanishes* toward the continuum.
- **The gap this paper addresses:** the prolongator has never been learned, and
  the learned coarse→fine literature (inverse-RG upscaling, RG-inspired flows,
  diffusion for gauge theory) has never been scored on the quantity that
  actually matters for this use — trajectories to equilibrium.
- Contributions, three:
  1. **A learned prolongator whose output thermalizes in 0–25 HMC trajectories**
     (median 4) across 35 couplings spanning β = 1.49 → 872.8 at L = 32 — a
     cost **flat in β** — against 49–321 for the best classical prolongator
     (Endres-style APE smearing, per-β tuned), 11 → 575 → never for a fresh
     cold start, and never above β ≈ 9.6 for a hot start. Across volume the
     advantage persists but narrows (168× → 17.6× over a 16× volume range,
     §4.4), and the paper should say so.
  2. **A direct measurement of how far the seed is from equilibrium** — KL in
     nats/site via the exact free energy — which specifies what the tail must
     fix and shows the seed is emphatically *not* the Boltzmann distribution
     despite four-significant-figure agreement on observables.
  3. **Sector transport as an identity, not an approximation.** The ladder
     fixed point ⟨Q²⟩ ≈ V/(4π²β) under (V, β) → (4V, 4β) means the seed
     inherits its P(Q) from a coupling where HMC still mixes, so the tail never
     has to tunnel. Measured: the sector tail is ≤ 150 trajectories and *falls*
     with volume.
- One paragraph, up front, stating what the correctness claim attaches to:
  **the HMC chain started from the seed, not the model's output.** The model is
  an initializer with no accept/reject and no exactness claim of its own.

**Figures:**
- `[EXISTS] Fig 44` — `44_pipeline.png`, the pipeline schematic: coarse HMC →
  diffusion prolongation → sector transport → HMC tail → measurement, with the β
  ladder as the outer loop and the exact arrows drawn solid against the single
  dashed learned one.

---

## 2. Setup: the theory and why it is the right testbed

### 2.1 2D compact U(1) on the lattice
Link angles, Wilson action, plaquette convention, gauge invariance, topological
charge as the wrapped-plaquette winding number.

### 2.2 Exact solvability
Character expansion gives exact ⟨plaquette⟩, Wilson loops, free energy, and the
finite-volume P(Q). Emphasize early: this is what lets the paper *measure* seed
quality against truth instead of against another simulation.

### 2.3 The failure mode being targeted
Topological freezing of periodic HMC, and — the point the previous outline
under-stated — that the binding constraint in the headline regime is **UV
thermalization**, not topology. Table S1 records instanton-HMC ⟨Q²⟩ as correct
in *every* row; what fails is reaching equilibrium.

**Figures:**
- `[EXISTS] Fig 31` — `31_frozen_traces.png`, Q(t) for plain HMC at
  β = 14.1 / 55.0 / 218.6, L = 32: 0 sector changes in 3000 trajectories at all
  three, against the winding arm's 8447 / 5092 / 358. Data:
  `out/u1_2d/classical_arms/` (2026-08-20 re-run — see the §6.1 note).
- `[EXISTS] Fig 32` — `32_burnin_wall.png`, plaquette relaxation from cold, hot
  and seeded starts at the same three couplings, showing the burn-in wall.

---

## 3. Method

### 3.1 Blocking, the ladder, and the fixed-point invariant
2×2 blocking, tree-level β_c = β_f/4 refined by the exact character-convolution
MLE (13.1% correction at the bottom rung — not a rounding detail). State the
ladder invariant explicitly: exact ⟨Q²⟩ is a **fixed point** (1.20271 → 1.20334
→ 1.20334 → 1.20334 over four rungs, Villain). This is why the seed lands in
the right sector, and it deserves its own subsection.

- `[EXISTS] Fig 33` — `33_ladder_fixed_point.png`, the ⟨Q²⟩ ladder fixed point
  across five rungs, Villain beside the campaign's own Wilson ladder.

### 3.2 Diffusion on the torus of angles
Exact heat kernel on the circle; denoising score matching. Note the forward
kernel's exactness is special to U(1) and unavailable non-abelian — this
matters for §7 but no longer threatens the correctness claim, since correctness
never came from the model's density.

### 3.3 Gauge-covariant score network
Curl-head parameterization, complete rather than merely contained; conditioning
on coarse invariants; β and σ through FiLM, which is what lets one checkpoint
serve the whole ladder and extrapolate 15× in coupling.

- `[EXISTS] Fig 45` — `45_architecture.png`, the architecture diagram, curl
  head highlighted, drawn from the deployed checkpoint's own `model_kwargs`.

### 3.4 Topology transport
The three mechanisms — coarse-charge enforcement via the instanton shift,
blocking-consistency guidance with the derived width λ(σ) = 8σ², and
rethermalization under the no-topological-moves honesty convention.

Make the structural argument here: a local score with a finite receptive field
cannot control a global integer, and the degradation is quantitative. Under the
seed framing this is *not* a deficiency — the sector is supplied by the ladder
identity and the model is not asked for it.

- `[EXISTS] Fig 34` — `34_match_rate_volume.png`, raw (projection-off) Q-match
  rate vs volume: 0.484 (L=16), 0.234 (L=32), 0.094 (L=64), halving per 4×
  volume. The L=128 value of 0.062 quoted in §21.6 has no surviving run
  directory and is **not** on the figure; quote it from the narrative or drop it.
- `[EXISTS] Fig 35` — `35_sector_freeze_sigma.png`, sector-change fraction vs σ
  during reverse sampling, σ_freeze ≈ 0.304 / 0.312 / 0.307 flat across a 16×
  range in volume.

### 3.5 Climbing more than one rung (NEW, measured 2026-08-22)

The ladder is a multi-lift construction and the paper should say what the rung
count costs, because until now every controlled measurement in BOTH studies used
a single lift from an HMC coarse ensemble. `60_multi_lift_compounding.py` (u1)
and `45_multi_lift_compounding.py` (u2) fix the ENDPOINT and vary the number of
lifts, so the arms differ only in how many times the model was applied:

    3 lifts   L=8  ->  L=16  ->  L=32  ->  L=64
    2 lifts            L=16  ->  L=32  ->  L=64
    1 lift                      L=32  ->  L=64

Eight cells: two theories x two endpoints (in coverage, past the training
ceiling) x rethermalization between rungs on/off. Every arm's start is generated
by HMC at exactly the chain's coupling, with topological updates on -- reading
the nearest ensemble off disk, or starting from a sector-frozen configuration,
both confound the comparison and both were caught doing so.

Three results, and the third is the one that changes a sentence elsewhere in the
paper.

* **The rung count is free.** Three lifts land at 0.94-1.02x the one-lift error
  with the ladder's rethermalization, 0.84-1.00x without. No trend in any cell.
* **The error is injected by the FINAL lift.** u2's 3-lift trace is z = +15.80
  at L = 16 (model beta 4.4), +0.91 at L = 32 (15.8), -157.44 at L = 64 (61.7).
  The intermediate rungs sit inside training coverage; the endpoint does not.
  **So laddering does not extend the COUPLING reach** -- every lift multiplies
  beta by about four, so the final lift lands at the same model beta whatever
  path reached it, and that rung's coverage binds. The ladder buys VOLUME at
  fixed coupling coverage, which is what it was for. State this as a negative
  result; it forecloses an obvious reader question.
* **The lift transports topology exactly under composition, and the tail does
  not.** With no rethermalization between rungs, 100% of configurations keep
  their starting charge at 1, 2 and 3 lifts in all four chains -- extending
  `36_transport_check.py` from one lift to three. Switch the ladder's own ten
  sweeps back on and the 3-lift arm loses charge wherever an intermediate rung
  is weakly coupled: u1 keeps 33.6% (rethermalizing at L = 16, beta = 3.87) and
  81.2% (beta = 5.24); u2, whose intermediate rungs are far stiffer, keeps 98.4%
  and 100%.

  This is re-sampling, not corruption, and the direction proves it: `<Q^2>` moves
  TOWARD the exact value (u1 ceiling chain 1.633 -> 1.539 against exact 1.386),
  because a rung weak enough for local moves to change Q is a rung where they
  sample Q correctly. **The framing sentence must therefore be stated as: the
  ladder re-samples topology at every rung where that is still valid, and
  transports it unchanged once the coupling is stiff enough that it is not.**
  "Drawn at the base and carried unchanged to the top" is exactly true only with
  intermediate rethermalization off.

### 3.6 What repairs the raw lift: sweeps, not trajectories (NEW 2026-08-22)

A practical point that changes how the tail should be described, and it is a
METHOD statement because both studies give the same answer.
`61_sweeps_vs_trajectories.py` (u1) and `44_sweeps_vs_trajectories.py` (u2) take
one lift, clone the configurations, and spend the same budget two ways --
heatbath + overrelaxation sweeps against HMC trajectories -- with costs matched
in LINK TOUCHES (a retherm sweep with two overrelaxation passes touches every
link 3 times; a trajectory touches it `n_steps` times).

| study | coupling | sweeps to \|z\| <= 2 | trajectories | ratio |
|---|---|---|---|---|
| u1 | beta_f = 55.02 | **6 touches** | 380 | 63x |
| u1 | beta_f = 98.47 | **12 touches** | never in 1500 | >125x |
| u1 | beta_f = 218.58 | **24 touches** | never in 2220 | >92x |
| u2 | model beta 43.9 | **6 touches** | never in 4600 | >767x |
| u2 | model beta 134 (+29% past coverage) | **6 touches** | never in 2560 | >427x |
| u2 | model beta 327 (+214% past coverage) | **6 touches** | never in 2560 | >427x |

Cold-start trajectories never converge in any cell of either study. Two
consequences worth stating in the paper:

* **The repair for a raw lift is cheap exact local sweeps, not more HMC** --
  including at couplings far past the training ceiling, where the raw lift is
  150-250 sigma out and two sweeps still fix it.
* **Any `t_therm` quoted in trajectories understates the seed by two orders of
  magnitude** as a practical cost. That does not invalidate the t_therm tables,
  which compare like with like against classical arms, but the paper should say
  which currency it is using and why.

This also settles what "the seed does not thermalize past the top training rung"
means: it is a statement about the MOVE, not about the model. The lift's local
error is repairable at any coupling tested; what is NOT repairable by local
sweeps is topology, which is why Q is transported rather than generated.

- `[EXISTS] Fig 30` — `fig30_multi_lift.png` (`46_multi_lift_figure.py`), three
  panels: no compounding, error injected by the final lift, and the
  charge-preservation bar chart across all eight cells. Reads both studies'
  output; it is the natural place to show u1 and u2 side by side.

A caveat that WAS carried here is now discharged. Post-rethermalization
endpoint |z| appeared to creep with lift count (u2 in-coverage 0.63 / 0.83 /
1.86; u1 ceiling 0.19 / 0.01 / 2.69), monotone in three of four chains. At 4x
the statistics it went the diagnostic way: u2 reads 0.08 / 0.71 / 0.82 and u1
0.15 / 0.32 / 0.63 at n = 256. Since `z ~ sqrt(N)` a real bias would have
DOUBLED and it fell by half, so "no compounding" holds for the DELIVERED
product, not only for the raw lift. Charge preservation reproduces at the higher
statistics (u2 98.4 -> 97.7%, u1 81.2 -> 82.0%), so that effect is real.

### 3.7 The reverse-diffusion step count, and why 200 is justified (NEW 2026-08-22)

Both studies fix the sampler at 200 reverse-diffusion steps and neither had
measured what that buys. u2's dial (`14_sampler_steps.py`) found 25 steps was
~3x cheaper at ~2.7x the extended-loop error. u1's (`63_sampler_steps.py`) at
first appeared to find far more -- a flat post-rethermalization score from 18
steps to 200, i.e. a free factor of 10-14.

**That was wrong, and the way it was wrong is the useful part.** The scan called
`generate_fine_from_coarse` with the function's bare defaults, and those are not
the deployed sampler: `v3_scale.yaml` runs `physics_blend_coef: 1.0`,
`physics_blend_beta_min: 5.0`, and `03_run_ladder.py` rebuilds the noise
schedule with `sigma_min_beta_coef: 0.1` before sampling, while the function
defaults blend off. The blend and the step count interact, so an unblended scan
cannot see the cost of cutting steps. **A measurement of a tunable is only about
the deployed system if it reads the deployed configuration**; the script now
takes `--config` and reads every knob from it.

Re-run with the deployed knobs, worst-loop |z| against the closed form:

| steps | raw, beta_f = 55.02 | raw, 218.58 | post, 55.02 | post, 218.58 | cost |
|---|---|---|---|---|---|
| 12 | 32.9 | 36.9 | 0.50 | 0.58 | 17x cheaper |
| 18 | 16.0 | 19.7 | 0.44 | 0.52 | 11x cheaper |
| 25 | 11.4 | 15.5 | 0.44 | 0.51 | 8x cheaper |
| 100 | 3.4 | 17.4 | 0.44 | 0.50 | 3x cheaper |
| **200** | **1.0** | **4.3** | 0.43 | 0.50 | deployed |

**The two products want different settings, and that is the finding.** The post
column is flat from 12 steps up, so the DELIVERED ensemble needs only 18 steps.
The raw column is still falling at 100, so the SEED needs 200 -- and the seed is
what every seed-quality claim in section 4 is measured on (`t_therm`, `N*`, the
prolongator ablation). **`v3_scale.yaml` stays at 200 and the "factor of 10 on
the table" is withdrawn.**

Verified end to end rather than argued: `u1_2d/configs/v3_scale_s18.yaml` runs
the whole deployed ladder at 18 steps into `out/u1_2d/validation_s18/`. The
delivered ensemble is indistinguishable from the record (max |z| 2.07 -> 1.42,
1.74 -> 2.18, 1.28 -> 1.64 across the three rungs) while the raw lift degrades
3-4x at every rung (12.3 -> 53.1 at the top). Sixteen rethermalization sweeps
hide the difference in the ensemble, which is exactly why the post column alone
must not set the deployed value.

Two things worth a sentence in the paper:

* **A cheap sampler IS available for a consumer that only wants the
  rethermalized ensemble** -- 11x, at both couplings. It is not available for
  anyone using the output as an HMC seed. Whichever a run does, it should say so.
* **At beta_f = 218.58 the raw lift never really converges in step count**
  (19.7 / 15.5 / 26.0 / 28.9 / 17.4 / 4.3 at 18-200, non-monotone and large).
  That coupling is 3.6x past u1's dense training ceiling of beta = 60, so this is
  the coverage limit of section 3.5 showing up in a different measurement, not a
  sampler effect. Consistent with Fig 46.

---

## 4. The result: seed quality

**This is the paper's centre of gravity and should be the longest section.**

### 4.1 The measurement
`t_therm` — trajectories of instanton-HMC needed to reach equilibrium from a
given start, scored against exact references. Define it precisely, state the
criterion, and state the budget convention explicitly (every non-converging
entry reads "> 2000", never "never" — §25.5 lesson 5).

### 4.2 Seven arms, one criterion (Table S6b, promoted from appendix C)

| β_f | tile | halve | flux | **ape** | fresh hot | fresh cold | **diffusion seed** |
|---|---|---|---|---|---|---|---|
| 4.44 | 77 | 69 | 71 | **49** | 63 | 56 | **8** |
| 6.11 | 696 | 156 | 185 | **136** | 148 | 100 | **4** |
| 14.15 | > 2000 | > 2000 | 425 | **149** | never | 141 | **0** |
| 55.02 | > 2000 | > 2000 | > 2000 | **321** | never | 393 | **0** |
| 218.58 | > 2000 | > 2000 | > 2000 | **150** | never | never | **6** |

Three things to make explicit, in this order:

1. **The learned seed is flat in β at 0–8 trajectories** while every other arm
   grows or fails. At β = 14.15 and 55.02 it is *already thermalized* by the
   criterion.
2. **The classical arm is a real competitor, not a strawman.** `ape` is
   Endres-style prolong-then-smooth with the smearing count tuned per β to
   match the exact plaquette (a fixed count would hand it an over-ordered
   configuration and beat a strawman). It is the only non-learned arm that
   beats a fresh cold start, and it converges at β = 218.58 where fresh starts
   never do. The learned seed still wins by 6×, 34×, and 25× at the couplings
   where both converge in nonzero time.
3. **The speedup is specific to learning, not to having been handed the coarse
   configuration.** Three geometric prolongators — including the exact inverse
   of the blocking rule — are all *worse than a fresh cold start*. Prolonging by
   any obvious deterministic rule satisfies the coarse constraint while being
   wrong at short distances, which the chain must then undo.

- `[EXISTS] Fig 29` — `29_seed_quality.png`, `t_therm` vs β, five arms (the
  three geometric prolongators are drawn as one best-of trace), log scale.
  **Lead figure.** One panel carries the paper's main claim.
- `14_relaxation_mid.png`, `15_relaxation_high.png` — relaxation from a
  diffusion seed.
- `12_timescales.png`, `16_autocorrelation_modes.png` — autocorrelation.

### 4.3 The tail never has to tunnel
The sector arrives correct by the §3.1 identity. Measured (§21.6): fixing P(Q)
with a short instanton-HMC tail needs **100, 0, 0** trajectories at
V = 2048, 8192, 32768 — the cost *falls* while the χ² test's power *rises*
(7, 11, 15 populated bins), so this is not a resolution artifact. Across the
L = 32 β-ladder the tail never exceeds 150 trajectories.

Deliberately mismatched topology recovers too: P(Q) χ² p-value 0.0005 → 0.43 in
6 seconds of MCMC.

- `21_pq_tail_mismatch.png`, `22_pq_tail_L64.png` — the seeding recovery.
- `[EXISTS] Fig 36` — `36_sector_tail.png`, the tail repairing ⟨Q²⟩ and the
  P(Q) χ² across five couplings at two volumes, with wall-clock annotated.
- **Still not drawn, and it needs new data rather than a new script.** The
  tail-length **vs volume** panel (100 / 0 / 0 trajectories at
  V = 2048 / 8192 / 32768, with 7 / 11 / 15 testable bins) cannot be rebuilt:
  `sector_tail_scaling/` was pruned 2026-08-18 and only the `raw`-variant
  ensembles survive in `generalization/generated/`, so reproducing it means
  regenerating the `transport` ensembles first. Fig 36 covers the same claim
  across β at two volumes from live data.

### 4.4 Does the advantage survive volume? (measured 2026-08-19)

Fixed β_f = 14.1464, V = 2048 → 32768 (L = 32/64/128), the same 16× range as
the sector-tail scan. **The answer is two-sided and both sides belong in the
main text.**

| L | V | seed | cold start | hot start | speedup |
|---|---|---|---|---|---|
| 32 | 2048 | **1** | 168 | never | 168× |
| 64 | 8192 | **3** | 400 | never | 133× |
| 128 | 32768 | **30** | 528 | never | 17.6× |

*The seed does not degrade.* Its absolute plaquette bias is flat across the
range — 9.7, 8.5, 9.7 × 10⁻⁴ — a volume-independent per-site offset, which is
what the ≈1 nat/site density measurement predicts and an independent
corroboration of §5.3's per-site picture.

*The criterion tightens.* `t_therm` is defined on a z-score whose denominator
is the across-chain SEM, and the per-chain spatial mean self-averages, so the
acceptance width falls with volume (3.10 → 1.60 × 10⁻⁴) and z climbs
3.11 → 3.24 → 6.06 on a seed of constant quality. The baseline is less
sensitive because it anneals an O(1) bias — relaxation-dominated, threshold
entering logarithmically — while the seed starts a hair above threshold and is
threshold-dominated.

**Scope this carefully in the writing.** The flat-cost claim is established in
the **β** direction (§4.2) and *not* in the **V** direction: the advantage
narrows monotonically, and a 30-trajectory tail at L = 128 is a real charge.
The defensible statements are (i) the seed's quality is volume-independent,
and (ii) it beats every converging alternative at every volume by 17.6–168×.

Known confound to disclose: the chain count used for `t_therm` falls 32/16/8
across the three volumes, so part of the SEM decrease is fewer chains rather
than self-averaging. A rerun at fixed chain count would sharpen the
decomposition; it cannot change the direction of either effect, since the bias
column is chain-count independent.

- `[EXISTS] Fig 30` — `30_volume_scan.png`, two panels: the raw `t_therm`
  growth, and the flat-bias/shrinking-threshold decomposition that explains it.

## 5. How far from equilibrium is the seed?

The second contribution, and under this framing it is a *specification of the
tail*, not a negative result. Structure it as a measurement, not a caveat.

### 5.1 Observable-level agreement (what conventional grading says)
38 cases, β = 1.49 → 872.8 (15× beyond the training max), L up to 128.
Plaquette to ~2 parts in 10⁴. **Report the z-distribution, not a pass count** —
mean |z_exact| = 0.888 on the τ_int-aware records, against 0.798 ideal.

This is evidence the seed is *close*, which is why the tail is short. It is not
a standalone correctness claim and should not be written as one.

- `04_matched_scan.png`, `06_size_scan.png`, `13_beta_scan.png`.
- `10_case_extrapolation.png`, `11_case_L64.png` — pick two for main text.
- `[EXISTS] Fig 37` — `37_z_distribution.png`, the z-histogram across all
  cases/observables with the unit normal, matched arm against the
  deliberate-mismatch control. Matched mean |z| = 0.806 against an ideal 0.798,
  4 of 1091 beyond |z| = 3; the mismatch control carries 29 of 210.

### 5.2 Where the agreement frays, and why that is the interesting part
std(z) grows with loop extent. **Corrected 2026-08-20: the growth is 0.91 at
W(1×1) → 1.19 at W(12×12)** on the τ_int-aware records over the 37 matched
cases (Fig 38). The 1.09 → 1.44 / max |z| 3.1 → 5.9 previously quoted here
predates the §25.7 re-scoring, which widened the error bars and so shrank every
z. The direction of the claim is unchanged and is what the figure shows; the
numbers are not. The residual lives in **long-wavelength modes** — exactly the modes
local rethermalization relaxes slowest. That is a measured statement about
*what the tail has left to do*, and it is the bridge to §5.3.

- `[EXISTS] Fig 38` — `38_z_vs_loop_area.png`, std(z) and max|z| vs Wilson
  loop area.

### 5.3 The density gap, measured
The free-energy identity E_q[log w] − ΔF = −KL(q‖p) turns a saturated
certificate into a measurement in nats/site. Result: **≈ 1 nat/site**, i.e.
hundreds to thousands of nats per configuration, while the plaquette agrees to
2 parts in 10⁴.

*(Pick one number set before drafting — the walkthrough says 0.88 / 1.02, the
narrative says 0.9–1.0, and the AIS cross-check gives 1.01–1.68. See
`READING_GUIDE.md` §Live inconsistencies item 1.)*

The machinery — probability-flow ODE, one-pass sampling, fiber-corrected
weights, Hutchinson divergence — belongs here, compressed, and framed as **an
instrument for measuring seed quality**. Include the validation of the
instrument on an exactly solvable target (ESS/N > 0.5, free-energy certificate
closing to < 0.02 nats), because that is what licenses the number.

- `28_dissociation.png` — the money figure. Observables sharp, density off.
- `[EXISTS] Fig 39` — `39_kl_per_site.png`, KL per site vs case on the deployed
  checkpoint (0.94 / 1.10 / 1.10 / 1.70), with the instrument's own validation
  on an exactly solvable target as the reference line. **Use these four numbers
  as the one set** — that settles `READING_GUIDE.md` §Live inconsistencies
  item 1, which is the "pick one number set before drafting" note above.

### 5.4 Why the dissociation had to happen
Low-order gauge-invariant observables are a very low-dimensional projection of
a 2L²-dimensional measure. Cite Schaefer–Sommer–Virotta exactly here: Wilson
loops decouple from the slow topological modes, so this is what one should
*expect*, not a quirk of this checkpoint.

**The reading under this framing:** a seed can be four-significant-figures
correct on every observable you would think to check and still be ~1 nat/site
from equilibrium — which is precisely why you run the tail and why you must
measure `t_therm` rather than trust an observable table.

### 5.5 The gap will not be trained away (appendix-bound, summarized here)
One paragraph plus a pointer. Six interventions, each converged with an
identified mechanism; the recurring one is that **maximum likelihood optimizes
the wrong direction of KL**, demonstrated at 197k parameters and again at 354,
so the asymmetry is intrinsic to the objective rather than a capacity effect.

The conclusion that matters for this paper: **budget the tail, do not expect to
train the gap away.** Full chain goes to appendix D.

- `24_proposal_sweep.png`, `25_finetune_dynamics.png` — appendix.

---

## 6. Cost accounting

### 6.1 The classical baseline of record
**HMC + exact winding update, not plain HMC and not PTBC.** Say why in the
first paragraph. Table S8, L = 32, 3000 trajectories: plain periodic HMC is
fully frozen at all three couplings; the winding update reproduces exact ⟨Q²⟩ to
2% with τ_int ≈ 1.2–2.9 for a 1–18% overhead; a properly tuned PTBC ladder
(swap acceptance 0.68–0.98, τ_int ≈ 3) still costs 25–121× more. Cost of one
independent configuration: **0.124 / 0.090 / 0.198 s** for `hmc+inst`.

> **Number caution, 2026-08-20.** Those three seconds-figures come from a run
> directory removed in the 2026-08-18 prune. The arms were re-run
> (`out/u1_2d/classical_arms/`) and the **physics reproduces exactly** —
> τ_int(Q²) 2.85 / 1.20 / 1.39, zero sector changes for plain HMC at all three
> couplings, open boundaries 1.04 / 0.55 / 0.52 — but the wall-clock is ~35%
> faster (**0.077 / 0.055 / 0.128 s**) because the re-run is single-threaded.
> Figures 40 and 41 carry the re-run, which is the conservative direction: it
> makes the classical baseline harder to beat. Quote one set or the other,
> never a mixture.

- `[EXISTS] Fig 40` — `40_cost_per_config.png`, s per independent configuration
  vs β, the four classical arms plus the prolongator, log scale.

### 6.2 The winding update itself
Definition, gauge-covariant construction, the Metropolis test that makes it
exact, cost ΔS ≈ 2π²β/V. Distinguish clearly from the **deterministic
projection** used inside the prolongator — same object, different role, and the
distinction is what keeps the correctness claim honest.

### 6.3 Break-even
- Prolongation: flat ~2.4 s/configuration at every coupling, plus a 0–8
  trajectory tail.
- Entry cost, charged: **8820 s one-time** (21.7 min data + 125.3 min
  training), which exceeds every classical burn-in that converges.
- The defensible claim is about **scaling** — flat in β against a baseline whose
  entry cost diverges and then stops converging — not about being cheaper
  outright at a single coupling.
- **The break-even configuration count against `hmc+inst` at β = 218.58 is now
  measured, and the answer is that there is no crossing** — 0.128 s against
  2.55 s marginal, so the winding update stays cheaper at every configuration
  count. Against tuned PTBC the crossing is at 250 configurations. Fig 41 draws
  both, and this closes the item.

- `17_headtohead_cost.png`, `18_entry_cost.png`, `26_three_way.png`.
- `[EXISTS] Fig 41` — `41_breakeven.png`, cumulative cost vs number of
  configurations, three lines, crossings annotated.

---

## 7. What this implies for the class of method

### 7.1 The design directive, now demonstrated rather than owed
Exactness comes from Markov-chain machinery wrapped *around* the proposal, not
from the proposal's own likelihood. Under this framing the paper *is* the
demonstration: a proposal with ~1 nat/site of density error, wrapped in exact
HMC, delivers correct physics in 0–8 trajectories.

Note that in non-abelian theories the likelihood route is unavailable in
principle (the forward heat kernel, hence the score target, is itself
approximate) — which makes the prolongator framing the *only* one that
transfers.

### 7.2 A local corrector is not a substitute for a real tail
The MALA experiment. Acceptance ratio ≈ 1 against equilibrium starts while
⟨Q²⟩ is **bit-identical before and after in all eight settings** — zero sector
changes across 50 steps × 64 configurations × 8 settings. An acceptance rate,
however high, is a local statement and does not bound mixing on the modes the
proposal cannot move.

- `[EXISTS] Fig 42` — `42_mala_locality.png`, MALA acceptance vs ε
  (model-start and equilibrium-start, nearly identical) beside ⟨Q²⟩
  before/after (bit-identical in all eight settings, and wrong).

### 7.3 A reporting protocol
Compressed to a boxed checklist. Strongest items under this framing: report
`t_therm` against a tuned classical prolongator, not against a cold start;
state the budget in the cell rather than writing "never"; report the
z-distribution not a pass count; report dispersion against observable extent;
never quote a saturated ESS; report KL where an exact free energy exists;
charge the generative arm its entry cost; report raw pre-enforcement topology;
say which mode the correctness claim attaches to.

**Six statistical items added 2026-08-22.** Each was found by an error made in
one of the two studies and then checked for in the other, so they are stated as
protocol rather than as anecdote. `docs/PARITY_U1_U2.md` §5 holds the full
record; the paper should carry them compressed.

0. **A note on how these were found.** Each is a correction to a claim this
   project had already made, and two of them are corrections to *earlier
   versions of this list* -- item 3 was itself wrong by a factor of 3.3 until
   the observable correlations were measured rather than assumed. The general
   lesson is the cheap one: before quoting any statistic, compute what value it
   would take if nothing were wrong.

1. **Never quote a bias without its standard error.** A u2 finding --
   rethermalization making W(8x8) "four times worse" -- was retracted when both
   disputed numbers turned out to sit at z = 0.31 and z = 1.30 against a SEM of
   1219 ppm. Large Wilson loops have enormous per-configuration spread and are
   frequently unresolved at the ensemble sizes in use.
2. **`N* = (sigma/bias)^2` squares the bias**, so it is unbounded wherever the
   bias is unresolved. Quote N* only at scales that pass item 1.
3. **`mean |z|` has a null value of sqrt(2/pi) = 0.798**, not zero, because |z|
   is half-normal for a correct model with correct errors -- **and its standard
   error must use the EFFECTIVE number of observables.** Measured: the 41
   observables scored at L = 32 have a correlation matrix with top eigenvalue
   18.6 and mean within-family |correlation| 0.62 (2D Wilson loops of different
   sizes are near-deterministic functions of one another), giving a
   participation-ratio `N_eff` of **3.77**, so `SE(mean |z|) = 0.31`, not 0.09.
   Using the raw count overstated three claims in this project by 3.3x: a
   validation 0.484 is 1.0 sigma from null and not 3.3; a capacity 0.187 is 2.0
   and not 6.5; and a sector-ablation null excludes only effects above 0.88, not
   0.27. Quote `N_eff` beside every `mean |z|`.
4. **A relative deviation is not comparable across beta.** The theory's own
   spread falls by orders of magnitude as beta rises, so an unnormalized ratio
   drifts downward whether or not the model improves: Spearman -0.82 against
   model beta in u2's fig29, which REVERSES to +0.80 in z.
5. **A single `t_therm` is not interpolatable to a neighbouring coupling.**
   Measured: 59 / 51 / 6 / 50 records at adjacent couplings, reproduced across
   two independent rounds and two independent implementations. Report
   correlations across a scan; never name an example point.
6. **State the resolution of every null result** -- computed at `N_eff`, per
   item 3. u2's sector-distribution ablation agrees to 0.012 and 0.096 in
   mean |z|; at `N_eff = 3.77` the SE of that difference is 0.44, so it excludes
   nothing smaller than **0.88**. The claim is a weak bound, not a demonstration
   of zero, and the strong form of the transfer argument should rest on u1's
   `sector_augment` construction instead (section 8.6).

---

## 8. Carrying the method to a non-abelian group: 2D U(2)

**Status: publishable as written. Added 2026-08-21.** Everything below is
measured and every script is tracked; the two open items are named in 8.6 and
neither is load-bearing for the section's claim.

**Why this section exists.** Sections 1-7 establish the prolongator result on a
theory that is *abelian* and *exactly solvable*, and both properties do real
work: the abelian telescope makes topology transport an identity, and the
character expansion supplies the reference every z-score is computed against. A
referee is entitled to ask which of the two the method actually needs. 2D U(2)
separates them. It is genuinely non-abelian, it is still exactly solvable, and --
the reason it is the right next step rather than SU(2) -- its topology lives
entirely in the determinant, which is an honest compact U(1) field. So the U(1)
machinery is *reused* rather than rewritten, and what changes is the physics.

### 8.1 What carries over unchanged, and why

Links use the NTHMC-compatible split representation `U = e^{i phi} q`,
`[..., 5] = (phi, q0, q1, q2, q3)`. Three facts carry the section:

* `psi = wrap(2 phi) = arg det U` is a compact U(1) gauge field and **Q is a
  functional of `psi` alone**. Because `det` is a homomorphism, the plaquette
  determinant phase is the plain SUM of link phases, so the abelian telescope of
  section 3.1 survives *verbatim*: the coarse determinant plaquette is the
  wrapped sum of its four fine children, exactly, non-abelian group
  notwithstanding. **Sector transport is therefore still an identity.**
* One inverse-RG step factorizes as `p(psi, q) = p(psi) p(q | psi)`. The model
  generates `psi` only. The SU(2) sector needs no model at all: at frozen `phi`
  the local weight is exactly `exp(beta k . q)`, so a conditional heatbath is an
  EXACT sampler for `p(q | psi)` and leaves `psi` and `Q` bit-for-bit unchanged.
* **The joint does not factorize** -- `(1/2) ReTr P = cos(omega_p) cos(phi_p)` is
  a product. Generating the sectors independently is wrong at
  `O(phi^2 omega^2)`. Two consequences, both handled: SU(2) is generated
  conditionally, and `psi`'s marginal is NOT Wilson at `beta/4` but carries the
  exact SU(2)-integrated weight `w_det(alpha) = 2 I_1(z)/z`,
  `z = beta cos(alpha/2)`. Anything analytic must use the minimum-KL projection
  `matched_u1_beta`, which differs from `beta/4` by 23% at `beta = 4`.

- `[NEW] Fig 26` -- **transport exactness**, `36_transport_check.py`. Fraction of
  configurations whose fine `Q` equals their coarse `Q`, against coupling, at
  both `L_c = 16 -> 32` and `L_c = 32 -> 64`. It is 100% everywhere, config by
  config -- not `<Q^2>` agreeing on average. This is the identity the whole
  section rests on and it had never been tested on the *generative* path, only
  on the blocking map in `09_verify_identities.py`. Small figure; a table would
  also do.

### 8.2 The U(2)-specific physics: two freezing mechanisms, not one

This is the section's original contribution and it has no U(1) analogue.
`U(2) = (U(1) x SU(2)) / Z_2`, so `Q` even <=> the ordered product of SU(2)
plaquettes is `+1`, and `Q` odd <=> it is `-1`. The two winding moves are
governed by different parameters, and **only one is protected by the ladder**:

* **Even `dQ`** is a central U(1) instanton, cost `2 pi^2 beta / V`, governed by
  `beta / V` -- which the matched ladder holds nearly constant (0.219 -> 0.202 ->
  0.198 -> 0.197 across `L = 8..64`). Even-charge mobility is a ladder invariant
  and never degrades.
* **Odd `dQ`** must cross the `Z_2` monodromy. No fixed shift field does it
  cheaply: halving the instanton leaves a spurious `-1` on one plaquette at cost
  `2 beta` (`dS = 37` at `beta = 20, L = 8`); the `U(1)_T` construction costs
  `O(beta L)`. Gauge fixing does not help.

The fix is to change the *acceptance*, not the proposal: propose the winding-1
shift on `psi`, accept on the EXACT SU(2)-integrated marginal, then resample
SU(2) from its exact conditional -- which is where the flipped plaquette is
absorbed for free. Head-to-head at matched protocol (L = 16, hot start, 256
chains, 2000 trajectories, same script and seed, only `--charge-step` differing):

| beta | joint flips | marginal flips | joint tau(Q^2) | marginal tau(Q^2) |
|---|---|---|---|---|
| 14 | 4919 | 72522 | 0.55 | 2.73 |
| 21 | 13 | 67298 | 0.53 | 2.37 |
| 28 | 0 | 61403 | 0.55 | 1.98 |

Odd fraction is correct at every point (z = -0.50 / +0.41 / -1.65 against exact
0.5000 / 0.4989 / 0.4928), and the move is separately verified unbiased at its
deployed setting (`34_marginal_move_bias.py`: odd-weight z = +0.26 and +1.46 at
10x the statistics of the first pass).

- `[EXISTS] Fig 9` -- `fig09_parity_mobility.png`, the two-move comparison.
- `[EXISTS] Fig 10` -- `fig10_winding_economics.png`, the cost of each move.

### 8.3 Two standard diagnostics report HEALTHY on a parity-frozen chain

The most transferable warning in the section, and it generalizes to any theory
with a discrete topological obstruction:

* **Sector-change counts.** Even moves keep firing while the odd/even balance is
  stuck, so the chain "changes sector" thousands of times while `P(Q)` is 20%
  wrong. Do not conclude a coupling is ergodic from sector-change counts.
* **`tau_int(Q^2)`.** The *broken* sampler looks 4x better -- 0.55 against the
  marginal move's 1.98-2.73 -- because the joint move shuffles `Q` by `+-2`
  quickly *inside one parity class* while never crossing the monodromy. The
  marginal move's larger value is the honest cost of sampling the parity degree
  of freedom too.

Neither is an ergodicity test. **Count parity flips.**

- `[EXISTS] Fig 19` -- `fig19_freezing.png`, `Q` traces in the frozen regime.

### 8.4 The result: a generated configuration as an HMC seed

`L = 64`, `beta = 416.524`, 64 chains, 400 trajectories per arm, eight arms
(`08_hmc_seed_benchmark.py`). The classical baseline is the honest one -- HMC
plus the *marginal* odd move -- not plain HMC.

| arm | plaq err t=0 | plaq err final | `<Q^2>` | P(Q) covered | odd sectors |
|---|---|---|---|---|---|
| diffusion seed | **5.33e-06** | 6.29e-06 | 0.938 | 0.991 | **2** |
| cold start | 4.83e-03 | 4.65e-05 | **0.000** | 0.399 | 0 |
| cold + even winding | 4.83e-03 | 5.94e-05 | 0.870 | 0.507 | **0** |
| diffusion + even winding | 5.33e-06 | -5.93e-06 | 0.984 | 1.000 | 4 |
| cold + odd winding | 4.83e-03 | 4.22e-05 | 0.985 | 1.000 | 4 |
| hot start | -1.00e+00 | -6.25e-02 | **91.5** | 1.000 | 30 |

Exact `<Q^2> = 1.001`. Three things to say, in this order:

1. **Plain HMC is not slow here, it is stationary.** One sector, `<Q^2> = 0.000`,
   0.399 of exact `P(Q)`, after 400 trajectories.
2. **The cheap classical move does not fix it.** Adding even winding raises
   `<Q^2>` to 0.870 but the chain still occupies **zero odd sectors**. That is
   8.2 made visible: the accessible move cannot change parity.
3. **The seed arrives with odd sectors it never had to manufacture.** 0.991
   coverage and 2 odd sectors *before any winding move at all*, inherited by
   transport from a base at `beta = 3.5` where HMC is fully ergodic. Its
   plaquette starts three orders of magnitude closer to exact than a cold start
   and does not move; the cold arms plateau at ~4.7e-05, still ~8x further from
   exact than the seed was at `t = 0`.

Read coverage WITH `<Q^2>`: the hot arm "covers" 1.000 while carrying
`<Q^2> = 91.5`.

- `[EXISTS] Fig 6` -- `fig06_seed_quality.png`, relative error vs trajectory, all
  arms. **Section lead figure.**
- `[EXISTS] Fig 7` -- `fig07_topological_reach.png`, distinct sectors occupied and
  `<Q^2>` vs trajectory, all arms. The strongest single panel in the section.

### 8.5 Cost, stated as a cost claim rather than an impossibility one

An earlier version of this work claimed the classical arm *could not* reach odd
charge. That was false -- it was a property of the retired joint proposal, not of
the theory. What survives is better, because it is falsifiable and still
decisive:

* `cold + odd winding` reaches the same endpoint as the seed and takes
  **1025 s** to do it, against **334 s** for `diffusion + even winding`. The
  classical route must *manufacture* the sectors the seed *arrives with*, using
  the expensive move, at ~3x the cost.
* The ladder itself is not a speed-up at the accuracy setting of record: 200
  reverse-diffusion steps make the top rung 3.87x slower than HMC + winding per
  independent configuration. At 25 steps it is **1.38x faster** at ~2.7x the
  extended-loop error, and below 18 steps the lift collapses. The ~90 s fixed
  overhead per ladder pass (30 SU(2) + 10 retherm sweeps) is the next knob, not
  the sampler.

- `[EXISTS] Fig 13` -- `fig13_cost.png`, seconds per independent configuration.
- `[EXISTS] Fig 14` -- `fig14_sampler_steps.png` (appendix), the accuracy/cost dial.

### 8.6 What does not carry, stated rather than papered over

* **Seed quality tracks distance to training coverage, not beta.** Across 15
  couplings at two volumes the seed is excellent within ~10% of a training rung
  in model beta, degraded at 16-30%, and *fails entirely* past the top rung
  (model beta 104). **Two of those couplings are IN-SAMPLE** -- at
  `beta_f = 415.61` both the coarse input and the fine target are training rungs
  at the same volumes, 0.2% off in beta -- and must be marked as such in any
  figure and excluded from any correlation. The claim does not need them: the
  seed thermalizes where *both* classical arms never do at `beta_f = 58.03,
  87.04, 127.55, 183.59, 264.24`, all out-of-sample.
* **Volume degrades the seed at fixed coverage.** At model beta ~45 and the same
  gap, `t_therm` is 6 at `L = 32` and `inf` at `L = 64`. The four L = 64 bases
  were chosen by MODEL BETA precisely so each pairs with an L = 32 scan point and
  differs in volume and almost nothing else, which makes the paired comparison
  legitimate. `[EXISTS] Fig 27` -- `fig27_volume_scan.png`, `38_volume_figure.py`.
* **The high-beta training rungs install their topology rather than sampling
  it** (`seed_exact_sectors`, on every rung above model beta 12.9). This is sound
  *here* -- Q is transported and the learned object is local, so what the data
  must be right about is conditional local structure at fixed sector, which
  heatbath equilibrates whether or not the chain tunnels. But note precisely what
  the closed form is used for: it sets the sector FREQUENCIES of the training
  data, and those are overridden at deployment by transport. What the training
  data must supply is sector COVERAGE, which needs no closed form. The
  exactly-solvable dependency therefore sits in the *training-data recipe* and in
  the *scoring*, not in the method. **RUN 2026-08-22, and the answer is that it
  does not move.** `39_sector_distribution_data.py` rebuilt the training set with
  the installed charges drawn from UNIFORM over the same support instead of the
  closed form -- 106 ensembles, `<Q^2>` differing by a median factor of **5.6**
  (range 3.2-88) -- and trained an identical second network. Observable agreement
  after the ladder differs by 0.012 (L = 32) and 0.096 (L = 64) in mean |z|.
  **State the resolution with it:** with 41 observables the SE of that difference
  is 0.133, so the test excludes no effect smaller than **0.27**. It is a bound,
  not a demonstration of zero, and one diagnostic runs the other way (the
  prolongator's `t_therm` favours the exact arm 0 vs 8 and 2 vs 5 -- single
  t_therm values, which §7.3 item 5 says not to lean on).
* **And u1 makes the stronger version of that point by construction.** u1's
  `sector_augment` builds charged-sector coverage by applying FIXED instanton
  shifts of +-1, +-2 to a random half of the configurations at a rung. It never
  draws from P(Q) and never consults a closed form, and it is active on all four
  high-beta anchors of the deployed config -- so every u1 result of record was
  produced with sector coverage built without an exact P(Q). Together: u2 shows a
  WRONG sector distribution costs nothing measurable, and u1 shows NO sector
  distribution is needed at all. What the data must supply is a way to CHANGE the
  charge, not a way to WEIGHT it, and a topological shift is available in any
  theory with a topological charge. This is the transfer argument for 4D SU(3),
  and it no longer rests on solvability.
* **The density gap is the same as u1's and does not shrink here.** ~1.14
  nats/site, flat to 3% across a 30x range in beta, drifting slightly upward.
  Section 5's dissociation argument carries over unchanged.
* **The exact P(Q) is a training-data convenience, not a requirement of the
  method** -- tested directly rather than argued. `39_sector_distribution_data.py`
  builds two training sets from the same source ensembles through the same code
  path, drawing the installed charges from the closed form in one arm and from
  UNIFORM over the same support in the other (median `<Q^2>` ratio 5.6x, so the
  arms genuinely differ). Two identical networks are trained on them and scored
  by `40_sector_experiment_report.py`. Because the fine charge is imposed from
  the coarse ensemble at deployment and transport is exact, the training data
  should only need to COVER the sectors, not weight them correctly -- and
  coverage needs no closed form. **This is the experiment that decides whether
  the construction can be claimed for 4D SU(3).** Result goes here.

- `[EXISTS] Fig 21` -- `fig21_seed_quality.png`, `t_therm` vs beta, six arms.
  **Requires an edit before use: the two in-sample couplings must be marked.**
- `[EXISTS] Fig 24` -- `fig24_kl_per_site.png` (appendix), the flat density gap.

### 8.7 What the section claims

Not "the method is faster in 2D U(2)". The claim is:

> The prolongator construction transfers to a non-abelian group without
> modification, because what it needs is a blocking map that transports topology
> exactly -- which the determinant supplies. In transferring, it exposes a
> freezing mechanism with no abelian analogue, defeats the two diagnostics
> normally used to detect freezing, and delivers starting configurations
> carrying a topological charge sampled at a coupling where sampling works,
> which no amount of HMC at the target coupling can produce.

---

---

## 9. Related work

### 9.1 Classical multiscale thermalization — the direct ancestor
Endres et al. and Detmold–Endres, front and centre. The structural
correspondence: matched-β ladder ↔ their r₀ matching; the HMC tail ↔ their
step 4; sector transport ↔ their Q-preserving prolongation. **This paper is
their algorithm with a learned prolongator, and §4.2 is the comparison.**

### 9.2 The learned coarse-to-fine line
Inverse-RG upscaling (Ron–Swendsen–Brandt; Efthymiou et al.; Bachtis et al.),
RG-inspired flows (Bauer et al.), diffusion for gauge theory (Wang et al.; Zhu
et al.). All validate on critical exponents or observables; none measures
thermalization cost or asks whether the generated ensemble is Boltzmann.

### 9.3 Width is not correctness
The Zhu et al. case at L = 16, β = 7 (exact ⟨Q²⟩ = 1.0064): their HMC arm
0.06×, their diffusion arm 2.36×, ours 1.08× with χ² p = 0.41. Both of their
arms reject the exact distribution overwhelmingly, in opposite directions.

Frame this structurally, not competitively: **a wider Q distribution than a
frozen chain is not evidence of correctness when the correct answer is
available and sits between them.** Note the over-production is a failure our own
*raw* model shows too (2.5–5.4× above exact at strong coupling) — it looks like
a property of score-based samplers on this theory. Label the digitization as
digitization and our row as an out-of-range checkpoint use.

- `[EXISTS] Fig 43` — `43_zhu_pq.png`, the four P(Q) histograms with exact
  overlaid, the digitization and the out-of-range checkpoint use both labelled
  on the panel itself.

### 9.4 Positioning
Novel: the learned prolongator, the `t_therm` comparison against a tuned
classical arm, the density-gap measurement, the ladder invariant, and the
reporting protocol. Not novel: the ladder concept, the equivariant
architecture, the diffusion machinery, the winding update (Albandea et al.).

---

## 10. Conclusions and outlook

- A learned prolongator produces starting configurations that thermalize in
  O(1) trajectories at every coupling tested, where the best classical
  prolongator needs 10²–10³ and cold starts stop converging.
- Correctness is supplied by the HMC tail. The seed is measurably ~1 nat/site
  from Boltzmann, and that is fine — it is what the tail is for.
- Transferable: the ladder invariant, the equivariant curl-form score, the
  topology transport machinery, and the reporting protocol.
- Outlook: non-abelian (2D SU(2) — trivial π₁, exact heat kernel unavailable,
  single-plaquette curl basis known to be incomplete at ~18% of DSM target
  variance), and 4D as the eventual target. Note that the prolongator framing
  survives the loss of every exact reference, because `t_therm` can be measured
  against an equilibrated long chain rather than against analytics.

---

## Appendices

- **A. Exact character-expansion references.**
- **B. Full campaign tables** — the 38-case table (τ_int-aware, denominator 38),
  per-observable z, the sector-mode comparison.
- **C. Instanton-HMC burn-in scan** (Table S1) and the classical-remedy
  benchmark (Table S8: PTBC tuning, open boundaries, the swap-acceptance bug).
- **D. The density-gap program** — ODE likelihood, fiber weights, the six-item
  falsification chain, the R²_c decomposition, the Villain control and why it
  cannot be read as a subtraction. Tables S2, S5, S7 series.
- **E. Reproducibility** — `29_verify_identities.py`,
  `30_assemble_appendix_figures.py --check`, device conventions, checkpoints.

---

## What was dropped, and why

Recorded so the decision is reviewable rather than silent. None of this is
deleted from `NARRATIVE.md`; it is out of the *paper*.

| dropped | reason |
|---|---|
| **AIS bridging (§21)** — main text | It exists to deliver exactness *via importance weights*. The HMC tail delivers exactness directly, so the mechanism is orphaned under this framing. One sentence in appendix D at most; the ridge-scan intervention is a good methodological anecdote but not this paper's business. |
| **ESS as a headline metric** | ESS diagnoses importance sampling, which this paper does not do. Keep only the reporting rule ("never quote a saturated ESS") in §7.3. `19_ess_weights.png`, `23_ess_progress.png` → appendix or cut. |
| **The fine-tuning chain as a main-text section** | Compressed to §5.5's single paragraph. It answers "can the gap be trained away" (no), which under this framing is a *budgeting* question, not a correctness one. |
| **Per-level SMC** | Same reason as AIS, with less to show for it. |
| **"Observable agreement does not certify the measure" as a co-headline** | Retained as §5.4, demoted from a second thesis to the explanation of why `t_therm` is the right metric. |
| **PTBC as a benchmark arm** | Already retired by measurement (§25.6a). Keep as appendix C evidence that it was checked. |

**Kept deliberately, per the reframing decision:** NARRATIVE §15–18 stay in the
narrative in full. They are the quantitative answer to "how wrong is the seed,
and how much work does the HMC have to do" — which is now a load-bearing
question rather than a post-mortem.

---

## Figure economy

A main text of 10–13 figures, all of which now exist:

1. Pipeline schematic — `44_pipeline.png`
2. `t_therm` vs β, five arms — `29_seed_quality.png` — **lead figure**
3. Frozen-HMC Q traces — `31_frozen_traces.png`
4. Ladder ⟨Q²⟩ fixed point — `33_ladder_fixed_point.png`
5. Raw Q-match rate vs volume — `34_match_rate_volume.png`
6. Relaxation from a diffusion seed — `15_relaxation_high.png`
7. Sector-tail recovery — `21_pq_tail_mismatch.png` or `36_sector_tail.png`
8. Observable scan — `13_beta_scan.png`
9. std(z) vs loop area — `38_z_vs_loop_area.png`
10. Dissociation — `28_dissociation.png`
11. KL per site — `39_kl_per_site.png`
12. s per independent configuration — `40_cost_per_config.png`
13. Volume scan — `30_volume_scan.png` — the two-sided answer on whether
    the advantage survives volume.

Held for the appendix, in decreasing order of how likely a referee is to ask
for one of them in the main text: `45_architecture.png`, `37_z_distribution.png`,
`41_breakeven.png`, `42_mala_locality.png`, `43_zhu_pq.png`,
`35_sector_freeze_sigma.png`.

### Section 8 (2D U(2)) -- five main-text figures

All in `out/u2_2d/figures/`. Section 8 should not exceed five; it is a
demonstration of transfer, not a second paper.

| # | file | carries | state |
|---|---|---|---|
| 8a | `fig07_topological_reach.png` | sectors occupied and `<Q^2>` vs trajectory, eight arms -- plain HMC flat at one sector, even-winding at zero odd sectors, the seed arriving with them | **strongest panel in the section** |
| 8b | `fig06_seed_quality.png` | relative error vs trajectory, all arms | section lead |
| 8c | `fig09_parity_mobility.png` | joint vs marginal odd move, parity flips vs beta | ready |
| 8d | `fig13_cost.png` | seconds per independent configuration | ready |
| 8e | **`fig26_transport_exactness.png`** | fine `Q` = coarse `Q`, 100%, both volumes | **NEW -- `36_transport_check.py`, data 2026-08-21** |

**`fig30_multi_lift.png` is a MAIN-TEXT figure for section 3.5, not section 8**
(`46_multi_lift_figure.py`). It reads both studies' output and shows u1 and u2
side by side in all three panels, so it belongs with the method rather than with
the transfer demonstration -- and it keeps section 8 at its five-figure budget.

**And `fig28_pipeline.png` replaces u1's figure 1** (`41_pipeline_schematic.py`). It is
drawn for BOTH studies -- the SU(2) box is dashed and labelled `u2 only`, absent in U(1) --
so the paper carries one schematic rather than two. It is the natural place to make the
section-8 claim visible: the charge branch is drawn running AROUND the network.

Appendix, u1: **`46_observable_scan.png`** (`62_observable_scan.py`, NEW
2026-08-22) -- observable agreement across 14 couplings from beta 6 to 518, in
relative deviation AND in z, with the training ceiling at beta = 60 hatched. It
is the cleanest coverage figure in either study because u1's coverage is DENSE
to 60 rather than a set of isolated rungs, so the ceiling shows as a step and
the bias SIGN flips across it: raw z at W(1x1) runs -0.6, +6.1, +9.0, +8.9,
+8.7, +21.7 inside coverage and -63, -138, -150, -162, -179, -198, -205 outside.
Panel (d) shows ten sweeps returning almost every coupling to |z| < 2, including
far past the ceiling -- the same point section 3.6 makes on cost.

Appendix, u2: **`fig27_volume_scan`** (the volume answer, section 8.6),
**`fig29_observable_scan`** (observable agreement across 12 couplings, raw and
post-tail -- the coverage story shown on observables rather than on a
thermalization count; supports 8.6's first bullet),
`fig10_winding_economics`, `fig19_freezing`, `fig11_ladder_accuracy`,
`fig12_area_law`, `fig14_sampler_steps`, `fig18_z_vs_loop_area_*`,
`fig20_honest_distributions_*`, `fig24_kl_per_site`, `fig21_seed_quality` (after
the in-sample couplings are marked), and `fig1`-`fig5` (exact-solvability checks:
determinant density, sector weights, area law, beta matching, the ladder).

**Two figures must not go in without an edit.** `fig21_seed_quality` needs its
two in-sample couplings marked -- DONE 2026-08-21, `30_seed_quality_figure.py`
now carries `TRAIN_RUNGS` and draws the marking itself.

`fig22_division_of_labour` was held out until the rethermalization discrepancy
was resolved. **It is resolved and the resolution is a RETRACTION**
(`42_retherm_reconcile.py`; write-up
`out/u2_2d/retherm_reconcile/RECONCILIATION.md`). Neither side of the dispute
was ever resolved statistically: at W(8x8) the per-configuration spread is
19500 ppm, so 256 configurations give a standard error of 1219 ppm, and the two
contested numbers -- 378 ppm "before" and 1581 ppm "after" -- sit at z = 0.31
and z = 1.30. Measured fresh on the same configurations the sign flips with
sweep count. **There is no infrared damage to report, and the `N* = 137`
claim that followed from it is withdrawn**, since `N* = (sigma/bias)^2` on a
bias consistent with zero is unbounded.

`fig22` MAY therefore go in, but only over the scales that are resolved: the
raw lift is z = 18.6 at W(1x1) and z = 3.2 at W(2x2), and ten sweeps remove
both; W(4x4) and larger are already indistinguishable from exact in the RAW
lift at 256 configurations, so the figure must label them as unresolved rather
than draw a trend through them. The paper text should make the same
distinction: the model's residual is measured at two scales and bounded at the
rest.

**This is a general obligation for the paper, not a one-off correction.** Any
statement of the form "the deviation grows/shrinks with loop size" needs its
standard error quoted alongside it. Large Wilson loops have enormous
per-configuration spread, and at the ensemble sizes used here (64-256
configurations) they are frequently not resolved at all. `43_observable_scan.py`
now reports both the physical systematic and z for exactly this reason.
