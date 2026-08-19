# Paper Outline — Diffusion-Based Inverse RG for 2D Compact U(1)

Working scope: one paper, U(1) only. Figure references in `[brackets]` are
existing files in `out/u1_2d/paper_appendix/figures/`; `[NEW]` marks a panel
that does not exist yet and would have to be assembled (all from data already
in `out/u1_2d/`).

**Suggested title framing:** the sampler is the instrument, the measurement is
the claim. Something like *"Diffusion-based inverse renormalization group for
lattice gauge theory: what observable validation does and does not certify."*
The two-result structure (a working sampler; a demonstration that the standard
way of grading such samplers is insufficient) should be visible in the title.

---

## 1. Introduction

- Critical slowing down and topological freezing as the cost wall of lattice
  simulation; why generative samplers are attractive.
- The existing line of work: inverse-RG upscaling, RG-inspired coarse→fine
  flows, normalizing flows, diffusion for gauge theory. What that line
  validates on: critical exponents, Wilson loops, susceptibility.
- **The gap this paper addresses:** almost none of that line asks whether the
  generated ensemble *is* the Boltzmann distribution — and in the one theory
  where you can actually check, it isn't, by a wide margin, while every
  conventional check passes.
- Contributions, stated as three:
  1. A diffusion inverse-RG ladder that reproduces gauge-invariant observables
     out to 15× beyond its training coupling and 64× its training area.
  2. A direct measurement of the density gap (KL in nats/site via an exact free
     energy) showing that agreement to 2 parts in 10⁴ on the plaquette
     coexists with ~1–1.7 nats/site of density error.
  3. A cost benchmark against the *correct* classical baseline (HMC + exact
     winding update, not frozen HMC and not PTBC), plus a reporting protocol.
- One paragraph stating up front which correctness claim attaches to which
  mode (heuristic generation vs. seeded exact chain). Doing this in the intro
  rather than the discussion is what keeps the paper honest.

**Figures:** none, or a single schematic.
- `[NEW] Fig 0` — pipeline schematic: coarse ensemble → diffusion lift →
  sector transport → retherm → fine ensemble, with the beta ladder drawn as
  the outer loop. One clean figure here buys a lot of readability later.

---

## 2. Setup: the theory and why it is the right testbed

### 2.1 2D compact U(1) on the lattice
Link angles, Wilson action, plaquette convention, gauge invariance, topological
charge as the wrapped-plaquette winding number.

### 2.2 Exact solvability
Character expansion gives exact ⟨plaquette⟩, Wilson loops, free energy, and the
finite-volume P(Q). This is the whole reason the paper can say anything the
rest of the literature cannot — emphasize it early.

### 2.3 The failure mode being targeted
Topological freezing of periodic HMC at large β.

**Figures:**
- `[NEW] Fig 1` — Q(t) traces for plain HMC at β = 14.1 / 55.0 / 218.6, L = 32,
  showing 0 sector changes in 3000 trajectories at all three. Flat lines are
  the point. Data: `out/u1_2d/ptbc_benchmark_tuned/`.
- `[NEW] Fig 2` — exact ⟨Q²⟩ vs β overlaid with what frozen HMC measures (0),
  making the size of the systematic error visible.

---

## 3. Method

### 3.1 Blocking, the ladder, and the fixed-point invariant
2×2 blocking, tree-level β_c = β_f/4, L_f = 2L_c. State the ladder invariant
explicitly: exact finite-volume ⟨Q²⟩ ≈ V/(4π²β) is a **fixed point** of the
ladder (1.20271 → 1.20334 → 1.20334 → 1.20334 over four rungs, Villain). So
sector transport across a rung is an identity, not an approximation, and
climbing the ladder is a continuum trajectory at fixed physical volume. This is
the design's justification and deserves its own short subsection.

- `[NEW] Fig 3` — the ⟨Q²⟩ ladder fixed point: exact ⟨Q²⟩ across four rungs of
  (L, β) doubling/quadrupling, flat line. Cheap figure, strong argument.

### 3.2 Diffusion on the torus of angles
Forward process = exact heat kernel on the circle (wrapped Gaussian); denoising
score matching objective; note that the exactness of the forward kernel is
special to U(1) and is *not* available non-abelian — this foreshadows §7.

