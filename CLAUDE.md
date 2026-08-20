# CLAUDE.md

Project conventions for AI coding agents (Claude, Codex, etc.) working on InverseRG.

## Project Overview

Diffusion-based inverse renormalization group for lattice field theories.
A score-based diffusion model lifts coarse configurations to fine
configurations so that gauge-invariant observable distributions match direct
HMC; iterating up a matched beta ladder reaches lattice sizes/couplings where
direct HMC suffers from critical slowing down and topological freezing.

Three sibling packages, one per theory. `u2_2d/` is the ACTIVE one; `u1_2d/` is
closed and `su2_2d/` is set aside.

- `u1_2d/` — 2D compact U(1). **CLOSED / frozen** (2026-08-02): the complete
  study — campaign, ESS/exactness program, matching-residual decomposition,
  AIS transport, L=64 head-to-head — is finished and documented. Results in
  `out/u1_2d/paper_appendix/appendix.md`, full story in `docs/u1_2d/NARRATIVE.md`,
  audit in `docs/u1_2d/V2_AUDIT.md`. Do not reopen model-quality work; bug-parity
  fixes only. **Post-closure corrections (2026-08-14/15) are in
  `docs/u1_2d/NARRATIVE.md` §25.5** — read it before quoting Tables S1, S3, S4, S6b
  or S7b, all of which carried numbers from superseded runs, and before
  quoting the exact-P(Q) crutch (§21.6, `PHYSICS_WALKTHROUGH.md` F1).
  **The two owed referee experiments were run 2026-08-15 and are in §25.6**
  (Tables S8–S10): the classical-remedy benchmark, the Zhu et al. head-to-head,
  and the MALA-exactness test. **§25.7 closes the `U1_2D_REVIEW.md` backlog**
  (M3, M4, `norm_type`, validation σ-bias, the citation audit in §26.1, and the
  `topo_weight` follow-up). Two consequences to know before quoting anything:
  Table S3 is regenerated on τ_int-aware records with a denominator of **38,
  not 35** — the three deep-frozen cases were never untestable, the χ² gate was
  silently dropping them — and the `TODO.md` §2 recommendation to adopt
  `topo_weight = 0.3` is **withdrawn**, since it does not move the raw sector
  match rate it would have to act through.
