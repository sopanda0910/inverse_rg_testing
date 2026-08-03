# Supplementary Material — v2 Model

This appendix documents the v2 checkpoint of the diffusion-based inverse-RG
sampler for 2D compact U(1) lattice gauge theory. It addresses four questions:
(1) does the generated ensemble match exact results, inside and far outside the
training range; (2) how does the sampler compare, in wall-clock cost and
correctness, against the strongest classical baseline we could construct
(instanton-update HMC, whose global Q-hop is the volume-independent uniform
Q-shift move); (3) what does a diffusion-generated configuration buy as an HMC
starting point; (4) what an exact-likelihood diagnostic honestly says about
the model as an importance-sampling proposal; and (5) how far sampling-time
tuning and likelihood-aware fine-tuning can close that importance-sampling
gap — including which standard remedies fail, and why.

## Methodology

**The model.** A gauge-covariant score network (invariant plaquette/rectangle
inputs, plaquette-curl output head, per-site channel normalization) is trained
by denoising score matching on wrapped link angles, conditioned on the
2×2-blocked coarse field, over continuous log-uniform couplings β ∈ [1, 60] at
L = 8, 16, 32. Generation runs the reverse process as one inverse-RG step
(coarse β_c at L → fine β_f at 2L, matched so the blocked fine theory
reproduces the coarse one). Relative to the previous (v6) checkpoint, v2 adds:
exact-symmetry data augmentation (90° rotations, reflections, and charge
conjugation θ → −θ, which enforces P(Q) = P(−Q) statistically); oversampling
of small noise levels at high β (targeting the σ-region that resolves the
narrow high-β link distributions); a per-site normalization with no
lattice-size dependence; a global coarse-FiLM channel carrying the coarse
winding sum 2πQ/V to every layer; and a β-gated exact-score blend (analytic
noised-Wilson score as σ → 0, gated off below β ≈ 5).

**Honesty conventions.** All topology results use the strict setting:
rethermalization performs **no** topological (instanton-hop) updates, so the
model plus the deterministic coarse-charge transport must carry the sector —
rethermalization cannot manufacture topology. Raw (pre-enforcement) topology
metrics are quoted where model transport itself is at issue. Error bars are
per-chain time averages (never pooled across time × chain) for HMC series, and
per-config SEM for generated ensembles; z-scores are against the exact
character-expansion values. Two independent seeds were run for the
out-of-sample tracks; all seed-2 results confirmed seed-1 within statistics.

**Sector modes.** The pipeline exposes two topological-sector treatments.
*Transport* (the strict default used above): the fine sector is the coarse
configuration's sector, carried deterministically by the smooth instanton
shift — final P(Q) is the coarse base's empirical histogram, so this mode
measures what the model itself carries, but it cannot retarget topology when
the requested β_f is not the base's matched coupling. *Exact-sector*
(production): the coarse base is first charge-conjugation symmetrized
(C-antithetic: half the batch is mapped θ → −θ, exactly measure-preserving,
enforcing P(Q) = P(−Q) at finite sample size), and each configuration's
sector is then drawn from the exact finite-volume P(Q) at the *target*
coupling and imposed by the same instanton shift. Sector statistics are then
correct by construction at any target — the honest successor to
hop-in-rethermalization, and this pipeline's analogue of Q-shift sector
reconstruction. Wilson observables are statistically identical in the two
modes (mean |plaquette z| 1.77 vs 1.74 over 38 cases).

**Statistical baseline.** Under these conventions the v2 checkpoint matches
exact results across 38 study cases from β_f = 1.49 to 872.8 (15× the training
maximum) and volumes to L = 128 (64× the training area), with topology
transport improved over v6 (mean raw spurious ⟨Q²⟩ excess 5.3 → 2.9; raw
charge-match rate 0.17 → 0.21) at equal Wilson-observable accuracy. In
exact-sector mode the sector statistics are additionally correct by
construction: exact-P(Q) χ² failures drop from 5/35 (all in the mismatch
track and the largest volume) to 1/35 — consistent with the α = 0.05 false
positive rate — and the worst ⟨Q²⟩ deviation from |z| = 11.8 to 2.8.

