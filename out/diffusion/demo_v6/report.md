# v6: one diffusion model across couplings and lattice sizes — final report

Campaign 2026-07-18/19. Model: `checkpoints/score_net.pt` — trained ONCE on
continuous log-uniform couplings beta in [1, 60] (60 rungs at L=16, 12 at L=32,
6 at L=8, 128 configs each) plus four sector-augmented anchors, with the
beta-aware noise floor `sigma_min(beta) = min(0.03, 0.3/sqrt(beta))`, the raw
winding conditioning channel (`cond_channels: 5`), the soft-topological-charge
penalty, and in-sampler charge projection. Study: 38 cases (matched track A/D,
mismatch controls B, size scan C, out-of-sample mid-gap track E, extrapolation
demo F), parts A/D/E/F at two independent seeds. Ground truth: exact character
expansion. Machine-readable tables: `generalization/verdict.md`; figure:
`generalization/showcase.png`.

## 1. The goal, answered

**One model generates correct ensembles at couplings 15x beyond its training
range and at lattice sizes it never trained on.**

| case | beta_f | L_f | plaq z (2 seeds) | W22 z | W44 z | topology |
|---|---|---|---|---|---|---|
| F_L32_bc100 | **398.5** | 32 | -1.1 / -0.2 | -0.4 / +0.5 | +0.4 / -0.0 | all Q = 0, consistent with exact <Q^2> ~ 9e-4 |
| F_L32_bc218.58 | **872.8** | 32 | +0.1 / -1.0 | -0.7 / -1.5 | -0.8 / -0.5 | all Q = 0, consistent with exact <Q^2> ~ 1e-7 |
| F_L64_bc55.0237 | 218.6 | **64** | -0.8 / -0.2 | -1.5 / -0.3 | -0.7 / +0.1 | <Q^2> z = +1.3 / +0.8 vs exact 0.47 |

Training saw nothing above beta = 60 and no fine lattice larger than L = 32.
At beta = 873 direct HMC is not an alternative: Q-tunneling is suppressed by
~exp(-2 beta), hot starts freeze into wrong sectors permanently, and cold
starts pin Q = 0 with burn-ins of hundreds of trajectories. (The "+inf" Q^2
z-scores in the raw tables at beta >= 398 are a zero-variance display artifact:
generated and exact <Q^2> are both zero to well below one config's worth of
probability.) The historic L >= 64 small-loop KS caveat was resolved
post-campaign (2026-07-19 diagnostics, `diag_run.log`): regenerating the
references with burn-in 5000 makes every Wilson-loop KS pass at L = 64,
beta = 14.15 — the "shape failure seen since v2" was reference
under-thermalization. At L = 128 the residual is p ~ 0.02, the same order as
the references' own scatter around exact (+2.9 old vs -3.1 new). At
beta = 218.6, L = 64 even burn-5000 HMC stays +4.3 sigma off the exact
plaquette, so exact-only tests are the validation standard there. Full
analysis: `improvements_vs_hmc.md`, section 5.

## 2. The out-of-sample gap is closed

v5 exposed that raw-topology gains were in-sample recall (excess 3.26 on-grid
vs 4.57 mid-gap). With continuous-beta training there is no grid:

| | in-sample A/D | out-of-sample E |
|---|---|---|
| v5 (11-coupling grid) | 3.26 | 4.57 |
| **v6 (continuous beta)** | **2.56** | **2.56** |

Identical to two decimals, and the overall level is the best of any checkpoint
(v2 baseline: 4.67). The same collapse shows in seed quality: OOS cases
E_bc2.7 / E_bc4.5 / E_bc5.8 thermalize in 0 / 9 / 8 trajectories — as fast as
the trained-adjacent cases. "Off-grid" is no longer a meaningful category
inside the training range.

## 3. Thermalization: the useful zone widened; the wall moved but stands

Raw seeds (no retherm) vs standard HMC's sampling interval 2 tau_int
(`verdict.md` for all 29 rows):

- **beta_f <= 10**: HMC generally wins or ties — as in every campaign; nothing
  to gain where HMC mixes well.
- **beta_f = 10-70**: seeds win 10 of 13 cases, in- and out-of-sample alike
  (t_therm 0-24 vs intervals 9-35), with hot HMC frozen throughout. The v5
  never-zone here is fully gone.
- **beta_f >= 78**: every raw seed still plateaus outside |z| <= 2 — the wall
  moved from ~55-70 (v5) to ~78 (E_bc18 at 70.5 now passes) but was not
  eliminated by the beta-aware floor. This is a raw-seed statement only: the
  post-pipeline ensembles (charge projection + 16 retherm sweeps) pass every
  observable test up to beta = 873, so the ladder is unaffected; but claims of
  "retherm-free seeding" must stop at beta_f ~ 70.

## 4. What each v6 ingredient bought

1. **Continuous-beta training** — closed the OOS gap (section 2); the single
   most consequential change of the whole program.
2. **Beta-aware sigma floor** — extrapolation quality at beta >= 398 (section 1)
   and a modest wall shift (70 -> 78); did not remove the wall, so the residual
   high-beta raw-seed bias is not (only) a noise-floor effect.
3. **Winding channel + sector augmentation + topo penalty** — raw spurious Q^2
   excess at its historical best (2.56 vs 4.67 at v2, -45%), uniformly in beta.
   Per-config match rates remain ~0.1-0.2: the curl zero-mode bound is physics,
   and deterministic charge projection remains structural.
4. **In-sampler projection** — pipeline-side only by design; post-pipeline
   topology passes everywhere it can be tested.

## 5. Reproducibility

- Chain log: `run.log` (STAGE_DATA 13:49 -> CHAIN_DONE 10:12 next day; survived
  one laptop sleep with zero lost work).
- Config: `diffusion/configs/demo_v6.yaml`; per-case seeds derive from
  `--seed` {20260718, 314159} + crc32(run_id).
- Analysis is one command: `12_campaign_verdict.py --study
  out/diffusion/demo_v6/generalization --train-range 1:60`.
- Predecessor reports: `out/diffusion/demo/generalization_v5/report.md` (OOS
  diagnosis), `out/diffusion/demo/generalization_v4/report.md` (fixed-study
  methodology), `out/diffusion/demo/generalization_v3/report.md`.
