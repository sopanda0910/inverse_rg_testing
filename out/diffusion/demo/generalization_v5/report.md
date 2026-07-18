# Generalization v5: dense beta track, in-sampler charge projection, and the out-of-sample verdict

Model: v4 checkpoint (`out/diffusion/demo_v4/checkpoints/score_net.pt`) — 18 training
rungs: L=8 {1,2}, L=16 {1,2,3,4,5,6.5,8,10,14.1464,25,55.0237}, L=32
{2,4,6.5,14.1464,55.0237}, soft-topological-charge penalty (topo_weight 0.1).
Sampling now applies the coarse-charge projection DURING the reverse SDE
(every 10 steps below sigma = 0.5, plus the final exact pass). Runs 2026-07-17/18.
Study: 35 cases — matched track beta_f = 1.49 -> 218.6 (A/D, 16 cases), deliberate
coupling mismatches (B, 7), lattice-size scan to L=128 (C, 2), and the
**out-of-sample track (E, 10)**: matched pairs whose base AND target both sit
mid-gap, >= 0.09-0.34 log-distance from every training coupling. A/D and E ran at
two independent seeds each (`seeds/s2/`).

## 1. Executive summary

The out-of-sample track splits the story into three claims with different strengths:

1. **Pipeline observables generalize genuinely, everywhere.** All 10 OOS cases at
   both seeds match exact values: plaquette/Q^2 z-scores scatter within +-2-3 with
   no systematic sign, P(Q) chi^2 passes 19/20 seed-cases, and the deepest
   off-grid extrapolations (beta_f = 138, 178 — >2.5x beyond any training
   coupling) are among the cleanest (Q^2 z ~ -0.5, chi^2 p ~ 0.8). This is not
   grid recall.
2. **The raw model's topology improvement is mostly in-sample.** Mean spurious
   Q^2 excess (pre-enforcement): 3.26 on the training-adjacent track, but
   **4.57 on the OOS track** — statistically back at the v2 baseline (4.67).
   The v2 -> v3 -> v5 "improvement" (4.67 -> 3.71 -> 3.26) is largely proximity
   to the densified grid. The pipeline stays clean because charge enforcement +
   retherm absorb exactly this — by design, not luck.
3. **Raw-seed thermalization speed is partly in-sample, and has an absolute
   wall.** In beta_f = 10-55: matched in-sample seeds are uniformly fast
   (t_therm = 1-15 at the trained pairs; median ~12, zero "never"s), OOS seeds
   are erratic (7 to 91, one never; median ~60). Beyond beta_f ~ 55-70,
   **every** raw seed — in-sample or not — fails the immediate |z|<=2 test:
   the dense D/E tracks locate a wall between 55 and 78 that grid proximity
   does not move. Retherm (the actual pipeline) remains what carries those rungs.

## 2. What changed vs v4

- **In-sampler charge projection** (`charge_projection_sigma=0.5`, interval 10 in
  `generate_fine_from_coarse`; `step_callback` hook in `sample_ancestral`): the
  topological sector is corrected while noise remains, so the sampler relaxes the
  instanton strain instead of leaving it to rethermalization. Affects the
  pipeline/seed path only — the study's raw-topology metrics still sample with
  enforcement fully off.
- **Denser training grid** (demo_v4.yaml): L=16 rungs added at beta = 3, 10, 25.
- **Denser study track**: A gains bc = 1.5, 5; D extends to bc = 20, 30, 40
  (beta_f ~ 78, 118, 158); new part E (OOS, above). 35 cases total.
- 05_hmc_thermalization gained `--skip-cached` (completed cases rebuild report
  entries from disk in ~8 s instead of ~5 min of HMC redo).

## 3. Pipeline-level results across the full track

Both seeds, matched + OOS tracks interleaved (beta_f = 1.49 ... 218.6, 26 cases):
every case consistent with exact within seed scatter; the densified upper track
(78, 118, 158) passes with |z| <= 1.3 at seed 1. Weakest OOS point: E_bc4.5
(beta_f = 16.2, the 14.15<->25 gap): P(Q) chi^2 p = 0.04 and one seed's smallest
Wilson-loop KS = 0.004 with same-sign Q^2 z ~ +1.6 at both seeds — worth a
third seed if this gap matters for deployment. The historic crossover case
(2 -> 6.105) remains clean. Full tables: `summary_tables.md` (parts A, D, E, B, C)
and `seeds/s2/summary_tables.md`.

