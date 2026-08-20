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

---

## 8. Related work

### 8.1 Classical multiscale thermalization — the direct ancestor
Endres et al. and Detmold–Endres, front and centre. The structural
correspondence: matched-β ladder ↔ their r₀ matching; the HMC tail ↔ their
step 4; sector transport ↔ their Q-preserving prolongation. **This paper is
their algorithm with a learned prolongator, and §4.2 is the comparison.**

### 8.2 The learned coarse-to-fine line
Inverse-RG upscaling (Ron–Swendsen–Brandt; Efthymiou et al.; Bachtis et al.),
RG-inspired flows (Bauer et al.), diffusion for gauge theory (Wang et al.; Zhu
et al.). All validate on critical exponents or observables; none measures
thermalization cost or asks whether the generated ensemble is Boltzmann.

### 8.3 Width is not correctness
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

### 8.4 Positioning
Novel: the learned prolongator, the `t_therm` comparison against a tuned
classical arm, the density-gap measurement, the ladder invariant, and the
reporting protocol. Not novel: the ladder concept, the equivariant
architecture, the diffusion machinery, the winding update (Albandea et al.).

---

## 9. Conclusions and outlook

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