**Exactness machinery and the ESS-gap program.** Beyond the diagnostic ODE
likelihood of Fig. 19, the pipeline now includes a fully valid exactness
route: sampling the probability-flow ODE itself yields each configuration
*and* the exact density of the process that produced it in one pass (Heun
integration accumulating the Hutchinson divergence along the trajectory), so
the self-normalized importance weights
w = e^(−S_f(x)) e^(+S_matched(c)) / q(x|c) are valid for the actual samples —
both proposal factors are known exactly — and feed asymptotically exact
estimators (SNIS reweighting and an independence-Metropolis chain). The
machinery is validated end-to-end on an exactly solvable wrapped-Gaussian
target (true score, exact divergence: ESS/N > 0.5) and its estimator noise is
bounded by stability controls (8 Hutchinson probes; 240 integration steps).
On this validated footing the remaining weight spread is a measured property
of the score model's density, and Figs. 23–25 with Table S5 document a
systematic program against it: a sampling-time proposal sweep (one free win:
a lower terminal noise floor), two disciplined negative results (maximum-
likelihood fine-tuning through the flow, and single-case reverse-KL), and a
guarded multi-case reverse-KL fine-tune that halves the density gap at every
coupling — including 4× beyond its training range — without sacrificing the
one-checkpoint generality the pipeline is built on. Fine-tuned checkpoints
are used *only* for the likelihood/ESS results in this section; every other
result in this appendix uses the unmodified v2 campaign checkpoint.

---

### Figure 1 — `figures/01_ladder_drift.png`
**Ladder observable drift.** Mean plaquette (and companion observables) at each
rung of the iterated ladder L = 8 → 16 → 32 → 64 (β = 1.35 → 4.0 → 14.15 →
55.02), generated ensemble vs exact. Drift does not accumulate across rungs:
each inverse step is followed by short local rethermalization (16 sweeps,
no Q-hops), which pins the UV before the next doubling.

### Figure 2 — `figures/02_ladder_topology.png`
**Ladder topology.** Topological charge distribution by rung against the exact
finite-volume P(Q). The sector content is inherited from the coarse base — an
L = 8, β = 1.35 ensemble where HMC tunnels freely — and transported
structurally up the ladder, which is how correct ⟨Q²⟩ persists at couplings
where any direct chain is frozen.

### Figure 3 — `figures/03_ladder_rung_L64.png`
**Top rung validation (L = 64, β = 55.02).** Full observable panel at the
ladder's final rung: plaquette and Wilson-loop distributions, Q histogram vs
exact P(Q). This coupling/volume is far beyond anything in training data.

### Figure 4 — `figures/04_matched_scan.png`
**Matched-pair coupling scan (parts A and D).** One inverse step L = 16 → 32
per case over β_f = 1.49–218.58 (matched pairs), generated vs exact:
z-scores stay within the |z| ≤ 2–3 statistical band over more than two decades
of coupling, from a single checkpoint with no per-case tuning.

### Figure 5 — `figures/05_mismatch_scan.png`
**Deliberate mismatch controls (part B).** The conditioning coarse ensemble is
held at β_c = 4 while the target β_f is varied off the matched value. The
model tracks the *requested* coupling — evidence that β-conditioning, not the
coarse input alone, sets the generated physics. Wilson observables pass;
P(Q), by design of the transport mode, remains the β_c = 4 base's sector
histogram, which is *structurally* wrong for the off-matched targets — this
track fails the exact-P(Q) χ² test under pure transport, and is corrected by
the exact-sector mode (Fig. 20) or by a seconds-long instanton-HMC tail
(Fig. 21).

### Figure 6 — `figures/06_size_scan.png`
**Volume transfer (part C).** The same checkpoint applied at L = 64 and
L = 128 (never trained above L = 32); observables against exact values at
β_f = 14.15. The v2 per-site normalization removes the lattice-size dependence
that GroupNorm statistics introduced in earlier checkpoints.

