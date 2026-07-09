# Generalization study v2: after clean data + crossover training rungs

Re-run of the full generalization & scalability study with the model retrained
per the v1 report's Recommendations #1 and #2:

- **#1 (clean data)**: training ensembles at beta >= 8 regenerated with cold
  starts + long burn-in (600; 2000 at beta = 55), eliminating the hot-start
  metastable defect bias that contaminated the original training data.
- **#2 (crossover coverage)**: two new training rungs at **beta = 5.0 and 6.5**
  (cold, burn 600) fill the gap beta in (4, 8), for 8 rungs total:
  {1, 2, 4, 5, 6.5, 8, 14.1464, 55.0237}, all L = 16.

Same 20 cases, same protocol, and the same cached HMC bases/references as v1
(cold-start, Q-hop, checkpoint-independent), so every change below is
attributable to the retrained model. v1 lives in `../generalization/`; the
intermediate Rec-#1-only recheck in `../generalization_retrained/`. Old
checkpoints: `../backup_hot_training/` (hot-trained), `../backup_rec1_checkpoints/`
(clean data, no crossover rungs).

## Headline results

| item | v1 (hot-trained) | v2 (this run) |
|---|---|---|
| A_bc4 (trained pair 4 -> 14.15) Wilson KS failures | **17/19**, loops 1-2% low | **1/19** |
| beta ~ 6 plaquette deficit (A_bc2 / B_bt6 z) | -4.2 / -4.4 (after Rec #1 alone) | **+0.07 / +0.12** |
| A_bc2 (2 -> 6.105) Q^2 z | -4.17 | +3.45 (overcorrected; see finding 2) |
| Case means within \|z\| <= 2.2 | all except A_bc2 Q^2 | all except A_bc2 Q^2 and D_bc55 Q^2 (Poisson-limited; finding 3) |
| Cases with <= 1 Wilson KS failure | 17/20 | 14/20 (elevated: A_bc2 6, C_L128 6, B_bt16 4, D_bc55 4; findings 2-4) |

Both targeted weak spots are resolved. The remaining tension is concentrated in
two genuinely hard regimes -- crossover topology (beta_f ~ 6) and the 4x
coupling extrapolation -- plus a new distribution-shape sensitivity at L = 128.

Full per-case tables: `summary_tables.md`. Per-case figures: `figures/`.
Cross-case scans: `fig_matched_scan.png`, `fig_mismatch_scan.png`,
`fig_size_scan.png`; scalability: `fig_scaling_volume.png`,
`fig_scaling_coupling.png`, `fig_scaling_parity.png`.

### 1. Both v1 weak spots are fixed

**A_bc4 (the trained pair)**: KS failures 17/19 -> 1/19 (min p across loops
0.026, next 0.08+), plaquette z = -1.29, W(4x4) z = +1.10, Q^2 z = +0.30,
P(Q) chi^2 p = 0.31. The v1 distribution-level deficit was the model faithfully
reproducing its biased training data; with clean data it is gone.

**The beta ~ 6 crossover plaquette deficit** (which appeared after the Rec-#1
retrain: ~ -1.3e-3, z ~ -4.2/-4.4 from both bases) is eliminated by the new
rungs: A_bc2 plaquette diff +0.00003 (z = +0.07), B_bt6 +0.00004 (z = +0.12),
and B_bt6 is now clean across the board (1/19 KS, all means within 1.1 sigma).
This confirms the interpolation-gap interpretation: the v1 model's apparent
accuracy at beta ~ 6 was an accidental cancellation between interpolation error
and training-data bias; unbiased data exposed the former, and coverage removed it.

### 2. Crossover topology at beta_f ~ 6.1 remains the hardest observable

A_bc2 (2 -> 6.105) Q^2 vs exact 4.686 across checkpoints: 3.19 (-4.2 sigma, v1)
-> 4.31 (-0.65, Rec-#1 recheck) -> 6.66 (+3.4, v2). The sign flip between
consecutive retrainings at fixed exact value says this is not a stable bias but
a high-variance, training-sensitive regime: beta_f ~ 6 has the broadest P(Q)
relative to the charge-transport granularity, and 128 configs give sigma(Q^2)
~ 0.6. Notably P(Q) chi^2 p = 0.83 (shape fine) and the 6/19 mid-loop KS
failures are unchanged from v1. Worth more statistics (multiple generation
seeds / larger n_configs) before concluding a model defect; if it persists,
this case, not the trained pair, is the real frontier.

### 3. The 4x coupling extrapolation under-produces topological charge

D_bc55 (55 -> 218.6, fully outside training): exact <Q^2> = 0.029 means only
~3.7 of 128 configs should carry any charge. v2 produced 0 charged configs
(one-sided Poisson p ~ 0.025); v1 produced 1 (z ~ -3.0). The naive z = inf in
the tables is an artifact of a zero-variance sample -- this is precisely v1's
Recommendation #3 (report Poisson intervals when expected charged-config counts
are < ~10), now demonstrably needed. Verdict: charge transport at extreme
extrapolation is marginally low for both models; all non-topological
observables there remain within ~1.6 sigma (4/19 KS, smallest loops).

### 4. Size scan: means clean to 128x128; new shape sensitivity at L = 128

C_L64: 0/19 KS, all means within 1.9 sigma. C_L128: means clean (max |z| = 2.2
on Q^2, P(Q) chi^2 p = 0.42), but 6/19 small/mid-loop KS failures
(p = 0.002-0.04) where v1 had 1/19. At V = 128^2 each per-config loop average
is extremely precise, so two-sample KS with 64 configs resolves per-mil shifts
in the distribution shape that are invisible in the means. Candidate cause:
fixed retherm depth (16 sweeps) relative to volume. Flagged for follow-up, not
a mean-level bias.

### 5. Everything else

The matched scan (beta_f = 1.49 -> 218.6), the mismatch scan (0.42x - 3.9x,
including tree-level 2 -> 8 which passes everything), and the remaining B cases
are consistent with v1's picture: means track exact across two decades of
coupling; small-beta topology excellent (A_bc0.25: <Q^2> ~ 31 regime). Mild KS
uptick at B_bt16/B_bt20 (4/19, 3/19; min p 0.004) sits near the noise floor of
19 correlated tests and does not correlate with any mean-level deviation.
Small-beta large-loop histograms remain noise-dominated (v1 finding 6 applies
unchanged).

## Recommendations (updated)

1. ~~Regenerate training data cold and retrain~~ -- **done, confirmed effective**.
2. ~~Add crossover training coverage~~ -- **done (beta = 5, 6.5), confirmed effective**.
3. Poisson intervals for topology when expected charged configs < ~10
   (D_bc55's z = inf makes this concrete) -- still open, now higher priority.
4. A_bc2 Q^2: repeat generation with several seeds / more configs to separate
   variance from bias before any model change.
5. C_L128 small-loop KS: test whether scaling retherm sweeps with L (or a short
   HMC tail, cf. the thermalization benchmark) removes the shape shift.
6. The demo ladder / validation / thermalization outputs
   (`../generated/`, `../validation/`, `../thermalization/`) still reflect the
   OLD hot-trained checkpoint; re-run 03/04 (and 05 if quoted) with this one.

## Reproduction

```
# config: diffusion/configs/demo.yaml (paths rewritten artifacts/ -> out/), 8 rungs, cold protocol
.venv/Scripts/python.exe diffusion/scripts/01_generate_data.py --config <cfg>
.venv/Scripts/python.exe diffusion/scripts/02_train.py         --config <cfg>
.venv/Scripts/python.exe diffusion/scripts/06_generalization_study.py --out-dir out/diffusion/demo/generalization_v2
.venv/Scripts/python.exe diffusion/scripts/07_scaling_figures.py      --dir out/diffusion/demo/generalization_v2
```

Bases/references were seeded by copying `../generalization/{bases,reference}`
(checkpoint-independent). Full log: `run.log`.
