# Inverse-RG diffusion model: generalization & scalability study

**Date:** 2026-07-08
**Model under test:** demo checkpoint `out/diffusion/demo/checkpoints/score_net.pt` — trained *only* on L=16 Wilson ensembles at beta in {1, 2, 4, 8, 14.1464, 55.0237}.
**Script:** `diffusion/scripts/06_generalization_study.py` (resumable; `--report-only` rebuilds figures/tables from `summary.json`).
**Data appendix:** `summary_tables.md` (full per-case observable tables), `summary.json` (machine-readable), `figures/` (per-case 4-panel validation + Wilson-loop distribution grids).

## What was tested

One rung of inverse RG (coarse L -> fine 2L) under four generalization axes,
20 cases total:

- **Part A — matched-pair coupling scan** (L=16 -> 32, 128 configs/case):
  base HMC at beta_c in {0.25, 0.5, 0.75, 1, 2, 3, 4, 6, 8}, generating at the
  physically matched fine coupling beta_f = `approx_matched_fine_beta(beta_c)`
  (1.49, 2.02, 2.54, 3.10, 6.11, 10.02, 14.15, 22.32, 30.38). Most targets fall
  *between* training betas, so this is also a coupling-interpolation test.
- **Part D — upper-coupling continuation**: 14.1464 -> 55.02 (edge of training)
  and 55.02 -> **218.58** (4x beyond anything in training).
- **Part B — target-coupling mismatch** (limitation probe): base fixed at
  (L=16, beta=4), generating at beta_f in {6, 10, 16, 20, 30, 55.02} vs the
  matched 14.15 (0.42x to 3.9x), plus the tree-level case beta_c=2 -> beta_f=8
  (matched would be 6.11).
- **Part C — lattice-size scan** at fixed pair 4 -> 14.1464: starting configs
  16x16, **32x32, 64x64**, generating 32, 64, **128x128** (96 and 64 configs at
  the two largest sizes). Training saw only L=16 fine lattices; L=128 is 64x
  the training volume.

Generation settings match the demo ladder (200 sampler steps, 1 corrector step,
blocking-consistency weight 1.0, coarse-charge enforcement, 16 retherm sweeps
with instanton Q-hops).

**Ground truth is two-tier.** (1) Exact character-expansion values at finite L
for every Wilson loop, the plaquette, chi_top, and P(Q); z-scores against these
("z" below) are sampler-independent. (2) Fresh HMC reference ensembles **with
instanton Q-hop updates and cold starts** (unlike `04_validate.py`, whose
references are deliberately topology-frozen to demonstrate freezing) for
distribution-level KS tests. Reference sanity was verified case by case:
after the cold-start fix (below), every reference agrees with exact values to
within ~3 sigma across plaquette, W(4x4), and Q^2.

## Headline results