### Figure 7 — `figures/07_raw_topology.png`
**Raw (pre-enforcement) topology transport.** The model-level metric charge
enforcement would otherwise hide: spurious raw ⟨Q²⟩ excess over the coarse
base, per track. v2's symmetry augmentation (charge conjugation ties the ±Q
sectors) cuts the mean excess from 5.3 (v6) to 2.9, with the largest gains at
low β (e.g. +11.3 → +1.5) — under the stricter no-Q-hop rethermalization.

### Figure 8 — `figures/08_case_low.png`
**Representative low-β case (β_f = 3.10, L = 32).** Full validation panel in
the regime where topology fluctuates freely and HMC is healthy — the pipeline
must (and does) reproduce a broad P(Q).

### Figure 9 — `figures/09_case_high.png`
**Representative frozen-regime case (β_f = 218.58, L = 32).** Same panel deep
in the topologically frozen regime (direct HMC: zero tunnelings). ⟨Q²⟩ agrees
with the exact susceptibility; a fresh hot-start HMC ensemble at this coupling
is wrong by two orders of magnitude in the same quantity.

### Figure 10 — `figures/10_case_extrapolation.png`
**Extrapolation frontier (β_f = 872.8, L = 32).** Fifteen times the training
maximum. Wilson observables pass against exact values. For topology, exact
⟨Q²⟩ ≈ 9·10⁻⁴ while every generated configuration has Q = 0: the sample
variance of Q² is then exactly zero and the z-score is ill-defined (the
verdict tables record it as +inf for this reason) — the meaningful statement
is that with expected nonzero-charge count n·⟨Q²⟩ ≪ 1 at this ensemble size,
an all-zero sample is the modal outcome under the exact P(Q); the sector
content matches exact expectations rather than being merely "consistent".

### Figure 11 — `figures/11_case_L64.png`
**Joint coupling + volume extrapolation (β_f = 218.58, L = 64).** The hardest
case in the study: 4× the training coupling and 4× the training area
simultaneously.

### Figure 12 — `figures/12_timescales.png`
**Thermalization timescales.** Per coupling: t_therm of an HMC chain started
from a raw diffusion sample (no rethermalization applied — every sweep the
seed needs is charged here), the equilibrated chain's own sampling interval
2τ_int, and fresh hot/cold-start burn-in. Seeds thermalize in 0–13
trajectories in 24 of 29 cases — below the interval, i.e. cheaper than the
chain's marginal cost per config; fresh hot chains never thermalize above
β ≈ 8.8.

### Figure 13 — `figures/13_beta_scan.png`
**Thermalization across the β scan.** The same three quantities as a function
of β_f: the ordering t_therm(seed) < 2τ_int < burn-in(fresh) sets in at
moderate coupling and widens as standard HMC slides into critical slowing
down and topological freezing.

### Figure 14 — `figures/14_relaxation_mid.png`
**Relaxation curves, β_f = 55.02 (L = 32).** Ensemble-mean observable traces
for the three starting points with exponential fits and |z| ≤ 2 bands. The
diffusion seed starts at its plateau (no measurable decay — the desired
outcome); hot and cold starts relax over hundreds of trajectories or not at
all.

### Figure 15 — `figures/15_relaxation_high.png`
**Relaxation curves, β_f = 218.58 (L = 32).** Same as Fig. 14 at the frozen
regime's deep end: fresh chains never reach tolerance within the 640-trajectory
budget; the seeded chain is indistinguishable from equilibrium within a few
trajectories.

### Figure 16 — `figures/16_autocorrelation_modes.png`
**Fast vs slow modes.** Normalized autocorrelation Γ(δ) of Wilson observables
(fast modes) against the topological charge (slow mode) on equilibrated
windows. Wilson-loop correlations decay within ~10 trajectories while Γ_Q
stays pinned at 1 — the frozen-topology signature; nothing in the seeded
continuation depends on Q mixing afterward, since the sector is transported,
not evolved.