### 3.3 Gauge-covariant score network
Curl-head parameterization; equivariance by construction rather than by
augmentation; conditioning on the coarse configuration.

- `[NEW] Fig 4` — architecture diagram, curl head highlighted.
- Optional: equivariance residual under random gauge transformations
  (machine-precision), from `29_verify_identities.py`. Could be a table row
  instead of a figure.

### 3.4 Topology transport: the part local learning cannot do
The three mechanisms — coarse-charge enforcement via the instanton shift,
blocking-consistency guidance with the derived width λ(σ) = 8σ², and
rethermalization under the no-topological-moves honesty convention.

**This is the subsection that motivates §5**, so make the structural argument
here: a local score with a finite receptive field cannot control a global
integer, and the degradation is quantitative.

- `[NEW] Fig 5` — raw (projection-off) Q-match rate vs volume: 0.484 (L=16),
  0.234 (L=32), 0.094 (L=64), halving per 4× volume, with the extrapolation to
  L=128 marked. Data: `out/u1_2d/charge_freezing_L64/`. **This is one of the
  most persuasive figures in the paper** — it converts "we needed transport"
  from an engineering excuse into a measured scaling law.
- `[NEW] Fig 6` — sector-change fraction vs σ during reverse sampling, showing
  σ_freeze ≈ 0.304 / 0.312 / 0.307 flat across a 16× range in volume; annotate
  the deployed threshold. Data: `out/u1_2d/charge_freezing/`.

---

## 4. Observable-level validation (what conventional grading says)

### 4.1 Protocol
Two seeds per case, per-chain error bars, z against exact character-expansion
references, raw pre-enforcement topology whenever the model itself is graded.

### 4.2 Results across the campaign
38 cases, β = 1.49 → 872.8 (15× beyond the training max of 60), L up to 128
(64× the training area). Plaquette to ~2 parts in 10⁴.

**Report the z-distribution, not a pass count** — mean(z) = −0.17 ± 0.16 and
std(z) = 1.01 on the plaquette, 1.26 on W(2×2). Introduce this discipline here
so §6 can use it.

**Figures:** mostly already exist.
- `04_matched_scan.png` — matched (L, β) scan.
- `05_mismatch_scan.png` — deliberate coarse/fine mismatch.
- `06_size_scan.png` — volume scan.
- `13_beta_scan.png` — β dependence.
- `08_case_low.png`, `09_case_high.png`, `10_case_extrapolation.png`,
  `11_case_L64.png` — representative per-case observable panels. Pick two for
  the main text (the extrapolation case and L = 64) and put the rest in the
  appendix.
- `01_ladder_drift.png`, `03_ladder_rung_L64.png` — ladder stability.
- `[NEW]` z-histogram across all cases/observables with the unit normal
  overlaid. This is the figure that makes point 1 of the protocol concrete.

### 4.3 Where the agreement starts to fray
std(z) grows with loop extent (≈1.3 at W(4×4) → ≈1.4 at W(10–12), max |z|
3.3 → 4.5); beyond-3σ counts 1/114 on {plaquette, W2×2, W4×4} against 24/760
over the full observable set — an order-of-magnitude excess. Flag it here, pay
it off in §6.

- `[NEW] Fig 7` — std(z) and max|z| vs Wilson loop area. Small, cheap, and it
  is the observable-side shadow of the density gap. Consider making this a
  main-text figure even though it is a "negative" result.

---

## 5. Instanton updates and the classical baseline

This is where the paper earns the right to make a cost claim. The single most
important framing decision: **the baseline is HMC + exact winding update, not
plain HMC and not PTBC.** Say why in the first paragraph.

### 5.1 The winding (instanton) update
Definition of the smooth instanton field carrying exactly ΔQ = ±1, its
gauge-covariant construction, the Metropolis accept/reject that makes it exact,
and its cost (1–18% over plain HMC).

- `[NEW] Fig 8` — the instanton field itself: plaquette-angle heat map of a
  ΔQ = +1 shift, showing the uniform 2πΔQ/V strain. Helps readers who have not
  seen the construction.

### 5.2 Plain HMC is frozen; the winding update is exact and nearly free
Table S8 material, L = 32, 3000 trajectories:

| β | plain HMC | HMC + winding | tuned PTBC | open BC |
|---|---|---|---|---|
| 14.15 | frozen, ⟨Q²⟩ = 0 | 1.8705 vs exact 1.9040, τ_int 2.85 | 1.8742, 3.14 s/indep | 4.42, different observable |
| 55.02 | frozen | 0.4791 vs 0.4743, τ_int 1.20 | 0.5247, 10.87 s | 3.05 |
| 218.58 | frozen | 0.0296 vs 0.0290, τ_int 1.39 | 0.0375, 21.34 s | 2.77 |

Cost of one *independent* configuration: 0.124 / 0.090 / 0.198 s for
`hmc+inst`. That is the number every cost claim in the paper is measured
against.

- `[NEW] Fig 9` — s per independent configuration vs β, four arms
  (hmc = ∞, hmc+inst, tuned PTBC, open), log scale. One figure carries this
  entire subsection.
- `[NEW] Fig 10` — Q(t) traces side by side: frozen HMC vs HMC+winding at
  β = 218.58. Visual counterpart to Fig 9.

### 5.3 Why PTBC is the wrong baseline for this theory
PTBC manufactures a global topological move for theories that lack one; 2D
U(1) has an exact one. A properly tuned ladder (swap acceptance 0.68–0.98,
τ_int ≈ 3) still costs 25–121× more. Include this — it is a genuinely useful
negative for the field, and it pre-empts the obvious referee request. Include
the honest note that Hasenbusch's hierarchical local updates are not
implemented, so this is unoptimized PTBC.

- `[NEW] Fig 11` — swap acceptance matrix / ladder diagnostic for the tuned
  run, demonstrating it is not a strawman. Appendix-grade.

### 5.4 The instanton shift *inside* the pipeline
Distinguish clearly from §5.1: same mathematical object, different role — there
it is a Metropolis proposal in an exact chain, here it is a deterministic
projection applied during late sampling. Report raw pre-enforcement topology
(charge-match rate 0.21, raw ⟨Q²⟩ excess growing with volume: 1.7–2.7 at
L ≤ 32 to 7.1–28.2 at L = 64/128) and be explicit that enforcement supplies the
difference and that the mechanism's availability is theory-dependent.

- `07_raw_topology.png` — raw topology, pre-enforcement.
- `02_ladder_topology.png` — topology along the ladder.
- `20_mismatch_exact_sectors.png` — exact-sector production mode.
- `[NEW] Fig 12` — raw vs enforced P(Q) against exact P(Q), side by side, at
  one strong coupling. The honest version of the histogram everyone else
  publishes.

### 5.5 Head-to-head cost and the seeded mode
- Diffusion pipeline: flat ~2.4 s/configuration at every coupling.
- Classical entry cost: ~28 min burn-in to pass at β = 55; never passes at
  β = 218.6 (Table S1).
- **Charge the generative arm its entry cost**: 8820 s one-time (21.7 min data
  + 125.3 min training), which exceeds every classical burn-in that converges.
  The defensible claim is about *scaling* (flat in β vs. diverging), not about
  being cheaper outright. State the break-even configuration count against
  `hmc+inst` at β = 218.58 explicitly.
- The seeding result: diffusion supplies the thermalized start, a seconds-long
  instanton-HMC tail supplies correctness. P(Q) χ² p-value 0.0005 → 0.43 in
  6 seconds.

**Figures:** these largely exist and are strong.
- `17_headtohead_cost.png` — the central cost figure.
- `18_entry_cost.png` — entry cost vs quality.
- `12_timescales.png`, `16_autocorrelation_modes.png` — autocorrelation.
- `14_relaxation_mid.png`, `15_relaxation_high.png` — relaxation from a
  diffusion seed.
- `21_pq_tail_mismatch.png`, `22_pq_tail_L64.png` — the seeding recovery.
- `26_three_way.png` — three-way comparison.
- `[NEW]` break-even plot: cumulative cost vs number of configurations, three
  lines (hmc+inst, pipeline with entry cost amortized, pipeline marginal),
  crossing point annotated. Referees will ask for exactly this.

---

## 6. Observable agreement does not certify the measure

The paper's second contribution and, arguably, its more durable one. Structure
it as a measurement followed by a falsification chain, not as a caveat section.

### 6.1 The standard check degenerates
Self-normalized ESS sits at exactly 1/N — the estimator's floor, not a
measurement. It cannot distinguish a 10-nat gap from a 100-nat one. State the
reporting rule: never quote a saturated ESS as a number.

