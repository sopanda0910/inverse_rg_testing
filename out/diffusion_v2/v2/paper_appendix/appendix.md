# Supplementary Material — v2 Model

This appendix documents the v2 checkpoint of the diffusion-based inverse-RG
sampler for 2D compact U(1) lattice gauge theory. It addresses four questions:
(1) does the generated ensemble match exact results, inside and far outside the
training range; (2) how does the sampler compare, in wall-clock cost and
correctness, against the strongest classical baseline we could construct
(instanton-update HMC, whose global Q-hop is the volume-independent uniform
Q-shift move); (3) what does a diffusion-generated configuration buy as an HMC
starting point; and (4) what an exact-likelihood diagnostic honestly says about
the model as an importance-sampling proposal.

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
maximum. Wilson observables pass against exact values; exact ⟨Q²⟩ ≈ 9·10⁻⁴ is
consistent with the generated ensemble's (all-zero) charge content.

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
require likelihood-aware training.

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