### Figure 17 — `figures/17_headtohead_cost.png`
**Head-to-head vs instanton HMC: marginal cost and correctness (L = 32,
burn-in 500, 128 configs/batch).** Instanton HMC — the strongest classical
baseline; its Q-hop keeps tunneling to β = 256 where standard HMC froze at 16 —
is far cheaper per config where it is correct (~0.01 s vs ~2.4 s), but open
markers show it failing exactness (Wilson observables, up to 16.6σ) at
β ≥ 55: its topology moves work, its UV does not thermalize. The diffusion
pipeline passes everywhere at flat cost.

### Figure 18 — `figures/18_entry_cost.png`
**Entry cost vs β — the head-to-head's decisive plot.** Burn-in wall-clock
required before the instanton-HMC ensemble agrees with exact results: 8 s
(β = 4.4), 16 s (β = 14.1), 1677 s (β = 55, needing 8000 trajectories), and
*never within the tested budget* at β = 218.58 (7.2σ off after 8000
trajectories / 2534 s). The diffusion pipeline has no burn-in; its per-config
cost is flat (~2.3–2.8 s) across the same range. The baseline's entry cost
grows ~200× over one decade of β and then stops converging; the generative
cost does not.

### Figure 19 — `figures/19_ess_weights.png`
**Exact-likelihood diagnostic (honest negative).** Importance weights
w = e^(−S)/q from the probability-flow ODE likelihood (Hutchinson divergence,
validated on an exactly solvable wrapped-Gaussian case), with the coarse-level
density divided out via the matched-coupling action. The per-site weight
spread is small (0.03–0.09 nats) but multiplies with volume, so ESS/N sits at
the 1/N floor at L = 32 — with the guidance term on or off, locating the gap
in the score model's own density. The pipeline's correctness therefore rests
on structural charge transport, rethermalization, and observable-level
validation rather than reweighting; flow-based samplers with ESS/N ≈ 0.5–0.7
hold that ground, while this pipeline's advantages are flat-cost seeding,
extrapolation reach, and one-checkpoint generality. Closing the ESS gap would
require likelihood-aware training — attempted systematically in Figs. 23–25
and Table S5.

### Figure 20 — `figures/20_mismatch_exact_sectors.png`
**Mismatch controls in exact-sector mode.** The part-B scan of Fig. 5 rerun
with C-antithetic base symmetrization and sectors resampled from the exact
finite-volume P(Q) at each *target* coupling. Every χ² failure of the
transport mode (B_bt6: p = 0.0005 → 0.43; B_bt30: 0.0000 → 0.94;
B_bt55: 0.005 → 0.77; B_bc2_bt8: 0.03 → 0.32; and C_L128: 0.005 → 0.39)
passes; Wilson observables are unchanged. Sector content is no longer
inherited from the (deliberately wrong) base — it is drawn where the target
theory says it should be.

### Figure 21 — `figures/21_pq_tail_mismatch.png`
**Sector re-equilibration by an instanton-HMC tail (B_bt6, L = 32,
β_f = 6).** The seeding claim, topologically: starting from the *transported*
ensemble — whose P(Q) is the mismatched β_c = 4 base's histogram,
χ² p = 0.0005 — a 200-trajectory HMC continuation with the instanton Q-hop
restores ⟨Q²⟩ = 5.2 vs exact 4.78 (p = 0.43) in 6 seconds of wall clock.
Left: P(Q) before/after vs exact; right: the ⟨Q²⟩ trajectory relaxing onto
the exact line within tens of trajectories. The diffusion batch supplies the
expensive part (thermalized UV at the target coupling); the topologically
mixing tail is essentially free.

### Figure 22 — `figures/22_pq_tail_L64.png`
**Instanton-HMC tail at larger volume (C_L64, β_f = 14.15, L = 64).** Same
before/after construction on the size-scan rung: the tail moves the
transported histogram onto the exact P(Q) (χ² p 0.07 → 0.70) in 19 seconds,
demonstrating the tail's cost stays trivial as the volume grows (the Q-hop's
ΔS ≈ 2π²β/V is volume-independent).