- `19_ess_weights.png` — log-weight distributions.
- `23_ess_progress.png` — ESS across the program.

### 6.2 Measuring the gap directly
The free-energy identity E_q[log w] − ΔF = −KL(q‖p) turns the certificate into
a measurement in nats/site that survives weight degeneracy. Result: **1.10
nats/site at L = 16, β = 55 and 1.70 at L = 32, β = 218.6** (565 and 3473 nats
per configuration). Report mean (bulk offset) and spread (reweighting
usability) separately.

- `[NEW] Fig 13` — KL per site vs case, with the ~0.005 nats/site bar that
  importance-sampling exactness would require drawn as a horizontal line. The
  two-order-of-magnitude gap is the result.

### 6.3 The dissociation
Same ensembles: plaquette to 2 parts in 10⁴, density off by ~1 nat/site.
Explain why these are consistent (low-order gauge-invariant observables are a
very low-dimensional projection of a 2L²-dimensional measure) and where the
residual becomes visible (extended observables, §4.3).

- `28_dissociation.png` — the money figure of this section. Consider promoting
  it to the paper's *lead* figure; it is the single image that states the
  thesis.
- `27_program_optimum.png` — supporting.

### 6.4 The falsification chain
Six interventions, each with an identified mechanism: sampling-time knobs,
maximum-likelihood fine-tuning at two capacities, single- and multi-case
reverse-KL, capacity/data scaling, per-level SMC, surrogate-bridge AIS.

**The closure argument matters more than the list.** Two things to state
carefully:
- The within-arm R²_c decomposition: ≤6% of fiber log-weight variance is
  coarse-explainable, and a matching residual is a c-only function, so it can
  land nowhere else. The gap is fine-side model error. (The Villain
  exactly-matched arm corroborates but is confounded — say so; the honesty is
  worth more than the cleaner story.)
- AIS reaches its derived floor in 8 of 10 seeds (1.97–2.71× spread reduction
  at the extrapolation case) but does not lift ESS: a validated *mechanism*,
  not a delivered exactness route. The 2 divergent seeds are traced by
  intervention to the surrogate's ridge regularization (held-out σ 2132 → 43.1
  from a floor on the ridge grid alone), not to acceptance or basis width.

- `24_proposal_sweep.png` — sampler-knob sweep.
- `25_finetune_dynamics.png` — fine-tuning dynamics.
- `[NEW] Fig 14` — the falsification chain as a single panel: each intervention
  on the x-axis, resulting log-weight spread (or KL) on the y-axis, with the
  target bar. Turns "we tried six things" into one readable claim.
- `[NEW] Fig 15` — AIS: per-seed spread reduction, 8 converged / 2 divergent,
  colored by selected ridge. Appendix-grade but worth having.

### 6.5 Local diagnostics do not test global correctness
The MALA experiment. High acceptance (ratio ≈ 1 against equilibrium starts)
while ⟨Q²⟩ is **bit-identical before and after in all eight settings** — zero
sector changes across 50 steps × 64 configurations × 8 settings. Acceptance is
a local statement; it says nothing about whether the ensemble is distributed
correctly, and "exactness ensured by MALA" is unsupported by an acceptance rate
however high.

- `[NEW] Fig 16` — two panels: MALA acceptance vs ε for model-start and
  equilibrium-start (nearly identical), beside ⟨Q²⟩ before/after (identical,
  and wrong). The juxtaposition is the argument.

---

## 7. What this implies for the class of method

### 7.1 The design directive
Exactness has to come from Markov-chain machinery wrapped *around* the proposal
— seeded chains, Metropolis tails, structural sector imposition — not from the
proposal's own likelihood. Note that in non-abelian theories the likelihood
route is unavailable in principle, since the forward heat kernel and hence the
score target are themselves approximate.

### 7.2 Which mode the correctness claim attaches to
As deployed, the generation pipeline applies no accept/reject to the proposal:
an observable-validated heuristic, asymptotically exact only in the
retherm → ∞ limit that costs what direct simulation costs. The seeded mode is
asymptotically exact within its sector, with the sector supplied by the
transport identity. These deserve different language.