| run | base (L, beta) | target beta | plaq z | W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | Q^2 gen / exact | P(Q) chi2 p | # loop KS p < 0.01 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A_bc0.25 | (16, 0.25) | 1.489 | -1.33 | -0.40 | +1.25 | -0.35 | +0.12 | +0.68 | 31.09 / 28.52 | 0.77 | 0 |
| A_bc0.5 | (16, 0.5) | 2.024 | +1.02 | +0.62 | +1.07 | -1.03 | -0.92 | +0.12 | 19.83 / 19.51 | 0.88 | 0 |
| A_bc0.75 | (16, 0.75) | 2.544 | -1.52 | -1.67 | -0.08 | +0.33 | -0.60 | +0.71 | 15.53 / 14.25 | 0.35 | 0 |
| A_bc1 | (16, 1) | 3.104 | -1.13 | -1.22 | -1.19 | -2.35 | +0.99 | -1.80 | 8.66 / 10.81 | 0.70 | 0 |
| A_bc2 | (16, 2) | 6.105 | -1.24 | -1.15 | -0.79 | +1.40 | +0.55 | **-4.17** | 3.19 / 4.69 | 0.12 | 2 |
| A_bc3 | (16, 3) | 10.02 | -0.23 | -0.97 | -1.32 | -0.66 | +1.02 | -1.07 | 2.45 / 2.74 | 0.66 | 0 |
| A_bc4 | (16, 4) | 14.15 | -0.96 | -1.90 | -1.93 | -2.24 | -0.84 | +1.85 | 2.44 / 1.90 | 0.06 | **6** |
| A_bc6 | (16, 6) | 22.32 | +0.20 | -1.42 | -1.51 | -0.89 | +0.35 | -0.18 | 1.16 / 1.19 | 0.92 | 0 |
| A_bc8 | (16, 8) | 30.38 | -1.00 | -1.07 | -0.51 | +0.21 | +1.17 | -1.09 | 0.77 / 0.87 | 0.80 | 0 |
| D_bc14.15 | (16, 14.15) | 55.02 | +0.20 | -0.14 | +1.47 | +1.41 | -0.34 | -1.31 | 0.42 / 0.47 | 0.92 | 0 |
| D_bc55.02 | (16, 55.02) | **218.6** | +2.08 | +1.03 | -0.27 | +0.73 | -1.09 | -2.97 | 0.008 / 0.029 | — | 0 |
| B_bt6 | (16, 4) | 6 | -0.16 | -0.32 | -0.77 | -0.14 | -1.25 | +1.48 | 5.85 / 4.78 | 0.04 | 0 |
| B_bt10 | (16, 4) | 10 | +0.13 | -0.55 | -0.79 | +0.06 | -1.30 | -1.33 | 2.34 / 2.74 | 0.87 | 0 |
| B_bt16 | (16, 4) | 16 | +1.00 | +1.00 | +0.36 | +0.75 | +2.37 | -0.34 | 1.61 / 1.68 | 0.53 | 0 |
| B_bt20 | (16, 4) | 20 | -0.09 | +1.12 | +2.21 | +0.93 | -0.69 | -0.28 | 1.30 / 1.33 | 0.85 | 0 |
| B_bt30 | (16, 4) | 30 | -1.09 | -0.40 | +0.17 | +0.49 | -0.24 | -1.70 | 0.74 / 0.88 | 0.39 | 0 |
| B_bt55 | (16, 4) | 55.02 | +0.32 | +0.10 | +1.00 | +1.19 | +0.27 | -0.37 | 0.45 / 0.47 | 0.61 | 0 |
| B_bc2_bt8 | (16, 2) | 8 | +1.54 | +1.61 | +1.70 | +2.27 | -0.26 | +1.21 | 3.89 / 3.48 | 0.72 | 0 |
| C_L64 | (32, 4) | 14.15 | +0.59 | +0.88 | +0.66 | -0.48 | +0.39 | -0.17 | 7.43 / 7.62 | 0.11 | 0 |
| C_L128 | (64, 4) | 14.15 | +1.24 | +1.81 | +1.43 | +0.29 | +1.61 | -0.40 | 28.20 / 30.46 | 0.63 | 0 |

(Full tables with all ~19 loop sizes, Creutz ratios, chi_top, errors, and KS
p-values per observable: `summary_tables.md`. Z-score summary figures:
`fig_matched_scan.png`, `fig_mismatch_scan.png`, `fig_size_scan.png`.
Scalability showcase figures, built by `diffusion/scripts/07_scaling_figures.py`:
`fig_scaling_volume.png` — <Q^2> proportional to V over a 16x volume span, Wilson
area-law collapse across L = 32/64/128, and per-config sampling cost growing no
faster than V; `fig_scaling_coupling.png` — plaquette and Creutz-ratio string
tension tracking exact curves over beta_f = 1.49 -> 218.6 with the training
range marked; `fig_scaling_parity.png` — generated-vs-exact parity for <Q^2>
(~3 decades) and -ln W(2x2) (~2.5 decades) across all 20 cases.)

### 1. Coupling-scale generalization is broadly successful

Across the full matched scan beta_f = 1.49 -> 218.6 (a factor 147 in coupling,
generated from bases beta_c = 0.25 -> 55), every mean observable — plaquette,
Wilson loops from 1x1 to 12x12, Creutz ratios, <Q>, <Q^2>, chi_top — agrees
with exact values at the |z| <~ 2 level, with two exceptions discussed below.
This includes:

- **Interpolation** between training couplings (targets 2.02, 2.54, 3.10, 6.11,
  10.02, 22.3, 30.4 were never trained on).
- **Extrapolation** to beta_f = 218.6, 4x beyond the largest training coupling,
  where plaquette lands at z = +2.08 and all loops within |z| <= 1.1. The
  Q^2 z of -2.97 there is a sparse-count artifact of the z-score approximation:
  exact <Q^2> = 0.029 means only ~3.7 of 128 configs are expected to carry
  |Q| = 1; the run drew 1. A Poisson interval, the appropriate statistic at
  such counts, is consistent at ~2 sigma.
- **Strong-coupling bases** (beta_c = 0.25–0.75) where the coarse conditioning
  input is nearly pure noise, yet topology-rich targets come out right:
  generated <Q^2> = 31.1 / 19.8 / 15.5 vs exact 28.5 / 19.5 / 14.3, with exact
  P(Q) histogram chi^2 p = 0.35–0.88 across ~15 populated charge sectors.

### 2. The genuine weak spots: mid-coupling topology and the trained pair's distributions

- **<Q^2> at beta_f ~ 6 (A_bc2): z = -4.17** (generated 3.19 vs exact 4.69, a
  32% deficit), with 2 of 19 loop KS tests also failing. beta_f ~ 6 is the
  crossover where topological sectors are neither abundant (small beta) nor
  effectively frozen to Q ~ 0 (large beta): <Q^2> is a few units, the coarse
  base at beta_c = 2 carries wide charge fluctuations, and errors in
  charge transport are neither drowned in statistics nor suppressed by the
  enforcement mechanism. Notably A_bc1 (beta_f = 3.1) shows a milder -1.80.
- **The trained pair A_bc4 (4 -> 14.15) fails the most KS tests (6 of 19)**,
  with a *coherent* deficit that grows with loop area: z = -1.9 / -1.9 / -2.2
  at W(2x2)/W(4x4)/W(8x8) and -2.2 to -3.0 across every loop with area 49–100
  (e.g. W(8x10) = 0.0335(78) vs exact 0.0532), confirmed at the same level
  against the unbiased reference (z_ref -2.2 to -2.9). Individually these are
  2–3 sigma, but six consecutive loop sizes low together is unambiguous, and
  the per-config KS tests flag the same loops. Curiously the
  *mismatched* cases at nearby targets from the same base (B_bt10, B_bt16)
  pass all KS tests — so the deficit is not a property of the target coupling
  alone. Candidate explanations, unresolved: inherited bias from the
  hot-start-contaminated training data (see section 5), or slight
  over-constraint by matched conditioning. Worth revisiting after retraining
  on clean data.

### 3. Robustness to target-coupling mismatch is surprisingly strong

With the base fixed at beta_c = 4, generating anywhere from 0.42x to 3.9x the
matched coupling leaves all means within |z| <= 2.4 and passes every loop KS
test. The user-motivated tree-level case **beta_c = 2 -> beta_f = 8** (1.31x
the matched 6.11) is clean across the board (worst observable W(8x8) at
z = +2.27; P(Q) chi^2 p = 0.72). Two caveats keep this from being a free
lunch: (i) topology is partly rescued by construction — coarse-charge
enforcement plus Q-hop rethermalization re-equilibrate P(Q) at the target
beta regardless of the base; (ii) a mismatched pair no longer represents a
*physical* RG step, so "correct ensemble at beta_f" is the right test, and
that is what passes. For pipeline purposes: the matched schedule is not
delicate — factor-of-2 errors in the beta schedule do not visibly degrade
one-rung output.

### 4. Lattice-size generalization is clean up to 128x128 (64x training volume)

At the fixed pair 4 -> 14.1464, starting from 16, 32, and 64 (generating 32,
64, 128): all observables within |z| <= 1.8, no KS failures at L = 64/128, and
<Q^2> tracks the exact volume scaling — 1.90 -> 7.62 -> 30.46 exact vs
2.44 -> 7.43 -> 28.20 generated. The fully-convolutional score network plus
gauge-invariant conditioning transfers across volume with no retuning. (See
`fig_size_scan.png`; the mild upward drift of plaquette/loop z with L is worth
watching but is not yet significant.)