- `u2_2d/` — 2D U(2). **ACTIVE (opened 2026-08-19).** The successor study, and
  the reason it was chosen: 2D U(2) is exactly solvable, and its topology is
  carried entirely by the determinant, which is an honest compact U(1) field —
  so the closed U(1) machinery is reused rather than rewritten, while the group
  is genuinely non-abelian. Links are stored in the NTHMC-compatible split
  representation `U = e^{i phi} q` as `[..., 5]` = `(phi, q0, q1, q2, q3)`.
  Read `u2_2d/README.md` first, then `docs/u2_2d/DESIGN.md` for the
  derivations and the measured results. The design, and the three facts that
  carry it:

  * `psi = wrap(2 phi) = arg det U` is a compact U(1) gauge field, and
    `lgt.lattice.det_links` hands it back in exactly the `[B, 2, L, L]` layout
    every `u1_2d.lgt` routine consumes. **Q is a functional of psi alone.**
    Because det is a homomorphism, the plaquette determinant phase is the plain
    SUM of link phases, so the abelian telescope of `u1_2d` survives verbatim:
    the coarse determinant plaquette is the wrapped sum of the four fine ones,
    exactly, non-abelian group notwithstanding. Sector transport across an
    inverse-RG step is therefore an identity, as in U(1).
  * One inverse-RG step factorizes as `p(psi, q) = p(psi) p(q | psi)`. The model
    generates `psi` only. The SU(2) sector needs no model: at frozen `phi` the
    U(2) local weight is exactly `exp(beta k . q)`, so
    `lgt.local_updates.conditional_su2_sweeps` is an EXACT sampler for
    `p(q | psi)` and leaves `psi` and `Q` bit-for-bit unchanged. Naive inverse
    blocking of the coarse SU(2) part is only the seed; it cannot bias anything.
  * **The joint does NOT factorize** — `(1/2)ReTr P = cos(omega_p) cos(phi_p)` is
    a product, not a sum. Generating the two sectors independently and combining
    them is wrong at O(phi^2 omega^2). Two consequences, both already handled:
    the SU(2) sector must be generated CONDITIONALLY (it is), and `psi`'s own
    marginal is NOT U(1) Wilson at `beta/4`. Integrating SU(2) out of a plaquette
    gives the exact marginal weight `w_det(alpha) = 2 I_1(z)/z`,
    `z = beta cos(alpha/2)` (`lgt.actions.DetSectorAction`), which is Wilson at
    `beta/4` plus a `(3/2) log cos(alpha/2)` measure term. Anything that needs an
    analytic U(1) coupling must call `lgt.exact.matched_u1_beta` (the minimum-KL
    projection), NOT `beta/4`: they differ by 23% at beta = 4 and 0.003% at
    beta = 220.

  **The U(2)-specific result, measured — do not re-derive it.** `U(2) =
  (U(1) x SU(2)) / Z_2`, so `Q` even <=> the ordered product of SU(2) plaquettes
  is +1 and `Q` odd <=> it is -1. An EVEN change of Q is free (the U(1) instanton
  added to `phi`, purely central, `dS = O(beta/V)` — that is
  `central_winding_field`, and `winding_update` defaults to `charge_step=2`). An
  ODD change cannot leave SU(2) alone and no fixed shift field does it cheaply:
  halving the U(1) instanton leaves one plaquette with a spurious -1 at cost
  `2 beta` (dS = 37 at beta = 20, L = 8), and the `U(1)_T` subgroup construction
  costs O(beta L) instead (dS = 110); gauge fixing does not help. The GENERATIVE
  route is unaffected and this is the point: setting `psi` sets `Q`, and the exact
  conditional SU(2) sampler relaxes the monodromy for free (dS = 26-149 after
  `set_topological_charge`, back to ~5 after 25 conditional sweeps). The
  diffusion ladder reaches odd sectors where the classical global move cannot.

  Exactly solvable, and implemented: `lgt.exact` has the U(2) character expansion
  on the torus, `Z = sum_{j,k} (c_{j,k}/d_j)^V` over irreps `(j, k)` with
  `k = 2j (mod 2)` — verified against Weyl integration to 1e-10 — the exact area
  law `<(1/2)ReTr W(A)> = r_fund^A`, and the determinant-sector `P(Q)`, which
  matches heatbath to 1-2% in every sector at beta = 2, 5, 8. Tree-level ladder
  relation `beta_c = beta_f / 4` in all four u(2) directions.

- `su2_2d/` — 2D SU(2). **SET ASIDE (2026-08-03) and NOT in the working tree.**
  It was removed from tracking in `f7bca3b` while the focus moved to
  documenting and publishing U(1). Recover it with
  `git checkout 87fd6fa -- su2_2d` (27 files: quaternion link variables, exact
  group heat-kernel targets, group-manifold HMC, non-abelian curl-head score).
  Its heavy stages were run far enough to localize the first failure — the
  single-plaquette curl basis is incomplete for SU(2) — and no further.
  Do not reference `su2_2d/` paths in commands until it is restored.

The final U(1) checkpoints are `out/u1_2d/checkpoints/score_net.pt` (pipeline)
and `score_net_rkl2.pt` (likelihood/ESS work only). Everything else in
`out/u1_2d/` is reports/figures/summaries — regenerable `.pt` ensembles were
pruned 2026-08-02 (recoverable from git history if ever needed).

**Second prune, 2026-08-18 (1104 MB → 111 MB).** Two classes went:
(i) superseded or zero-reference run directories — `ptbc_benchmark/` (untuned),
`sector_mode_table/` (superseded by `_tau_aware`), `ais_transport_preFoldFix/`,
`ais_transport_rich/`, `generalization_exact_sectors_{b,seed2}/`,
`generalization_fresh_s4/`, `pq_hmc_tail_adaptive/`,
`ode_reweighting_{easy,probes8}/`, `tiling_smoke/`, the seven stray `*.log`, and
the `campaign_state/` + `*/state/` sentinels; (ii) regenerable `.pt` ensembles
inside directories that *are* of record (`generalization*`, `thermalization`,
`validation`, `data`, plus `.png`/`.npz`/`.log` under `gpu_verification/` and
`proj_sigma_ab/`, both of which are process-verification runs whose results live
in their `.json`/`.md`). Every `report.md`, appendix figure, and summary `.json`
survives; all 169 tests, `29_verify_identities.py`, and
`30_assemble_appendix_figures.py --check` pass after the prune.
**The narrative record of all of it stays in `docs/u1_2d/NARRATIVE.md`** — that is the
point of the prune, so a dead `out/` path quoted there is expected, not a bug.
Everything is recoverable from git history (all of `out/` was tracked).
Three directories were *spared* despite looking prunable, because they are live
figure inputs: `ode_reweighting_sweep/` and `model_ess_noguide/` (figures 19,
24, 26) and `thermalization/*_series.npz` (figures 12, 16, via scripts 08/11).

