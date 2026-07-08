# Recheck after clean retraining (Recommendation #1)

Implements Recommendation #1 of the generalization study (2026-07-08): the demo
training data at beta = 8, 14.1464, 55.0237 was contaminated by the hot-start
metastable defect state (plaquette biased low by tens of sigma). This run
regenerated those rungs with cold starts (burn-in 600, and 2000 for beta >= 20 --
the protocol verified against exact values up to beta = 218.6), retrained the
score model from scratch (100 epochs, same architecture/seed), and re-ran the two
weak-spot cases plus one control with the new checkpoint.

- Old (hot-start) data and checkpoint: `out/diffusion/demo/backup_hot_training/`
- New training data: `out/diffusion/demo/data/` (per-rung `hot_start` / `burn_in`
  overrides now supported by `01_generate_data.py` and set in `demo.yaml`)
- Recheck outputs (this directory) reuse the study's cached HMC bases/references,
  which are checkpoint-independent; z-scores are against exact character-expansion
  values; KS tests are against the cold-start, Q-hop references.
- Training loss was essentially unchanged (best val 3.563 vs 3.568) -- the DSM
  loss is insensitive to a sub-percent distributional shift; the effect shows up
  only in generated observables.

## Weak spot 1: A_bc4 (trained pair, base beta_c = 4 -> beta_f = 14.1464) -- FIXED

| | before (hot-trained) | after (cold-trained) |
|---|---|---|
| Wilson-loop KS failures (p < 0.05) | **17 / 19** (loops ~1-2% low) | **0 / 19** (min p = 0.080) |
| plaquette z vs exact | -0.96 | +1.12 |
| W(4x4) z | -1.93 | +0.07 |
| Q^2 z | +1.85 | -0.44 |
| P(Q) chi^2 p | 0.064 | 0.627 |

The distribution-level deficit at the trained pair is gone entirely. This
confirms the suspected cause: the model had faithfully learned the hot-start
bias present in its beta = 14.15 / 55 training ensembles.

## Weak spot 2: A_bc2 (crossover, base beta_c = 2 -> beta_f = 6.105) -- Q^2 FIXED

| | before | after |
|---|---|---|
| **Q^2 z vs exact** | **-4.17** | **-0.65** |
| P(Q) chi^2 p | 0.121 | 0.922 |
| W(4x4) z | -0.79 | -1.10 |
| plaquette z | -1.24 | **-4.16** (deficit -0.0012 absolute) |
| Wilson KS failures | 6 / 19 (mid loops) | 5 / 19 (small loops: 1x1..3x3) |

The targeted <Q^2> deficit is resolved. However, a new small-loop / plaquette
deficit appeared (see below).

## Control: B_bt6 (base beta_c = 4 -> target beta = 6) -- localizes the new deficit

| | before | after |
|---|---|---|
| plaquette z | -0.16 (diff -0.00004) | -4.42 (diff -0.0013) |
| Wilson KS failures | 0 / 19 | 2 / 19 (1x1, 2x2) |
| Q^2 z | +1.48 | -1.68 |

The same ~ -0.0013 plaquette deficit appears at target beta ~ 6 from BOTH bases
(beta_c = 2 and 4), so it is a property of the retrained model's conditioning at
beta ~ 6, not of the base ensemble. Everything else at these points (mid/large
loops, topology) is clean.

## Interpretation and next step

beta ~ 6 sits in the crossover gap of the training schedule (no rung between 4
and 8). The old model appeared accurate there, but its beta = 8 training data
was itself biased low -- plausibly an accidental cancellation between
interpolation error and data bias. With unbiased data the intrinsic
interpolation error is exposed: a ~1.3e-3 plaquette deficit (few sigma at these
statistics), UV-local (only the smallest loops fail KS).

This is precisely Recommendation #2 of the study: **add training coverage in
beta in [5, 10]** (e.g. rungs at 5 and 6.5) and re-run these two cases. The
hot-start-bias issue (Recommendation #1) is closed.

## Bookkeeping

The other study parts (full A/B/C/D scans) and the demo ladder / validation /
thermalization outputs still reflect the OLD checkpoint. Given A_bc4's change,
re-running the ladder pipeline (03 -> 04, and 05 if desired) with the new
checkpoint is recommended before quoting those numbers alongside these.
