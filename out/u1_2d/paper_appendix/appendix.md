# Supplementary Material — v2 Model

This appendix documents the v2 checkpoint of the diffusion-based inverse-RG
sampler for 2D compact U(1) lattice gauge theory. It addresses five questions:
(1) does the generated ensemble match exact results, inside and far outside the
training range; (2) how does the sampler compare, in wall-clock cost and
correctness, against the strongest classical baseline we could construct
(instanton-update HMC, whose global Q-hop is the volume-independent uniform
Q-shift move); (3) what does a diffusion-generated configuration buy as an HMC
starting point; (4) what an exact-likelihood diagnostic honestly says about
the model as an importance-sampling proposal; and (5) how far sampling-time
tuning and likelihood-aware fine-tuning can close that importance-sampling
gap — including which standard remedies fail, and why.

## What this appendix establishes

The sampler is the *instrument*, not the claim. Learned coarse-to-fine maps
for lattice field theory are an established line — inverse-RG upscaling of
configurations, RG-inspired coarse→fine flows, diffusion models for gauge
theory, and the classical multiscale-thermalization algorithms they descend
from. What that line has not done is ask whether the generated ensemble is
the Boltzmann distribution. It is validated on observables: critical
exponents, Wilson loops, topological susceptibility. Incorporating numerical
exactness into inverse-RG methods is named as open work in that literature.

This appendix answers it, for a sampler that passes conventional validation
by a wide margin. Four results:

1. **A way to measure distributional correctness when ESS is uninformative**
   (§ *Measuring the gap*). Self-normalized ESS is the usual check and it
   degenerates here — ESS/N sits at exactly 1/N, which is the estimator's
   floor, not a measurement, and cannot distinguish a 10-nat gap from a
   100-nat one. The free-energy identity converts the same weights into a
   *direct* KL readout in nats/site, which stays finite and informative after
   ESS has bottomed out.
2. **The measurement.** ≈ 1.10 nats/site at L = 16, β = 55 and 1.70 at
   L = 32, β = 218.6 — i.e. 565 and 3473 nats per configuration, from the
   free-energy identity on the deployed checkpoint
   (`out/u1_2d/ode_reweighting/`).
3. **The dissociation, and where it becomes visible**
   (§ *Validation sharpness*). The same ensembles reproduce the plaquette to
   two parts in 10⁴. The two facts are consistent because low-order
   gauge-invariant observables are a very low-dimensional projection of a
   2L²-dimensional measure — and the residual *is* detectable once one looks
   at extended observables, where the z-dispersion grows monotonically with
   loop area. Short-distance agreement does not certify the measure.
4. **A falsification chain rather than a shrug.** Six interventions —
   sampling-time knobs, maximum-likelihood fine-tuning at two capacities,
   single- and multi-case reverse-KL, capacity/data scaling, per-level SMC,
   and surrogate-bridge AIS — converged, with a mechanism identified for each
   (§ *Exactness endgame*, Tables S5–S7). The one control that could have
   explained the gap away, an exactly-matched action arm, eliminates it
   (Table S6): the gap is fine-side model error.

The practical consequence is stated in *Scope of the claim* below and
validated by Figs 17, 18, 21, 22 and 26: correctness for this class of
sampler has to come from Markov-chain machinery wrapped around the proposal
— seeded chains, Metropolis tails, structural sector imposition — not from
the proposal's own density. A recommended protocol for reporting all of this
is given at the end.

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

**What "correct" means here (scope of the claim).** The deployed pipeline
applies **no accept/reject step to the generated proposal**: the only
Metropolis moves are inside the local rethermalization sweeps and the
instanton Q-hop. Sixteen local sweeps *reduce* the proposal's bias; they do
not remove it, and local updates relax long-wavelength modes slowest. The
generation pipeline is therefore a **validated heuristic**, asymptotically
exact only in the rethermalization → ∞ limit — which costs what direct
simulation costs. Two claims must be kept apart, and are throughout:

- *Graded on observables* (this appendix's actual claim): the generated
  ensembles reproduce gauge-invariant observables against exact values to the
  precision quoted. Quantified below, including the residual bias.
- *As a measure* (not claimed): the generated ensemble is demonstrably **not**
  a sample from the target — the measured density gap is ≈ 1–1.7 nats/site,
  i.e. 565 nats per configuration at L = 16, β = 55 and 3473 at L = 32,
  β = 218.6.
  Observable agreement and distributional correctness are different
  statements, and only the first is established.

The conceptually exact mode is *seeding*: an HMC chain started from a
diffusion configuration is asymptotically exact **within its sector**, with
the sector supplied by transport (Figs 12–16, 21, 22, 26). That is the mode
the head-to-head and three-way results validate directly.

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
modes (mean |plaquette z| **vs the HMC reference** 1.77 vs 1.74 over 38
cases; against the exact character expansion, which is the convention used
everywhere else in this appendix, 1.06 vs 1.08).

**Why sector transport is exact, not approximate.** With β_f = 4β_c and
L_f = 2L_c the exact finite-volume ⟨Q²⟩ ≈ V/(4π²β) is *invariant* along the
ladder: for Villain the exact values over four rungs are 1.20271 → 1.20334 →
1.20334 → 1.20334. The ladder multiplies V and β by 4 simultaneously, so the
coarse ensemble's P(Q) **is** the fine theory's P(Q) — transport is an
identity, not an approximation that happens to work. Equivalently, climbing
the ladder is a continuum-limit trajectory at fixed physical volume, which is
what the endpoint (L = 64, β = 55) should be read as: the same physical
system resolved 8× finer than the base. The campaign's measured-matching
ladder inherits this to 4% (1.986 → 1.934 → 1.904 → 1.903), the drift sitting
in the first, strongest-coupling step where tree level is worst.

The identity is a statement about the *target distribution*, and it should not
be read as a statement about the model. The two are separated by the
measurements: the raw charge-match rate is 0.21, transport-mode worst
|z(⟨Q²⟩)| is 11.8, and the raw Q² excess grows with volume (1.7–2.7 at
L ≤ 32 to 7.1–28.2 at L = 64/128). So the correct sector *distribution* is
known exactly, while the model does **not** faithfully carry an individual
configuration's charge across the step. That is precisely why the sector is
imposed structurally (C-antithetic symmetrization plus resampling from the
exact finite-volume P(Q) at the target coupling) rather than trusted to the
network: the model is asked for a thermalized UV at the target coupling, not
to act as a topological transport operator. The division of labour is
deliberate, and only one half of it is exact. Its cost is a genuine
limitation — the structural route consumes the exact P(Q) this solvable theory
supplies, which a 4D non-abelian target will not.

**Statistical baseline.** Under these conventions the v2 checkpoint matches
exact results across 38 study cases from β_f = 1.49 to 872.8 (15× the training
maximum) and volumes to L = 128 (16× the largest training area, 64× the
smallest), with topology transport improved over v6 (mean raw spurious ⟨Q²⟩
excess ≈ 5 → 2.9 — both means taken **excluding the volume-scaling track C**,
whose excess of 28.15 dominates any pooled average; over all 38 cases the v2
mean is 4.01) and raw charge-match rate 0.17 → 0.21, at equal
Wilson-observable accuracy. In
exact-sector mode the sector statistics are additionally correct by
construction: exact-P(Q) χ² failures drop from 5/35 (all in the mismatch
track and the largest volume) to 1/35 — consistent with the α = 0.05 false
positive rate — and the worst ⟨Q²⟩ deviation from |z| = 11.8 to 2.8.

**Validation sharpness and the residual bias (added 2026-08-03).** The
"matches exact" statement above is an *upper bound on bias*, and the bound is
tight: with n = 64–128 configs per case the median relative SEM on ⟨cos θ_p⟩
is 0.0087%, so |z| > 2 detects a relative plaquette bias of **0.017%** — two
parts in 10⁴. Three residual features are visible at that precision and are
reported here rather than left implicit (all computed on `z_exact`, which
uses only the generated-ensemble error, the exact value being noiseless):

- *A weak negative offset, no longer significant.* 14 of the 20 Wilson-type
  observables have mean z < 0, and the leading ones are consistent with zero:
  plaquette −0.174 ± 0.163 (−1.1σ), W(2×2) −0.176 ± 0.204 (−0.9σ), W(4×4)
  +0.054 ± 0.208 (+0.3σ). The original campaign reported this as a real
  systematic (all 20 negative, plaquette at −2.1σ); under regeneration it does
  **not** survive, and is reported here as scatter rather than a systematic.
  It affects no conclusion either way, being far below the per-case
  resolution — but the earlier "coherent offset" reading was over-claimed.
- *Over-dispersion.* std(z) should be 1 for a correct model with correct
  errors; measured, it is 1.006 (plaquette), 1.259 (W2×2), 1.325 (W8×8),
  1.393 (W12×12), 2.597 (Q²). This is **genuine case-to-case model bias**,
  not an error-bar artifact: the coarse base delivered to the model at thin=5
  has τ_int = 0.50–0.62 on every observable, bounding any inherited-correlation
  inflation at ≤ 1.12×, and `z_exact` never involves the reference chain's
  errors at all.
- *The bias concentrates in extended observables.* std(z) grows with loop
  area — 1.282 (4×4) → 1.283 (6×6) → 1.325 (8×8) → 1.424 (10×10) → 1.393
  (12×12), with max |z| rising 3.30 → 4.51. The growth is a trend, not a
  monotone one: the 12×12 point sits below 10×10, so the ordering at the two
  largest loops is within noise. Counting beyond-3σ excursions over the
  *full* observable set gives 24 of 760 tests against 2.05 expected, versus
  1 of 114 over the {plaquette, W2×2, W4×4} subset the case tables emphasize
  — i.e. the short-distance subset is now fully consistent with chance while
  the extended set is over-populated by an order of magnitude. That contrast
  is the point of this bullet, and it is *sharper* than in the original
  campaign, where the subset itself carried 4 excursions. These are not
  independent failures — they are a handful of cases deviating coherently
  across all loop sizes.

This is the observable-side shadow of the density gap: the residual model
error lives in long-wavelength modes, exactly the modes that 16 local
rethermalization sweeps relax slowest and that the ~1 nat/site KL is made of.
Short-distance observables are reproduced to 10⁻⁴; extended ones carry the
error. Any successor should report large-loop dispersion, not only the
plaquette and small loops.

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
guarded multi-case reverse-KL fine-tune that reduces the density gap by 1.33×
on the geometric mean over the four monitors — concentrated as 2.3× where the
spread is largest, and still improving 4× beyond its training range, though
marginally negative at the mildest case — without sacrificing the
one-checkpoint generality the pipeline is built on. Fine-tuned checkpoints
are used *only* for the likelihood/ESS results in this section; every other
result in this appendix uses the unmodified v2 campaign checkpoint.

---

### Figure 1 — `figures/01_ladder_drift.png`
**Ladder observable drift.** z vs exact for the plaquette and two companion
loops, W(2×2) and W(4×4), at each *generated* rung of the ladder — L = 16, 32,
64 at β = 4.0, 14.15, 55.02 — lifted from an L = 8, β = 1.35 HMC base. Shading
is the |z| ≤ 2 band. Drift does not accumulate across rungs: every observable
stays inside the band at every rung, because each inverse step is followed by
short local rethermalization (16 sweeps, no Q-hops) which pins the UV before
the next doubling. Companion loops are shown because the residual model error
concentrates in extended observables (see *Validation sharpness*), so a
plaquette-only version of this figure would be the least sensitive one
available.

### Figure 2 — `figures/02_ladder_topology.png`
**Ladder topology.** ⟨Q⟩, ⟨Q²⟩ and χ_top per rung: generated (filled circles)
against the exact finite-volume values (black bars), with the direct-HMC
reference for contrast. The sector content is inherited from the coarse base —
an L = 8, β = 1.35 ensemble where HMC tunnels freely — and transported
structurally up the ladder, which is how correct ⟨Q²⟩ persists at couplings
where any direct chain is frozen. Generated ⟨Q²⟩ is *identical* at all three
rungs (1.823) against exact 1.934 → 1.904 → 1.903: the transported sector is
literally the base's, which is the ladder-invariance identity operating rather
than three independent agreements. Reference points drawn as grey ×
(L = 32 and 64) are chains that never tunnel at that coupling — they are the
freezing demonstration, not a reference, and their ⟨Q²⟩ of 12.3 and 57.5
against exact ≈ 1.9 is the bias being demonstrated. Only the exact values are
truth in this figure.

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
trajectories in 26 of 29 cases (23 of 29 under the stricter
below-2τ_int criterion) — below the interval, i.e. cheaper than the
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
baseline; its Q-hop keeps tunneling to β = 256 where standard HMC froze at 16
(from the `scripts/13` sweep; that run's output was not archived in
`out/u1_2d/` and the figure of record does not depend on it — rerun
`13_instanton_vs_standard_hmc.py` to re-materialize the numbers) —
is far cheaper per config where it is correct (~0.01 s vs ~2.4 s), but open
markers show it failing exactness (Wilson observables, up to 16.6σ) at
β ≥ 55: its topology moves work, its UV does not thermalize. The diffusion
pipeline passes everywhere at flat cost.

### Figure 18 — `figures/18_entry_cost.png`
**Entry cost vs β — the head-to-head's decisive plot.** Burn-in wall-clock
required before the instanton-HMC ensemble agrees with exact results: 8 s
(β = 4.4), 16 s (β = 14.1), 1677 s (β = 55, needing 8000 trajectories), and
*never within the tested budget* at β = 218.58 (7.2σ off after 8000
trajectories / 2534 s). The baseline's entry cost grows ~200× over one decade
of β and then stops converging.

**The diffusion arm is charged its own entry cost here** (dashed line): the
campaign that produced the checkpoint cost **8820 s once** — 21.7 min of HMC
data generation plus 125.3 min of training (`out/u1_2d/run.log`) — which is
larger than *every* instanton-HMC burn-in that converges. For a single
ensemble at a single coupling below β ≈ 55, instanton HMC is cheaper outright,
and we say so. The generative cost is a **fixed one-time charge plus a flat
marginal cost**, against a competitor cost that diverges with β: amortized
over the 38 study cases the campaign adds 1.8 s/config, giving ~4.2 s/config
total, still flat in β. The claim this figure supports is therefore *not*
"diffusion is cheaper" — it is that the generative cost does not grow with β
while the baseline's does, and beyond β ≈ 55 the baseline stops reaching
correctness at any tested budget.

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
restores ⟨Q²⟩ = 5.2 vs exact 4.78 (p = 0.39) in 6 seconds of wall clock.
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
to std ≈ 555 (3.4× the baseline's 161) while merely recovering knob-level at
its own coupling. (iii) The guarded multi-case reverse-KL (rkl2) is the only
variant that improves on the baseline overall (geometric mean over the four
monitors 52.3 → 39.4), and it does so *unevenly*: 2.3× at 16:55 (42.0 → 18.3)
but only 1.2–1.3× at the two L = 32 cases, and it is marginally **worse** than
the untuned baseline at the mildest case (16:14.1: 17.5 → 19.2). The gain is
therefore concentrated where the spread was largest, not uniform across the
plane — and it does extend to the extrapolation monitor it never trained on
(161.1 → 127.8). ESS/N nonetheless remains at the
1/N floor throughout: self-normalized weights need total spread of O(1–3)
before ESS lifts off, so an order of magnitude remains; the honest reading is
a modestly reduced density gap with a quantified remainder, not a solved
problem.

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
multi-case reverse-KL are the two keepers (42.0 → 35.1 → 18.3); ML fine-tuning,
single-case reverse-KL, the 3.7× capacity/data scale-up, and the 354-parameter
correction head (2.4–4.8× worse on its disjoint grid; omitted for scale) all
went backwards relative to the keeper
and were discarded by the guard protocol, which scores the geometric mean over
all four monitors (Table S5) rather than this single case — the capacity
scale-up in particular is the best variant *at* the mildest monitor (16:14.1)
while losing overall. (b) The quantified end state: per-site density gap of
the final checkpoint across the full (L, β) plane — 0.018–0.062 nats/site,
uniformly 3.7–12.5× above the ~0.005 bar at which self-normalized weights
would become usable. The program is closed at its optimum: rkl2 + σ_min 0.03,
with the remainder characterized rather than conjectured.

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
| cases with \|z(⟨Q²⟩)\| > 2 | 13 [b] | 3 [b] |
| significant ⟨Q⟩ asymmetry (\|z\| > 2) | 0 | 0 |
| mean \|plaquette z\| (38 cases) | 1.77 | 1.74 |

[b] Counting convention differs between the columns as originally tabulated:
the transport 13 includes 2 rows with z = +inf, while the exact-sector 3
excludes its own 2 such rows. Counted consistently the pair is 13 vs 5
(inf included) or 11 vs 3 (inf excluded); the qualitative gap is unchanged.

The exact-sector residuals are at the multiple-testing false-positive rate
(≈ 1.75 expected at α = 0.05 over 35 tests). χ² is computable for 35 of 38
cases; the three deep-frozen cases (exact ⟨Q²⟩ ≲ 10⁻³) have no populated
bins to test.

## Table S4 — P(Q) before/after a 200-trajectory instanton-HMC tail

| case | L | β_f | ⟨Q²⟩ before | after | exact | χ² p before | after | tail (s) |
|---|---|---|---|---|---|---|---|---|
| B_bt6 | 32 | 6 | 1.92 | 5.20 | 4.78 | 0.0005 | 0.39 | 6 |
| A_bc1.5 | 32 | 4.44 | 5.10 | 6.88 | 6.79 | 0.87 | 0.24 | 6 |
| E_bc11.8 | 32 | 43.6 | 0.44 | 0.54 | 0.58 | 0.31 | 0.96 | 16 |
| D_bc55.02 | 32 | 218.6 | 0.031 | 0.039 | 0.029 | — | — | 41 |
| C_L64 | 64 | 14.15 | 6.43 | 10.4 | 7.62 | 0.07 | 0.70 | 19 |

Tails run on the transport-mode ensembles (the harder starting point). The
frozen-regime row (β_f = 218.6) has too few populated Q bins for a χ² test;
its ⟨Q²⟩ stays consistent with exact. All tails cost seconds — negligible
against either arm of the head-to-head in Table S1.

## Table S5 — ESS-gap program: fiber log-weight std by checkpoint variant

| variant | L16 β14.1 | L16 β55.0 | L32 β55.0 | L32 β218.6 | geo. mean |
|---|---|---|---|---|---|
| v2 checkpoint, ladder knobs | **17.5** | 42.0 | 63.2 | 161.1 | 52.3 |
| v2 checkpoint, σ_min-coef 0.03 (knob only) | — | 35.1 | — | — | — |
| + ML fine-tune (best-val, step 75) | 29.3 | 87.9 | 251.4 | 942.0 | 157.1 |
| + single-case reverse-KL | 18.3 | 21.1 | 63.0 | 555.0 | 60.6 |
| multi-case reverse-KL (rkl2, guarded) | 19.2 | **18.3** | **53.9** | **127.8** | **39.4** |
| big net (hidden 80, +24 L=32 rungs), DSM | **15.0** | 32.7 | 56.9 | 153.7 | 45.5 |
| rkl2 + 354-param correction head (best-val) | worse 2.4–4.8× on its disjoint grid (8:8 → 19.1 vs 7.8; 16:25 → 80.4 vs 16.8; 32:14.1 → 148.5 vs 37.5) | | | |

All rows are fresh-seed verification runs with valid weights (probability-flow
ODE sampling, n = 64, 120 steps, 2 Hutchinson probes, σ_min-coef 0.03 except
the ladder-knobs row at 0.1). Bold marks the best variant *per column*, and
the per-column winner is not the same variant everywhere: rkl2 wins three of
four monitors while the untuned baseline and the capacity scale-up win the
mildest one. The guard protocol therefore selects on the geometric mean over
all four, where rkl2 is the unique optimum (39.4 against the baseline's 52.3,
a 1.33× overall reduction). Note that this is a materially weaker statement
than a uniform halving: the reduction is 2.3× at the single case where the
spread was largest and ≤ 1.3× elsewhere. ESS/N sits at or near the 1/64 floor
throughout (1.00–2.34× the floor across all populated entries): the total
spread must reach O(1–3) before self-normalized ESS lifts off, so the
reduction delivered by rkl2 is real but insufficient — roughly an order of
magnitude remains. The ordering of the ESS column is itself an illustration
of the next section's point: the *largest* ESS/N in the table (0.035 at
16:55) belongs to ML fine-tuning, the variant with the *worst* spread there
(87.9), so ESS ranks these checkpoints in nearly the opposite order to the
quantity that matters. Training cost of rkl2:
300 warm-started optimizer steps, ≈ 80 min on the laptop CPU; the campaign
checkpoint itself is unmodified, and only this section's likelihood/ESS
results use the fine-tuned variants. Full provenance:
`out/u1_2d/ess_chain/` (chain logs, per-stage sentinels, chosen
knobs, verification JSONs) and `scripts/19–26`.

## Measuring the gap when ESS is uninformative

The standard distributional check on a generative sampler is the
self-normalized effective sample size. It is the right instinct and it fails
in exactly the regime one most needs it.

**Why ESS stops reporting.** For self-normalized weights, ESS/N is bounded
below by 1/N — the value taken when a single sample carries all the weight.
Every raw-transport case here sits at that bound (Table S2: 0.016 with
N = 64, i.e. 1/64 to three digits). That is not a small ESS; it is an
*unresolved* one. The estimator has saturated, and the true value could be
arbitrarily smaller. Two proposals whose log-weight spreads differ by an
order of magnitude — 15 nats and 164 nats, both present in Table S5 —
report the identical ESS/N. Any program that tries to *improve* a proposal
while monitoring ESS is therefore flying blind: the quantity it optimizes
cannot see the progress it makes. This is the practical reason the ESS-gap
program (Figs 23–25) is reported in log-weight spread throughout, with ESS
quoted only to confirm it never lifted off.

**What replaces it.** For weights that are valid — meaning the proposal
density is known for the actual samples drawn — the identity

    E_q[log w]  −  ΔF_exact  =  −KL(q ‖ p)

holds exactly, with w = e^(−S_f) e^(+S_matched(c)) / q(x|c). If ΔF can be
computed independently, the *mean* log-weight is a direct measurement of the
Kullback–Leibler divergence, in nats. It is finite, it has a sem, and it is
completely insensitive to how degenerate the weights are: the mean of log w
is well-behaved precisely where the mean of w is not. That is the readout
this appendix uses, and it is what turns "the weights are degenerate" into
"the density is off by 1.10 nats/site."

Three ingredients are required, and each is a real constraint on where the
method applies:

1. *Valid weights for the actual samples.* It is not enough to be able to
   evaluate a density at a given configuration; the configurations must come
   with their own densities. Here the probability-flow ODE is **sampled**,
   accumulating the Hutchinson divergence along the same trajectory that
   produces the configuration, so each sample arrives with its exact log q in
   one pass. Evaluating a separately-drawn ensemble under a discretized
   reverse map would not give valid weights, because the evaluation map is
   not the inverse of the sampling map at finite step count.
2. *An independently computable ΔF.* Supplied here by the character
   expansion of the 2D U(1) partition function on the torus. This is the
   ingredient that does not transfer: in a theory without an exact free
   energy the identity still holds, but the KL cannot be read off, and one
   is left with the spread alone.
3. *Estimator control.* The Hutchinson trace estimator is unbiased in log q
   (it enters linearly), and the residual concerns are discretization and
   probe noise. Both are bounded by explicit controls rather than assumed:
   8 probes and 240 integration steps both reproduce the baseline spread
   (Fig. 24), pinning the measured spread on the model rather than the
   estimator.

**Validating the instrument.** Because the claim is a null result about a
model, the machinery is validated end-to-end on cases where the answer is
known. On an exactly solvable wrapped-Gaussian target with the true score and
exact divergence the pipeline returns ESS/N > 0.5 — i.e. it *can* report a
healthy ESS, so the floor values above are a property of the model, not of
the code. On synthetic exact weights the free-energy certificate closes to
< 0.02 nats. Both are unit tests, not one-off checks.

**Mean and variance are different diagnostics.** They are routinely
conflated under a single ESS number, and both are lost when that number
saturates. They answer different questions:

- the **mean** (the KL, ≈ 1 nat/site here) says how far the proposal's
  density sits from the target on average — a bulk offset, largely uniform
  per plaquette;
- the **spread** (0.018–0.062 nats/site) says whether reweighting is usable at
  all, since self-normalized estimators need total spread of O(1–3) before
  ESS lifts off.

Reporting both is what makes the closure statement quantitative: the residual
gap is a ~1 nat/site bulk offset plus a 0.018–0.062 nats/site spread plus
sector-frequency mismatch, and it is the *spread*, not the mean, that keeps
reweighting out of reach.

**Separating model error from matching error.** One competing explanation
survives all of the above: the coarse conditioning ensemble is drawn from a
single-coupling action, whereas the true blocked measure of a Wilson theory
carries induced multi-coupling structure. Any mismatch there contributes to
the weights without being the model's fault. The control is an arm in which
the matching is exact by construction — the Villain action, where blocking
gives β_c = β_f/4 exactly — so its spread is model error alone. Wilson ≤
Villain at every case, and Wilson's coarse-explainable fraction sits *below*
Villain's model-error baseline (Table S6): the matching floor is negligible
and the measured gap is fine-side model error, in full. This is the step that
makes the falsification chain a closure rather than an exhaustion, and it
generalizes — any theory with an exactly-blockable companion action admits
the same control.

## Exactness endgame (2026-08-02 evening): decomposition, AIS transport, L = 64

**Table S6 — Matching residual vs model error.** Both arms blend-free at the
*trained* σ floor (coef 0.3; below it, unblended sampling measures the
network's untrained-σ extrapolation, not the model). R²_c is the fiber
log-weight variance explained by coarse-only observables. The Villain arm was
rerun on 2026-08-03 after a bug fix (below); both runs are shown, because the
difference between them is itself informative.

| arm | L16 β14.1 std/site (R²_c) | L16 β55.0 | L32 β55.0 |
|---|---|---|---|
| Wilson (matching residual + model error) | 0.0209 (0.062) | 0.0419 (0.005) | 0.0175 (0.023) |
| Villain, β_c = β_f/4 exact (corrected) | 0.0298 (0.075) | 0.0914 (0.003) | 0.0406 (0.077) |
| Villain, β_c = Wilson-matched (original, superseded) | 0.0287 (0.174) | 0.0459 (0.031) | 0.0268 (0.048) |

**The bug.** `27_matching_residual.py` called
`approx_matched_coarse_beta(fine_beta)` without `action_type`, whose default
is `"wilson"`, so the Villain arm ran at β_c = 4.0 and 14.1464 rather than the
exact 14.1464/4 = 3.5366 and 55.0237/4 = 13.7559. Both runs are internally
valid (base HMC, S_matched and ΔF all use the same β_c); only the corrected
one has the exact-matching property the control depends on. Fixed in scripts
27 and 19.

**What the rerun showed, and why it was not what we expected.** Correcting the
matching made the Villain spreads *larger*, by +4%, +99% and +51%. The reason
is a train/test confound, not a matching effect: the checkpoint was trained on
**Wilson** data at the **Wilson**-matched ladder couplings, which are exactly
the couplings the buggy run happened to use. The corrected run conditions the
same model on a different action at couplings it never saw, so it measures
model error plus an out-of-distribution conditioning penalty. The corrected
Villain row is therefore an *upper bound* on model error, and the subtraction
"Wilson − Villain = matching floor" cannot be read quantitatively. We report
it because the confound is real and the earlier framing hid it.

**The conclusion survives, on stronger and Villain-independent grounds.** The
matching residual is, by construction, a function of the coarse configuration
alone — it is the discrepancy between S_matched(c) and the true blocked action
evaluated on the same c. Any such term can therefore contribute *only* to the
coarse-explainable variance R²_c. Wilson's R²_c is **0.062, 0.005, 0.023**: at
most ~6% of the fiber log-weight variance is coarse-explainable at all, and
that figure is itself an upper bound because c-dependent *model* error lands
there too. The matching floor is negligible, and the measured density gap is
fine-side model error — and this argument needs no Villain arm. The Villain
comparison corroborates it (Wilson ≤ Villain at every case, now by a wider
margin) without being load-bearing. Deployment-settings coarse regressions
from the AIS samples agree: R²_c = 0.003–0.064.

**Why the arm was not re-run against a Villain-trained checkpoint.** The
obvious repair — train a Villain-specific model so the control arm is free of
the conditioning confound — would replace one confound with a larger one. It
would compare *two different checkpoints* (different capacity utilization,
training noise and seeds) rather than one checkpoint with and without a
matching residual. Table S5 measures how big that substitution is: variants of
the same architecture move fiber spreads by factors of 2–6. The quantity being
resolved here is bounded at a few percent of the variance, so it sits an order
of magnitude below the noise of any cross-model comparison. No amount of
retraining resolves an effect smaller than the confound introduced to measure
it; the within-arm R²_c decomposition does, and needs no second campaign. The
2D U(1) study is therefore closed with the corrected Villain numbers reported
as-is, confound named, and the load-bearing argument moved to R²_c. Full
discussion in `docs/NARRATIVE.md` §18.5.

Provenance: `out/u1_2d/matching_residual/wilson/`, `villain_fixed/`
(corrected, of record), `villain/` (original, superseded).

**Table S7 — AIS-corrected transport (final AIS result).** Surrogate-bridge
annealed importance sampling from ODE samples with exact initial density
(48 bridge steps, 2 HMC + instanton-hop updates per step; coefficients fit on
the even half, quoted on the held-out odd half; 7-feature basis).

| case | std before | surrogate R² | predicted floor √(1−R²)·std | AIS std (held-out) | held-out ESS/N |
|---|---|---|---|---|---|
| 16:14.1 | 17.0 | 0.717 | 9.0 | 30.6 | 0.021 |
| 16:55.0 | 17.6 | 0.332 | 14.4 | 18.6 | 0.024 |
| 32:55.0 | 36.4 | 0.664 | 21.1 | 28.4 | 0.021 |
| 32:218.6 | 117.5 | 0.839 | 47.1 | 44.7 | 0.021 |

The bridge saturates its theoretical floor where the gap is largest
(32:218.6: measured 44.7 vs predicted 47.1 — a 2.6× spread reduction with the
mechanism working exactly as derived), but held-out ESS/N stays at the 1/48
floor everywhere: the weights degenerate on the topological-sector component,
which does not regress onto smooth features. A wider 11-feature basis
(W(2×2), 4th character, plaquette-neighbor correlator, blocked 3rd character)
raised in-sample R² but exploded the held-out weights at 2 of 4 cases
(std 1120 and 18,650) — under-regularized wide bases extrapolate wildly once
the bridge dynamics move samples off the fit manifold. Recorded as the
program's sixth honest negative; the 7-feature run is the final AIS number.
Provenance: `out/u1_2d/ais_transport/` (final),
`ais_transport_rich/` (negative), `exactness2/`.

> **Reproduction note (2026-08-03).** The 7-feature basis is now the code
> default (`--basis final7`, `u1_2d/model/ais.py`), so `scripts/28` reproduces
> this table as shipped; `--basis rich11` reproduces the negative above.
> Previously the module exposed only the 11-feature basis while the script's
> default output directory was the results-of-record path, so a bare rerun
> would have overwritten the final numbers with the discarded variant. Script
> 28 now writes to `artifacts/u1_2d/ais_transport` unless `--out` is given
> explicitly, and its report header records the basis and width. The R²
> columns here are in-sample (refit on all data after CV ridge selection);
> with n = 64 and 6–11 predictors expect ~9–17% optimism, so the
> coarse-explainable share is an over-estimate and the predicted floor
> correspondingly optimistic. `cv_resid_std` in the JSONs is the honest
> counterpart. Held-out ESS/N is at the 1/48 floor in all four cases; the
> three-digit values should be read as "at floor", not ordered.

**The measured KL.** For valid weights, E[log w] − ΔF_exact = −KL(q‖p)
identically, with ΔF exactly computable here from the character expansion —
so the free-energy certificate doubles as a direct, sem-quotable measurement
of the model's mean density offset: **≈ 1.10 nats/site at 16:55 and
1.70 nats/site at 32:218.6** on the deployed checkpoint (1.07 and 1.57 on the
rkl2 variant — the mean offset is the one quantity the ESS program barely
moved, which is itself informative: the fine-tunes reshaped the *spread*, not
the bulk offset). The log-mean-exp gap
itself closes only at healthy ESS, which no case of the real model reaches;
on synthetic exact weights the certificate closes to < 0.02 nats (unit
test), validating the conventions end-to-end. The structure of the remaining
gap is therefore fully quantified: a bulk smooth offset of ~1 nat/site
(mean), spread 0.018–0.062 nats/site (variance), plus sector-frequency
mismatch. Within-sector SNIS combined with the exact finite-volume P(Q)
removes the sector component but inherits the bulk spread; neither crutch
alone yields usable exact estimates at n ≈ 100.

**L = 64 head-to-head and the entry-cost verdict.** At L = 64, β = 55, the
instanton-HMC arm with the standard 400-trajectory burn-in fails every Wilson
observable at z ≈ +9 to +10 while the diffusion arm passes all observables
(max |z| = 1.83, 8.6 s/config including base, sampling, and retherm). The bias is
positive (too ordered) and Q² is fine — cold-start relaxation of
long-wavelength modes, not topology — and it does **not** anneal away:
max Wilson |z| = 6.5 at burn-in 1600 and 6.3 at 6400. The competitor's
marginal-cost advantage (0.036 s/config) is purchased with an ensemble that
is still ~6σ biased after 16× the standard burn-in. This is the entry-cost
explosion of Fig. 18 materializing at scale, measured. Provenance:
`out/u1_2d/diffusion_vs_instanton/L64/` (+ `burnin_scan/`).

**Fresh-seed classification of the 3σ Wilson flags.** In the regenerated
campaign there are **no 3σ mean-value flags to classify**: across all 76
mean-value tests (plaquette and W(2×2) over the 38 cases) the largest |z| is
below 3, against an expectation of ~0.2 flags. The four cases flagged in the
original campaign (D_bc14.1464 plaq −2.93 ∧ W22 −3.47, B_bt20 −3.19,
A_bc8 −2.71, F_L64 W22 +3.03) now sit at −0.47/+1.85, −0.11/−0.38,
+0.24/−1.10 and +1.66/+2.48 respectively. This is the strongest available
evidence that those flags were seed fluctuations rather than defects: they
were classified as such by rerunning them, and under an independent
regeneration of the whole campaign they simply did not recur.

The two fresh-seed reruns (seeds 20260803/20260804) were repeated anyway, on
the same four cases, and agree: the largest plaquette or W(2×2) |z| over the
eight case–seed pairs is 2.31 (A_bc8, seed s4). Of the two residuals the
original run recorded, one reproduces and one does not. It does **not**
reproduce for topology: s3's A_bc8 ⟨Q²⟩ excursion (z = +4.18, exact-P(Q)
χ² p = 0.003) is absent, with ⟨Q²⟩ z = +0.60 and −1.74 at the two seeds. It
**does** reproduce for distribution shape: F_L64's minimum KS p is 0.0006 and
0.0000 at the two seeds (both on the plaquette) — a *distribution-shape*
mismatch at the far extrapolation whose means nonetheless pass, and which
therefore stands as the honest residual defect of that regime, alongside the
volume-growing raw Q² excess (rescued by exact-sector mode, Table S3).
Provenance: `out/u1_2d/generalization_fresh_s3/`, `_s4/`.

**Program closure (2026-08-02).** The exactness program is closed at
rkl2 + σ_min-coef 0.03 — the measured optimum. The complete falsification
chain — sampling-time knobs (one win), data-side maximum-likelihood
fine-tuning at 197k and at 354 parameters (both degrade deployment: the
forward/reverse-KL asymmetry is intrinsic to the objective, not a capacity
effect), single-case reverse-KL (destroys extrapolation), guarded multi-case
reverse-KL (a 1.33× win on the geometric mean over the four monitors —
concentrated as 2.3× at the highest-spread case and ≤ 1.3× elsewhere — then
plateau), capacity/data scaling under DSM (wins the mildest monitor, loses
overall), per-level SMC
restructuring (no weight diversity to harvest), and surrogate-bridge AIS
(saturates its floor, 2.6× spread reduction at the extrapolation case, ESS
unchanged; wide-basis variant the sixth converged negative) — leaves the
per-site density gap at 0.018–0.062 nats/site (spread) and 1.1–1.7 nats/site
(mean, measured directly by the free-energy identity) against the ~0.005
usable-certificate bar (Fig. 27b), with the matching-residual explanation
eliminated by the Villain control (Table S6): the gap is fine-side model
error, in full. Exactness for this pipeline therefore rests, by measurement
rather than assumption, on the Markov-chain route — rethermalization,
instanton-HMC tails, exact-sector resampling — wrapped around the generative
proposal: the architecture the head-to-head, seeding, and three-way results
(Figs. 17, 18, 21, 22, 26) validate directly, and the design carried forward
to the non-abelian successor (`su2_2d/`).

## A reporting protocol for learned coarse-to-fine samplers

Everything above is specific to 2D U(1), but the failure mode is not: a
learned coarse-to-fine map can reproduce low-order gauge-invariant
observables to four significant figures while its density is off by ~1
nat/site. That is not a pathology of this checkpoint — it is what one should
expect from a model trained on a local objective (denoising score matching)
and graded on a handful of low-dimensional projections. The physics
literature has an independent statement of the same hazard: Wilson loops
decouple from the slow topological modes, so observable agreement and
correct sector content are not the same claim.

The following is what this study would have reported from the start, and what
we suggest for any sampler of this class. Most of it costs nothing beyond
what is already computed.

**1. Report the z-distribution, not a pass count.** "38 of 38 cases within
|z| ≤ 3" is compatible with a badly biased sampler and with underestimated
errors, and distinguishes neither. Under a correct model with correct errors,
z across cases is standard normal: report mean(z) and std(z). Here mean(z) is
−0.42 on the plaquette (a real, coherent negative offset across all 20
Wilson-type observables) and std(z) is 1.26 (over-dispersed). Both were
invisible in the pass counts.

**2. Report dispersion against observable extent.** Short-distance agreement
does not certify the measure, and the place the failure becomes visible is
extended observables. Here std(z) climbs monotonically 1.09 → 1.44 from
W(4×4) to W(12×12), with max |z| rising 3.1 → 5.9. Quoting only the
plaquette and small loops — the three least affected quantities — hides
exactly the signal that matters.

**3. Eliminate the error-bar explanations before claiming model bias (and
vice versa).** Over-dispersion has two candidate causes. Both are cheap to
rule out: (i) measure τ_int of the coarse base actually delivered to the
model — here 0.50–0.62 at thin = 5, bounding inherited-correlation inflation
at ≤ 1.12×, far too small to explain 1.26–1.44; (ii) state which error enters
the z you quote — z against an *exact* value involves only the generated
ensemble's error, so a reference chain's autocorrelation cannot inflate it.
With both excluded the dispersion is model bias, which is a much stronger
statement than "some cases disagree."

**4. Do not report a saturated ESS as a number.** If ESS/N equals 1/N to
the digits shown, say "degenerate" and report the log-weight spread instead.
Three-digit ESS values at the floor imply a precision that is not there and
silently hide order-of-magnitude differences between proposals.

**5. Where an exact free energy exists, report the KL directly.** The
identity E_q[log w] − ΔF = −KL(q‖p) turns a certificate into a measurement
in nats/site that survives weight degeneracy. Report the mean (bulk density
offset) and the spread (reweighting usability) separately; they are different
diagnostics and a single ESS number loses both.

**6. Include an exactly-matched control arm.** The coarse conditioning
distribution is a competing explanation for any measured gap. An action
whose blocking relation is exact by construction — Villain here — separates
matching error from model error and converts a list of failed remedies into a
closure. Without it, "we tried six things and none worked" is exhaustion, not
a result.

**7. State the multiplicity, and apply it symmetrically.** Report the number
of tests, the number of observables per case, and the expected false-positive
count — and apply that reasoning to passes as well as to failures. Reruns of
flagged cases with fresh seeds should be accompanied by reruns of a matched
sample of unflagged cases; otherwise regression to the mean guarantees the
flags "vanish."

**8. Charge the generative arm its entry cost.** Burn-in for the classical
baseline and training-plus-data-generation for the learned sampler are the
same kind of cost. Quote the one-time cost, the marginal cost, and the
break-even configuration count; a comparison of the competitor's entry cost
against the model's marginal cost is not a comparison. Here the one-time cost
is 8820 s, larger than every classical burn-in that converges, and the
defensible claim is about *scaling* — the generative cost is flat in β while
the baseline's diverges — not about being cheaper.

**9. Report raw, pre-enforcement topology.** Any structural sector
imposition (charge transport, exact-P(Q) resampling, Q-shift bijections) will
make the final histogram look correct by construction. The informative number
is what the model carries before enforcement: here a raw charge-match rate of
0.21, and a raw ⟨Q²⟩ excess that *grows with volume* (1.7–2.7 at L ≤ 32 to
7.1–28.2 at L = 64/128). Report both, and be explicit about which
enforcement mechanism supplies the difference and whether it is available in
the target theory.

**10. Say which mode the correctness claim attaches to.** A generation
pipeline with no accept/reject on the proposal is a heuristic validated on
observables. A seeded chain run with an exact kernel is asymptotically exact.
These deserve different language, and conflating them is the single easiest
way for an honest study to overclaim.