## Key Conventions

### Physics (U(1), and carried to SU(2) where stated)

- Link angles `theta[mu, x, y]` on periodic 2D square lattice, shape `[2, L, L]` or `[B, 2, L, L]`
- `field[:, 0]` = x-links (mu=0), `field[:, 1]` = y-links (mu=1)
- Index convention: `field[batch, mu, x, y]`; dim -2 is x, dim -1 is y
- Wilson action: `S = -beta * sum cos(plaquette_angles)`
- Angles always regularized to `(-pi, pi]` via `atan2(sin, cos)` (`u1_2d.lgt.lattice.wrap`)
- Plaquette: `p(x, y) = ux(x,y) + uy(x+1,y) - ux(x,y+1) - uy(x,y)`, wrapped
- Tree-level coupling relation across one 2x2 blocking step: `beta_c = beta_f / 4`
- 2D U(1) has no phase transition; RG flows go toward strong coupling (beta -> 0)
- U(2) links are `[..., 5]` = `(phi, q0, q1, q2, q3)` with
  `U = e^{i phi} (q0 I + i q_a sigma_a)`; index convention `links[batch, mu, x, y, :]`,
  so dim -3 is x and dim -2 is y (the `u1_2d` convention shifted by the group axis).
  Plaquette `P = U_0(x) U_1(x+0) U_0(x+1)^dag U_1(x)^dag`, same orientation as U(1).
  Action `S = -beta sum_p (1/2) ReTr P = -beta sum_p q0_p cos(phi_p)`.
  Topological charge `Q = sum_p wrap(arg det P) / 2 pi`, rounded.
  Tree-level ladder relation `beta_c = beta_f / 4`, same as U(1).
  `U(2) ~ 4 x U(1)` in the determinant sector — but only asymptotically; use
  `u2_2d.lgt.exact.matched_u1_beta`, never `beta/4`, whenever a number matters.
- SU(2) links are unit quaternions `[..., 4]` (w, v); plaquette word
  `P = U_x(x,y) U_y(x+1,y) U_x(x,y+1)^-1 U_y(x,y)^-1`; action
  `S = -(beta/2) * sum tr P`; 2D SU(2) has trivial pi_1 — no topological
  sectors (that is the point of doing it before 4D).

### Diffusion / Ladder

- Fine ensembles generated by batched HMC (Omelyan for U(1), expmap leapfrog for SU(2))
- Score network trained by denoising score matching on the group heat kernel
  (wrapped Gaussian on U(1); character-expansion kernel on SU(2))
- Beta ladder: matched sequence of (L, beta) rungs; each inverse step doubles L
- Validation compares gauge-invariant observables (plaquette, rectangles,
  Wilson loops, and for U(1) topological charge/susceptibility) between
  generated and reference ensembles; U(1) also has exact character-expansion
  references (`u1_2d.lgt.exact`), SU(2) has `su2_2d.lgt.exact`