### 7.3 A reporting protocol
The ten-point protocol, compressed to a boxed list. Strongest items for the
main text: report the z-distribution not a pass count; report dispersion
against observable extent; never quote a saturated ESS; report KL where an
exact free energy exists; include an exactly-matched control arm; charge the
generative arm its entry cost; report raw pre-enforcement topology; say which
mode the claim attaches to.

- `[NEW]` a boxed checklist rather than a figure. Consider making this a table
  with a "cost to compute" column — most items are free given what is already
  measured, and saying so is what will get it adopted.

---

## 8. Related work

### 8.1 The learned coarse-to-fine line
Inverse-RG upscaling, RG-inspired flows, diffusion for gauge theory, and the
classical multiscale-thermalization algorithms they descend from.

### 8.2 A direct comparison scored against the exact answer
The Zhu et al. (arXiv:2410.19602) case at L = 16, β = 7, exact ⟨Q²⟩ = 1.0064:

| arm | ⟨Q²⟩ | ratio to exact | χ² p |
|---|---|---|---|
| exact | 1.0064 | 1.00 | — |
| their HMC (digitized) | 0.0567 | 0.06 | 1.1e−271 |
| their diffusion (digitized) | 2.3715 | 2.36 | 9.3e−128 |
| ours, 8→16 | 1.0859 | 1.08 | 0.41 |

The point to make is structural, not competitive: **a wider Q distribution than
a frozen chain is not evidence of correctness when the correct answer is
available and sits between them.** Both arms reject the exact distribution at
overwhelming significance in opposite directions. Note that the over-production
failure is one our own raw model shows too (raw ⟨Q²⟩ 2.5–5.4× above exact at
strong coupling) — it looks like a property of score-based samplers on this
theory, not a mistake specific to any one pipeline. Label the digitization as
digitization, and label our row as an out-of-range checkpoint use.

- `[NEW] Fig 17` — the four P(Q) histograms on one axis with exact overlaid.
  Handle the framing carefully in the caption; the claim is about methodology,
  not about a competitor.

### 8.3 Positioning
What is novel: the measurement and the protocol. What is not: the ladder, the
equivariant architecture, the diffusion machinery.

---

## 9. Conclusions and outlook

- The sampler works as an instrument and is validated far outside its training
  range at flat marginal cost.
- The measurement says observable validation is a weak certificate: ~1 nat/site
  of density error hides behind four-significant-figure agreement.
- The transferable outputs: the ladder invariant, the topology transport
  machinery, the design directive, and the reporting protocol.
- Outlook: non-abelian (SU(2) as the next rung — trivial π₁, exact heat kernel
  no longer available, single-plaquette curl basis known to be incomplete), and
  4D as the eventual target. Be brief and concrete about what is known to break.

---

## Appendices

- **A. Exact character-expansion references** — formulae and verification.
- **B. Full campaign tables** — the 38-case table, per-observable z, the
  sector-mode comparison (denominator 38, τ_int-aware).
- **C. Instanton-HMC burn-in scan** (Table S1) and non-learned warm starts
  (Table S6b, the prolongator baseline).
- **D. ESS / KL program tables** (S2, S5, S7 series) including the ridge-scan
  intervention.
- **E. PTBC implementation and tuning**, including the defect-length and
  ladder-calibration lessons and the swap-acceptance reporting bug.
- **F. Reproducibility** — identity checks (`29_verify_identities.py`), figure
  provenance (`30_assemble_appendix_figures.py --check`), device conventions,
  checkpoint and data locations.

---

## Notes on figure economy

There are 28 existing appendix figures and roughly 17 suggested new panels.
A main text of 10–12 figures is realistic:

**Suggested main-text set:**
1. Pipeline schematic `[NEW]`
2. Frozen-HMC Q traces `[NEW]`
3. Ladder ⟨Q²⟩ fixed point `[NEW]`
4. Raw Q-match rate vs volume `[NEW]` — the structural argument for transport
5. Observable scan (`04_matched_scan.png` or `13_beta_scan.png`)
6. std(z) vs loop area `[NEW]`
7. s per independent configuration, four arms `[NEW]`
8. Head-to-head / entry cost (`17_headtohead_cost.png`)
9. Seeding recovery (`21_pq_tail_mismatch.png`)
10. Dissociation (`28_dissociation.png`) — candidate lead figure
11. KL per site vs the exactness bar `[NEW]`
12. MALA two-panel `[NEW]`

Everything else goes to the appendix, which already exists in assembled form.