### Figure 23 — `figures/23_ess_progress.png`
**The ESS-gap program across couplings.** Fiber-corrected log-weight spread —
now measured with *valid* weights (probability-flow ODE sampling returns each
configuration with its own density; fresh seeds, n = 64) — for each
checkpoint variant, absolute (left) and per site in nats (right). Three
results in one frame. (i) The spread grows ∝ βV under the baseline: a small,
nearly uniform per-plaquette density offset, not topology (sector action
differences are O(2π²β/V) ≈ 4 nats against spreads of 10²–10³) and not
estimator noise (Fig. 24's stability controls). (ii) The two standard
remedies *go backwards*: maximum-likelihood fine-tuning through the flow
degrades every case despite improving its own validation metric (Fig. 25a),
and single-case reverse-KL explodes the never-trained extrapolation coupling
to std ≈ 2202 while merely recovering knob-level at its own coupling.
(iii) The guarded multi-case reverse-KL (rkl2) roughly halves the spread at
*every* case — 16:55: 42 → 19.7; 32:218.6: 164 → 103 — including the
extrapolation monitor it never trained on. ESS/N nonetheless remains at the
1/N floor throughout: self-normalized weights need total spread of O(1–3)
before ESS lifts off, so an order of magnitude remains; the honest reading is
a halved density gap with a quantified remainder, not a solved problem.

### Figure 24 — `figures/24_proposal_sweep.png`
**Sampling-time proposal sweep (13 points, L = 16, β_f = 55.02).** The
deployed proposal is a family parameterized by sampling-time knobs, and every
member yields valid weights, so ESS can be tuned with no retraining. The one
free win: lowering the terminal noise floor (σ_min coefficient 0.1 → 0.03)
takes the spread 27 → 24 and ESS/N 0.030 → 0.031 — consistent with the
endgame-offset picture, since the ODE stops at σ_min while the weights
compare against σ = 0. The clearest negative: *strengthening* the exact-score
blend monotonically worsens the density (blend 4: std 128), i.e. the harmonic
β_eff approximation is a worse mid-σ density than the learned score — the
blend earns its keep only in the σ → 0 endgame it was designed for. The two
stability controls (8 Hutchinson probes; 240 integration steps) sit at the
baseline spread, pinning the spread on the model rather than the estimator.

### Figure 25 — `figures/25_finetune_dynamics.png`
**Why the negative results are negative, and how the positive one was
selected.** (a) The ML fine-tune (FFJORD-style, warm-started, 300 steps)
raises held-out log q/dof from −0.887 to −0.520 by step 75 — ≈ 190 nats per
configuration — yet its best-validation checkpoint *worsens* deployed spread
at every coupling (Fig. 23): maximum likelihood raises the density on *data*
configurations, but the weights probe the density on the *model's own
samples*; forward-KL improvement bought reverse-KL degradation, making
validation likelihood the wrong selection metric for this purpose. (b) The
multi-case reverse-KL run internalizes that lesson: round-robin training over
three (L, β) cases, evaluation on rotating disjoint coarse slices with
rotating seeds (no fixed-set selection), and checkpointing gated on two
conditions — mean training-case ESS improvement *and* an extrapolation
monitor (L = 32, β = 218.6, never trained on) staying below 1.5× its initial
spread. The guard blocked four of six save opportunities, including the
step-100 state with the highest training ESS; the surviving step-250
checkpoint is the one that generalized in fresh-seed verification.

### Figure 26 — `figures/26_three_way.png`
**The closing three-way verdict (L = 32).** (a) HMC trajectories until
thermalization for three starting points across the matched-β scan: hot-start
plain HMC never thermalizes for β ≳ 10; cold-start needs hundreds of
trajectories and its topology is frozen solid for β ≳ 8.8 (zero tunnelings in
321 × 32 trajectories, shaded region) — so plain HMC produces ensembles whose
⟨Q²⟩ is silently wrong across the entire upper scan; a diffusion-generated
seed thermalizes in 0–13 trajectories at every coupling to β = 872.8.
(b) Marginal cost per independent configuration for the two survivors:
instanton-HMC is cheapest per configuration where it works, but its ensembles
fail the exactness gates at β ≥ 55 until the entry cost explodes (Fig. 18,
Table S1: ~28 min of burn-in to pass at β = 55; never passes at β = 218.6),
while the diffusion pipeline — including rethermalization — stays flat at
~2.4 s/config with filled (exact-agreeing) markers throughout. This is the
pipeline's claim in one figure: not a universal replacement for HMC, but the
only sampler of the three that remains both available and correct in the
frozen regime.

### Figure 27 — `figures/27_program_optimum.png`
**The ESS program at its measured optimum.** (a) Every model-quality
intervention of the exactness program, chronological, at the reference case
(L = 16, β = 55, fresh-seed verification): the σ_min knob and the guarded
multi-case reverse-KL are the two keepers (42 → 24 → 19.7); ML fine-tuning,
single-case reverse-KL, the 3.7× capacity/data scale-up, and the 354-parameter
correction head (2–6× worse on its disjoint grid; omitted for scale) all went
backwards and were discarded by the guard protocol. (b) The quantified end
state: per-site density gap of the final checkpoint across the full (L, β)
plane — 0.02–0.07 nats/site, uniformly 4–10× above the ~0.005 bar at which
self-normalized weights would become usable. The program is closed at its
optimum: rkl2 + σ_min 0.03, with the remainder characterized rather than
conjectured.

---

## Table S1 — Instanton-HMC burn-in scan (entry cost vs quality, L = 32)

| β_f | burn-in (traj) | max Wilson \|z\| | quality | entry cost (s) | diffusion s/config |
|---|---|---|---|---|---|
| 4.44 | 500 | 2.5 | pass | 8 | 2.28 |
| 14.15 | 500 | 1.7 | pass | 16 | 2.39 |
| 55.02 | 500 | 7.1 | fail | 31 | 2.37 |
| 55.02 | 2000 | 3.3 | fail | 328 | — |
| 55.02 | 8000 | 1.1 | pass | 1677 | — |
| 118.5 | 500 | 9.4 | fail | 42 | 2.76 |
| 218.58 | 500 | 16.6 | fail | 58 | 2.55 |
| 218.58 | 2000 | 7.8 | fail | 605 | — |
| 218.58 | 8000 | 7.2 | fail | 2534 | — |

Production window 640 trajectories × 32 chains throughout; quality = all
Wilson-observable |z| ≤ 2.5 vs exact. Instanton-HMC ⟨Q²⟩ is correct in every
row (the Q-hop works); the failures are UV thermalization.

## Table S2 — Probability-flow ODE ESS (raw model transport)

| L | β_f | ESS/N (fiber-corrected) | log-w spread per site (nats) |
|---|---|---|---|
| 16 | 14.15 | 0.016 | 0.078 |
| 16 | 55.02 | 0.016 | 0.078 |
| 32 | 55.02 | 0.016 | 0.035 |
| 32 | 218.58 | 0.016 | 0.074 |

Guidance-off control: 0.019–0.021 at L = 16, 0.016 at L = 32 — statistically
identical, attributing the gap to the score model rather than the guidance.

## Table S3 — Sector-mode comparison (38-case study, same checkpoint and seeds)

| metric | transport | exact-sector |
|---|---|---|
| exact-P(Q) χ² failures (p < 0.05) | 5/35 | 1/35 |
| … of which mismatch track (B) | 4 | 0 |
| worst \|z(⟨Q²⟩ vs exact)\| | 11.8 | 2.8 |
| cases with \|z(⟨Q²⟩)\| > 2 | 13 | 3 |
| significant ⟨Q⟩ asymmetry (\|z\| > 2) | 0 | 0 |
| mean \|plaquette z\| (38 cases) | 1.77 | 1.74 |

The exact-sector residuals are at the multiple-testing false-positive rate
(≈ 1.75 expected at α = 0.05 over 35 tests). χ² is computable for 35 of 38
cases; the three deep-frozen cases (exact ⟨Q²⟩ ≲ 10⁻³) have no populated
bins to test.

## Table S4 — P(Q) before/after a 200-trajectory instanton-HMC tail

| case | L | β_f | ⟨Q²⟩ before | after | exact | χ² p before | after | tail (s) |
|---|---|---|---|---|---|---|---|---|
| B_bt6 | 32 | 6 | 1.92 | 5.20 | 4.78 | 0.0005 | 0.43 | 6 |
| A_bc1.5 | 32 | 4.44 | 5.10 | 6.88 | 6.79 | 0.87 | 0.24 | 6 |
| E_bc11.8 | 32 | 43.6 | 0.44 | 0.54 | 0.58 | 0.31 | 0.96 | 16 |
| D_bc55.02 | 32 | 218.6 | 0.031 | 0.039 | 0.029 | — | — | 41 |
| C_L64 | 64 | 14.15 | 6.43 | 10.4 | 7.62 | 0.07 | 0.70 | 19 |

Tails run on the transport-mode ensembles (the harder starting point). The
frozen-regime row (β_f = 218.6) has too few populated Q bins for a χ² test;
its ⟨Q²⟩ stays consistent with exact. All tails cost seconds — negligible
against either arm of the head-to-head in Table S1.

## Table S5 — ESS-gap program: fiber log-weight std by checkpoint variant

| variant | L16 β14.1 | L16 β55.0 | L32 β55.0 | L32 β218.6 |
|---|---|---|---|---|
| v2 checkpoint, ladder knobs | 17.9 | 42.1 | 84.3 | 163.7 |
| v2 checkpoint, σ_min-coef 0.03 (knob only) | — | 24.0 | — | — |
| + ML fine-tune (best-val, step 75) | 29.0 | 41.3 | 131.8 | 293.6 |
| + single-case reverse-KL | 23.9 | 24.1 | 75.1 | **2202** |
| multi-case reverse-KL (rkl2, guarded) | **15.1** | **19.7** | **40.8** | **102.6** |
| big net (hidden 80, +24 L=32 rungs), DSM | 19.7 | 31.6 | 49.6 | 211.9 |
| rkl2 + 354-param correction head (best-val) | worse 2–6× on its disjoint grid (8:8 → 17.7 vs 7.5; 16:25 → 105.8 vs 18.1; 32:14.1 → 155.5 vs 42.0) | | | |

All rows are fresh-seed verification runs with valid weights (probability-flow
ODE sampling, n = 64, 120 steps, 2 Hutchinson probes, σ_min-coef 0.03 except
the ladder-knobs row at 0.1). ESS/N sits at the 1/64 floor in every row
except the knob-only point (0.031): the total spread must reach O(1–3) before
self-normalized ESS lifts off, so the halving delivered by rkl2 is real but
insufficient — roughly an order of magnitude remains. Training cost of rkl2:
300 warm-started optimizer steps, ≈ 80 min on the laptop CPU; the campaign
checkpoint itself is unmodified, and only this section's likelihood/ESS
results use the fine-tuned variants. Full provenance:
`out/diffusion_v2/ess_chain/` (chain logs, per-stage sentinels, chosen
knobs, verification JSONs) and `scripts/19–26`.

**Program closure (2026-08-02).** The exactness program is closed at
rkl2 + σ_min-coef 0.03 — the measured optimum. The complete falsification
chain — sampling-time knobs (one win), data-side maximum-likelihood
fine-tuning at 197k and at 354 parameters (both degrade deployment: the
forward/reverse-KL asymmetry is intrinsic to the objective, not a capacity
effect), single-case reverse-KL (destroys extrapolation), guarded multi-case
reverse-KL (the one 2× win, then plateau), capacity/data scaling under DSM
(helps only in-distribution, costs extrapolation), and per-level SMC
restructuring (no weight diversity to harvest) — leaves the per-site density
gap at 0.02–0.07 nats/site against the ~0.005 usable-certificate bar
(Fig. 27b). Exactness for this pipeline therefore rests, by measurement
rather than assumption, on the Markov-chain route — rethermalization,
instanton-HMC tails, exact-sector resampling — wrapped around the generative
proposal: the architecture the head-to-head, seeding, and three-way results
(Figs. 17, 18, 21, 22, 26) validate directly, and the design carried forward
to the non-abelian successor (`su2_2d/`).