- Exactness lesson from U(1) (measured, do not re-litigate): the model's
  density gap is fine-side model error (~1 nat/site mean, 0.02–0.07 std).
  The matching-residual explanation is eliminated by the **within-arm R²_c
  decomposition** (≤6% of fiber log-weight variance is coarse-explainable,
  and a matching residual is a c-only function so it can land nowhere else)
  — *not* by the Villain arm, which corroborates but is confounded. Do not
  retrain a Villain-specific checkpoint to "fix" that arm: the effect is a
  few percent of variance while same-architecture checkpoint variants move
  spreads 2–6× (Table S5), so any cross-model comparison is an order of
  magnitude noisier than its own signal. Closed; see `docs/u1_2d/NARRATIVE.md`
  §18.5 for the full write-up and the general lesson (prefer within-model
  decompositions to cross-arm subtractions for small effects).
  Exactness **must** come from Markov-chain machinery wrapped around the
  proposal — not from the proposal's own likelihood. This is a *design
  directive* for SU(2), not a property the U(1) pipeline delivered: the
  deployed ladder applies **no accept/reject to the proposal** (the only MH
  is inside local retherm sweeps and the instanton hop), so as shipped it is
  a **validated heuristic**, asymptotically exact only in the retherm → ∞
  limit that costs what direct simulation costs. The conceptually clean
  claim is the *seeded* mode: exact HMC from a diffusion seed is
  asymptotically exact within its sector, with the sector supplied by
  transport. AIS bridging reaches its derived floor in 8 of 10 seeds
  (1.97–2.71× spread reduction at the extrapolation case) but did **not**
  lift ESS — it is a validated *mechanism*, not a delivered exactness route.
  The other 2 of 10 diverge by 10²–10³. The cause is the **surrogate's
  regularization**, established by intervention (Table S7c): holding inputs
  byte-identical and varying only a floor on the ridge grid moves held-out σ
  2132 → 43.1 at the extrapolation case, spanning both modes on its own. Both
  divergent seeds had selected the grid's smallest ridge and no converged seed
  did (p = 0.022), with coefficient norms 231/247 vs 40–105.
  Guard on the **surrogate coefficient norm**, not `hmc_acceptance_min` —
  acceptance is downstream and misses cases (at 32:218.6 σ blows up 18× with
  acceptance flat at 0.958). Do not reach for basis width, and do not trust
  `fit_surrogate_cv` to pick the ridge: its held-out folds sit on the fit
  manifold, while the coefficients only explode off it, so CV is blind to this
  failure by construction. More ridge is not monotonically better — 16:55.02
  reverses — so there is no floor to hard-code.
  (Table S7b/S7c, `parse_ais_seed_rate.py`, `40_fold_noise_audit.py`,
  `41_ridge_scan_report.py`.)
- The classical baseline of record is **HMC + winding update**, not PTBC and not
  plain HMC. Measured 2026-08-15 at L = 32 (Table S8): plain periodic HMC is
  fully frozen (0 sector changes in 3000 trajectories at β = 14.15/55.02/218.58),
  the winding update reproduces exact ⟨Q²⟩ to 2% with τ_int(Q²) ≈ 1.2–2.9 for a
  1–18% overhead, and a **properly tuned** PTBC ladder (swap acceptance
  0.68–0.98, τ_int ≈ 3) still costs 25–121× more. PTBC exists to manufacture a
  global topological move for theories that lack one; this theory has an exact
  one, so importing that comparison measures nothing. Do not re-open the PTBC
  arm — `u1_2d/lgt/ptbc.py` and its 20 tests are kept as the record that it was
  checked, and `out/u1_2d/ptbc_benchmark_tuned/` is the data of record (the
  untuned `ptbc_benchmark/` was superseded — its numbers are 45–51× pessimistic
  and its swap-acceptance column is halved by a since-fixed bug — and was
  deleted in the 2026-08-18 prune). Cost claims
  go against `hmc+inst` (0.198 s per independent configuration at β = 218.58).
  If the PTBC arm is ever re-run: it is latency-bound, so use the stacked
  action (`StackedDefectWilsonAction`) on GPU — replicas are then nearly free —
  and time the single-replica arms on CPU, which is faster for them.