## 4. Raw topology transport: in-sample vs out-of-sample

| track | mean raw Q^2 excess over base | n |
|---|---|---|
| v2 checkpoint (2026-07-16 baseline) | 4.67 | 11 |
| v3 checkpoint, in-sample A/D | 3.71 | 33 |
| v5 checkpoint, in-sample A/D | 3.26 | 16 |
| **v5 checkpoint, OOS track E** | **4.57** | 20 |

Per-config Q match rates stay 0.03-0.2 everywhere (lowest at large volume:
0.06 / 0.03 at L=64 / L=128 — the ~6e-3-per-site spurious-charge density scales
with V). Verdict: the topo penalty + dense grid reduce spurious charge only near
training couplings; the zero-mode bound (no curl-form loss can pin integer Q)
stands, and deterministic charge enforcement remains structurally necessary.

## 5. Thermalization across beta and L: the honest map

All 35 cases (t_therm = slowest Wilson observable, chain-count matched;
"2 tau" = standard HMC's sampling interval):

- **beta_f <= 10** — seeds and HMC comparable (t_therm 2-47 vs intervals 2-14);
  nothing to win here, as always.
- **beta_f 10-55, in-sample matched** — the pipeline's home turf: t_therm =
  3 (10.0), 1 (14.15), 10 (22.3), 15 (55.0) vs intervals 11-26, with hot HMC
  frozen and cold burn-ins of 140-500. The v4 never-zone at 16-30 is gone.
- **beta_f 10-55, OOS (E)** — erratic: 91 (11.7), 7 (16.2), 58 (21.5),
  never (34.4), 64 (45.6). A mild proximity trend plus large case-to-case noise;
  off-grid seeds typically still beat cold-start burn-in (~200-500) but not the
  HMC interval.
- **beta_f >= 70, everyone** — never, for in-sample (D_bc20/30/40/55) and OOS
  (E_bc18/35/45) alike: the raw-seed wall between beta_f ~ 55 and 78 is set by
  absolute coupling, not grid proximity. Note the *pipeline* ensembles at these
  couplings still pass all observable tests — 16 retherm sweeps carry them —
  and plain HMC has no path at all there (hot never converges, cold pins Q = 0,
  intervals 15-80 with tunneling suppressed ~ exp(-2 beta)).
- **Size scan (trained pair 4 -> 14.15)**: t_therm = 3 at L=64 and 10 at L=128 vs
  intervals 28 and 66 — the volume margin survives and grows.

## 6. Where this leaves the project

- Safe headline: *the inverse-RG pipeline (diffusion + charge enforcement +
  Q-hop retherm) reproduces exact observables across beta_f = 1.5-218.6 —
  including couplings and volumes far outside training — where plain HMC is
  topologically frozen.* Supported in- and out-of-sample, two seeds.
- Narrow headline: *raw seeds thermalize faster than the HMC sampling interval*
  — true at trained couplings for beta_f in [10, 55] and at L = 64/128 on the
  trained pair; NOT uniform off-grid, and false for everyone above beta_f ~ 70.
- If uniformly fast off-grid seeds matter: densify the grid where deployment
  needs it (the mechanism is confirmed), accept the retherm cost, or explore
  sector-conditioned training data at high beta. The beta_f >~ 70 wall will not
  yield to grid density.

## 7. Artifacts

- `summary.json` / `summary_tables.md` / `figures/` — 35-case study, seed 1
- `seeds/s2/` — A/D/E replica at seed 2
- `fig_raw_topology.png`, `fig_matched_scan.png`, `fig_mismatch_scan.png`,
  `fig_size_scan.png` — scans (seed 1)
- `thermalization/report.md` + `timescales.png`, `beta_scan.png`,
  per-case `*_relaxation.png` — the 35-case benchmark
- `run.log` — full chain provenance (STAGE_* sentinels, 2026-07-17 08:19 ->
  2026-07-18 12:54)
- Prior campaign for comparison: `../generalization_v4/report.md` (v3 checkpoint,
  3 seeds + v2 baseline)
