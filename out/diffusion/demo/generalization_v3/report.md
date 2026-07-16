# Generalization v3: multi-size + multi-beta training with a soft-topological-charge penalty

Run of 2026-07-15 (chain launched 19:29, CHAIN_DONE 23:30). Full pipeline:
data generation -> retraining -> 20-case generalization study, all with
`diffusion/configs/demo_v3.yaml` and checkpoint
`out/diffusion/demo_v3/checkpoints/score_net.pt`.

## What changed vs v2

1. **Training set** (8 -> 15 rungs): added L=8 at beta {1, 2} and L=32 at
   beta {2, 4, 6.5, 14.1464, 55.0237} alongside the unchanged eight L=16 rungs.
   The model now trains across three lattice sizes instead of one.
2. **Loss**: new soft-topological-charge penalty (`train.topo_weight: 0.1`),
   `(q_soft(denoised) - q_soft(target))^2 / (1 + sigma^2)` with
   `q_soft = sum sin(theta_p) / 2pi`. The integer charge has zero gradient a.e.
   through the curl-form score head; the sin surrogate does not. Contributes ~6%
   of the total loss at the start of training.

Training converged cleanly: val_total 11.08 -> 9.24 over 100 epochs, all 15 rungs
(including the new L=32 ones) reaching per-rung validation losses in the same
0.44-0.83 band as the L=16 rungs.

## Study outcome: no regressions — but the study is nearly checkpoint-blind

All 20 cases pass at the same level as v2 (`summary_tables.md`); no observable
regressed. However, a v2-vs-v3 diff exposed a structural property of the study
design that anyone comparing checkpoints with it must know:

- **The Q^2 / P(Q) columns never see the model.** `enforce_coarse_charge=True`
  copies Q from the cached base ensembles, so `q_squared_pre_retherm` is
  bit-identical between v2 and v3 in all 20 cases. These columns measure the
  base-ensemble draw plus retherm Q-hop re-equilibration only.
- **High-beta cases are RNG-coupled.** Both studies use `set_seed(1234)`, the
  same cached bases, and the same case order. At high beta the retherm local
  updates contract two nearby configs driven by identical uniforms onto the same
  trajectory (synchronous coupling), so post-retherm observables agree to all
  printed digits (e.g. A_bc4 plaquette z = -1.29 in both). Model differences
  survive only at low beta where the coupling is weak.
- This **resolves the old "A_bc2 Q^2 swings between retrains" mystery**: with
  base and seed held fixed the number does not move with the model at all
  (+3.45 -> +3.42). The historical swings (-4.2 / -0.65 / +3.4) were
  base-draw/seed sensitivity, not model quality. Multi-seed statistics, not
  model changes, are the right lens for that cell.

Where the model IS visible (pre-retherm, low beta): plaquette accuracy vs exact
is a wash overall (v3 closer in 9/20 cases) — the new penalty did not degrade UV
physics — with one clear win: A_bc0.25 (target beta 1.49, L=32) pre-retherm
plaquette error 0.155 -> 0.054, plausibly from the new low-beta/multi-size rungs.

## Topology transport A/B (the test the study cannot do)

`topo_ab_results.json`: 64 configs per case generated from identical bases with
`enforce_coarse_charge=False`, no retherm, same seed for both checkpoints, so the
measured charge comes from the model alone. Ideal transport is Q_fine = Q_base.

| case | beta_f | Q^2 base | Q^2 raw v2 | Q^2 raw v3 | match v2 | match v3 |
|---|---|---|---|---|---|---|
| A_bc1 | 3.10 | 9.48 | 9.38 | 10.14 | 0.19 | 0.19 |
| A_bc2 | 6.11 | 6.67 | 9.55 | 8.09 | 0.14 | 0.16 |
| A_bc4 | 14.15 | 2.22 | 8.44 | 6.48 | 0.17 | 0.14 |

- Per-config charge transport is unchanged (~15% match either way): the
  curl-head zero-mode argument stands — no loss term can pin integer Q, which is
  why `enforce_coarse_charge` remains necessary in the pipeline.
- The **ensemble-level spurious charge injected by raw sampling dropped where it
  matters**: excess Q^2 over the base shrank 2.88 -> 1.42 at the crossover
  (beta_f = 6.1) and 6.22 -> 4.26 at beta_f = 14.15 (~30-50% reduction). At
  beta_f = 3.1, where topology was already easy, no change (within noise).
- Caveat: N = 64 per cell; the Q^2 differences are ~1 sigma individually.
  Suggestive and in the right direction at both high-beta points, not decisive.
  A larger-N paired rerun would settle it.

## Bottom line

- Multi-size + multi-beta training and the topo penalty are in, validated
  (43 tests), and cost nothing in UV accuracy; the end-to-end pipeline remains
  correct everywhere it was correct before.
- The penalty measurably (though not yet decisively) reduces the raw sampler's
  spurious topological charge at beta_f >= 6 — the regime the ladder targets.
- The generalization study as currently designed cannot rank checkpoints:
  the Q columns are pinned by charge enforcement and the high-beta cells by RNG
  coupling. For future model comparisons: vary the seed (multi-seed error bars),
  and add pre-retherm / enforcement-off metrics to the study script.