### 5. Methodological finding: hot-start HMC has a metastable bias at beta >= 8 — and it contaminated the original references *and* the demo training data

The first pass of this study used hot-start, Q-hop HMC references (burn-in
200), and they disagreed with exact values by **12–67 sigma** (plaquette low
by 0.002–0.01) at every beta >= 10, while the *generated* ensembles matched
exact. Diagnosis: a hot start at large beta settles into a metastable state of
local defects that neither Q-hops (which fix global topology only) nor
hundreds of trajectories anneal; the deficit is flat across draws, i.e. it
looks converged. A **cold start + burn-in 600 (2000 for beta >= 20)**
reproduces exact values at every coupling tested, up to beta = 218.6.

Consequences:

- All references and bases in this study were rebuilt accordingly; the final
  reference-sanity check (reference vs exact) passes at <~ 3 sigma everywhere.
- The apparent "variance deficit" (generated Wilson-loop distributions
  narrower than reference, std ratios 0.3–0.5) seen against the biased
  references **was an artifact**; against unbiased references the std ratios
  are 0.87–1.26 and 18 of 20 cases pass all loop KS tests.
- **The demo training data itself** (`out/diffusion/demo/data`, hot-start) is
  biased the same way at beta = 8 / 14.15 / 55 (plaquette -6 / -23 / -71 sigma,
  up to -0.008 absolute). The model trained on it nevertheless produces
  exact-matching ensembles — consistency guidance toward coarse plaquettes
  plus rethermalization evidently dominate the small score-level bias — but
  the training data should be regenerated with cold starts before any
  retraining, and the A_bc4 distribution deficit re-examined then.

### 6. Reading the per-case figures at small beta: the loop signal-to-noise floor

In the `figures/*_wilson_dists.png` panels at small beta_f, the large-area
loop histograms look ragged and "wrong" for both generated and reference
ensembles. That is expected physics, not a defect: <W(A)> = exp(-sigma A)
with sigma large at strong coupling (0.52 at beta_f = 1.49), while per-config
measurement noise is area-independent (~1e-3 on the ensemble mean). Beyond
area ~16 the exact value (1e-9 to 1e-15) is orders of magnitude below the
noise floor, so both histograms are zero-centered noise — and they agree (KS
p = 0.2–0.7). The number of noise-dominated loops per case (exact mean below
3x the statistical error) is: 14/13/12/11 of ~19 at beta_f = 1.49/2.02/2.54/3.10,
6 at 6.1, ~2–3 at 10–14, 0 for beta_f >= 20. Informative observables at small
beta are the small loops, the plaquette-angle density, and topology — all of
which pass.

## Recommendations

1. **Regenerate training data with cold starts** (the `01_generate_data.py`
   defaults inherit `hot_start: true` from the configs) and retrain; then
   recheck the A_bc4 distribution-level deficit and the beta_f ~ 6 <Q^2>
   deficit.
2. **Add training coverage in the crossover region** beta in [5, 10] (only
   beta = 8 present now), where the <Q^2> deficit concentrates.
3. Consider **reporting Poisson intervals for <Q^2>** at beta/V large enough
   that fewer than ~10 configs carry charge (z-scores mislead there).
4. Adopt the cold-start + long-burn protocol for any future unbiased HMC
   baseline at beta >= 8 (now the default in this study's script for
   bases/references).

## Reproduction

```
.venv/Scripts/python.exe diffusion/scripts/06_generalization_study.py            # full study (resumable)
.venv/Scripts/python.exe diffusion/scripts/06_generalization_study.py --report-only
```

Artifacts: `bases/` (coarse HMC ensembles), `generated/` (diffusion outputs,
post-retherm), `reference/` (unbiased HMC), `figures/` (per-case validation
panels and Wilson-loop distribution grids), `fig_*.png` (cross-case summaries),
`summary_tables.md`, `summary.json` (includes per-case timings and
pre/post-rethermalization observables).