- Ladder invariant (use it, it is the design's justification): with
  β_f = 4β_c and L_f = 2L_c, the exact finite-volume ⟨Q²⟩ ≈ V/(4π²β) is a
  **fixed point** of the ladder (Villain: 1.20271 → 1.20334 → 1.20334 →
  1.20334 over four rungs). So the coarse ensemble's P(Q) *is* the fine
  theory's P(Q) — sector transport is an identity, not an approximation —
  and climbing the ladder is a continuum-limit trajectory at fixed physical
  volume.
- Validation caveat carried to SU(2): observable-level agreement is sharp
  (plaquette to ~2 parts in 10⁴) but does not constrain the density (KL is
  ~450–2100 nats/config). Residual model error concentrates in *extended*
  observables — std(z) grows 1.09 → 1.44 from W(4×4) to W(12×12). Report
  large-loop dispersion, not just plaquette/W(2×2)/W(4×4).

### Code Style

- No comments that merely narrate what code does
- All tensor operations handle both single and batched inputs
- Use `torch.no_grad()` for measurement computations when not inside training
- Preserve backward compatibility when adding new methods

### Testing

- `pytest u1_2d/tests -q` (169 tests) and `pytest u2_2d/tests -q` (84 tests);
  `su2_2d/tests` only exists once su2_2d is restored from git — see above
- `python u2_2d/scripts/09_verify_identities.py` — the exact U(2) identities
  (group representation, gauge invariance, the determinant telescope, analytic
  force vs autograd, microcanonical overrelaxation, winding parity, the character
  expansion vs Weyl integration). Seconds; must pass.
- `python u1_2d/scripts/29_verify_identities.py` — the exact physics identities
  (Q integrality, gauge invariance, blocking telescope, curl-head completeness,
  <Q^2> ladder fixed point, area law, instanton cost). Seconds; must pass.
- `python u1_2d/scripts/30_assemble_appendix_figures.py --check` — verifies the
  27 appendix figures match their canonical sources. Run before submitting.

## File Layout

```
u2_2d/            -- ACTIVE 2D U(2) study (configs, lgt, model, pipeline, scripts, tests, validate)
u1_2d/            -- CLOSED 2D U(1) study (configs, lgt, model, pipeline, scripts, tests, validate)
su2_2d/           -- SET ASIDE, not in the tree (git checkout 87fd6fa -- su2_2d)
docs/u1_2d/       -- NARRATIVE.md (full mathematical story), V2_AUDIT.md (final U(1) audit),
                     PHYSICS_WALKTHROUGH.md, U1_2D_REVIEW.md, PAPER_OUTLINE.md, READING_GUIDE.md
docs/u2_2d/       -- DESIGN.md (U(2) derivations and measured results)
docs/             -- Field_transform.html (NTHMC note on the U(1) vs U(2) field transformation)
out/u2_2d/        -- U(2) outputs: data, checkpoints, ladder, validation
out/u1_2d/        -- U(1) results of record: reports, figures, summaries, final checkpoints
out/su2_2d/       -- SU(2) outputs (untracked; only if su2_2d is restored)
artifacts/        -- gitignored scratch (safe to delete)
```

The sibling `NTHMC` repository (outside this tree, at `../NTHMC`) holds the
JAX-based 2D U(1) and 2D U(2) HMC and neural field-transformation code. `u2_2d`
deliberately matches its split representation, plaquette orientation and
determinant-phase topological charge, so configurations are interchangeable. Two
deliberate differences: `u2_2d` drops NTHMC's additive `beta V` constant from the
action to match the `u1_2d` sign convention, and rounds the topological charge
rather than using NTHMC's `floor(0.1 + .)` offset.

## Virtual Environment

A project-local virtualenv is at `.venv/` (gitignored).

**Always use the venv Python** — never the system Python:

```bash
# Windows
.venv/Scripts/python.exe -m pytest u1_2d/tests -q
```

Torch must come from the CUDA 12.8 index — the RTX 5060 is Blackwell (sm_120)
and pre-cu128 wheels report `cuda.is_available() == True`, then die at the first
kernel launch. `utils.configure_device` checks for this and refuses to start.

```bash
.venv/Scripts/pip install --index-url https://download.pytorch.org/whl/cu128 torch
.venv/Scripts/pip install -e ".[dev]"
```

## Compute (this machine)

**Current: RTX 5060 Laptop (8 GiB, sm_120) + Ryzen 7 260 (8c/16t), CUDA 12.8.**
`device: auto` resolves to `cuda`; override with `--device` or `U1_2D_DEVICE`.
8 GiB is ample — the whole v3_scale training set on-device is well under 1 GiB.

**Pick the device per stage from measurement, not intuition.** Batched HMC is
kernel-launch-bound at this project's volumes and is often *faster on CPU*
(sweeps/s, GPU÷CPU): 16 chains — L=16 0.43×, L=32 0.50×, L=64 1.36×; 64 chains —
L=16 0.79×, L=32 1.13×, L=64 3.08×. So the crossover is ~L=64 at 16 chains and
~L=32 at 64 chains. Model sampling and training always want the GPU.

| stage | device | why |
|---|---|---|
| 01 data | **cpu**, 8 shards | pure HMC at L≤32 |
| 02 train | cuda | score net |
| 03 ladder | cuda | sampler-dominated |
| 04 validate | **cpu** | reference HMC at L=16/32 |
| 05 therm | cuda | 64-chain baselines at L≥32 |
| 06 study | cuda | ladder sampling dominates |

**U(2) HAS A DIFFERENT DEVICE RULE FROM U(1) -- measured 2026-08-19, do not
carry the U(1) table over.** GPU/CPU trajectory rate for `u2_2d` batched HMC
(Ryzen 7 260 at one torch thread vs RTX 5060):

| L | chains | cpu traj/s | gpu traj/s | gpu/cpu |
|---|---|---|---|---|
| 8 | 32 | 10.05 | 5.18 | 0.52 |
| 16 | 32 | 3.93 | 5.26 | 1.34 |
| 16 | 64 | 2.13 | 5.30 | 2.48 |
| 32 | 32 | 1.15 | 5.36 | 4.67 |
| 32 | 64 | 0.58 | 4.81 | 8.30 |
| 64 | 64 | 0.12 | 4.88 | 39.96 |

The crossover is **L = 16**, not L = 64 as it is for U(1), because a quaternion
link carries ~6x the arithmetic of an angle so each launch pays for itself two
factors of two earlier. GPU throughput is FLAT at ~5 traj/s from L = 16 to
L = 64 -- purely launch-bound -- so on the GPU the large lattices are nearly
free, and the right move is to run the L = 8 rungs on CPU and everything else on
GPU *concurrently*. `u2_2d/scripts/run_stage01.ps1` does exactly that (3 CPU
shards + 4 GPU shards). Heatbath crosses over at the same point (L=32/64ch:
1.73 cpu vs 10.83 gpu sweeps/s).

Two other measured U(2) speedups, already applied: `lattice.staples(links, mu=)`
computes one link direction instead of both (the checkerboard sweeps update one
at a time, so computing both wasted exactly half of every heatbath and
overrelaxation sweep); and stage 01 thermalizes with heatbath + overrelaxation
before HMC (`thermalize_sweeps`), which replaced 2000 burn-in trajectories with
60 sweeps + 300 trajectories at L = 32, ~7x cheaper. Both are exact updates of
the same action, and the plaquette-vs-closed-form check is printed every run.

**Long runs: hold the machine awake with
`powershell -ExecutionPolicy Bypass -File u2_2d/scripts/keep_awake.ps1`.** It
calls SetThreadExecutionState(ES_CONTINUOUS), needs no administrator rights, and
releases automatically when the process exits -- there is no global setting left
behind to undo. Do not use a key-pressing loop.

**Parallelism: fan out over units, not threads.** Both heavy stages are
latency-bound — 01 holds one core, 06 holds the GPU at ~32% — and the batch
sizes are fixed by the physics, so the only lever is running units
concurrently. Threads inside one unit make it *worse*: 01 measures 154
sweeps/s on 1 torch thread, 142 on 8, 91 on 12.

```bash
# 01: N = physical cores, one thread each. 21.7 min -> 3.2 min.
for i in 0..7: 01_generate_data.py --shard $i/8 &   # U1_2D_TORCH_THREADS=1
01_generate_data.py --merge-shards

# 06: N = 3-4 on 8 GiB (each shard carries its own CUDA context + model)
for i in 0..3: 06_generalization_study.py --shard $i/4 --out-dir DIR &
06_generalization_study.py --merge-shards --out-dir DIR
```

`u1_2d/scripts/shard_runner.py` holds the helper and the full contract a
shardable stage must honor (own per-shard result file, aggregates deferred to
the merge, round-robin so expensive families spread evenly). Read it before
adding `--shard` to another stage.

**Device convention — the bug class CPU-only machines cannot show you.**
Ensembles are CPU-resident (`load_ensemble` pins `map_location`, `save_ensemble`
calls `.cpu()`, `generate_fine_from_coarse` returns CPU chunks); only the model
forward and the HMC integrator run on `device`. `run_hmc_ensemble` is the **one**
function that returns tensors on its `device`, so normalize its output before it
meets anything else. Three real bugs came from violating this (06, 27, 28, plus
`model/ais.py` `g_of` converting dtype but not device). Guard:
`python u1_2d/scripts/32_gpu_smoke.py` runs every compute-bearing script once on
the GPU and flags `DEVICE-BUG` separately from ordinary failures.

Historical (Snapdragon X Elite, CPU-only) — still the recipe if a run moves back
to that laptop: EcoQoS as-is, **no priority games**, `U1_2D_TORCH_THREADS=8` as
the single-process ceiling, **never parallel worker processes** — priority
elevation + parallelism hard-crashed that machine twice on 2026-07-24. Launch
detached long runs via Windows scheduled tasks (`schtasks /Run /TN <name>`), not
from an editor-attached shell; drivers are sentinel-resumable.
