# u1_2d Final Audit — Known Problems and Remaining Work

**Date:** 2026-08-02
**Scope:** full review of `u1_2d/` (model core, lattice/validation layers, exactness scripts 19–26, campaign result artifacts under `out/u1_2d/`) conducted before moving on to SU(2) 2D.

**Verdict up front:** the load-bearing math is correct everywhere it was checked — curl-head gauge structure, wrapped-Gaussian DSM target, probability-flow ODE signs and torus Jacobians, SNIS/ESS formulas, SMC incremental weights, HMC reversibility (verified numerically, |dH| ~ dt²), and `lgt/exact.py` against independent Monte Carlo. The five fine-tune negatives (mlft, rklft, rkl2, big-net RKL, score-correction head) were re-derived as mathematically correct implementations: they are real converged negatives, not bugs. Nothing below blocks the SU(2) move. The document lists what is genuinely still open, in priority order.

---

## 1. Highest-value open analysis: matching residual vs model error

Nothing yet separates the **coarse-action matching residual** from **model error** in the log-weight spread. The fiber weight decomposes as

```
log w = [c-only term: Wilson-family projection residual of the true blocked action] + e(x, c) + const
```

A c-only term **cannot be removed by any fine-score fine-tune**. The observed failure pattern — uniform ~0.02–0.07 nats/site across (L, β), every model-side lever failing (ML at two capacities, single/multi-case RKL, 724k-param scale-up, correction head), rkl2 halving but never closing the gap — is exactly the signature a substantial c-side floor would produce.

Two cheap probes:

1. **Regression:** regress the stored `log_weights` (already in every `reweighting_results.json`) against coarse observables (plaquette, rectangles, Q², higher characters). Afternoon of work, zero simulation.
2. **Villain control:** run `scripts/19_ode_reweighting.py` with `action_type: villain`, where β/4 matching is *exact* (`lgt/blocking.py:78`). The Villain spread is pure model error by construction; Wilson − Villain is the matching floor.

If the floor is significant, the fix is cheap and preserves validity: sample the coarse base from an improved action `S_matched + Σ g_k O_k` (the `match_coarse_beta(n_characters>1)` machinery already exists) and use that density in the weight. Either outcome — "gap is matching residual" or "gap is model error, program definitively closed" — is worth having before SU(2).

**Related insight:** the score-correction head's 2–6× negative result is partly explained by shadowing. In `_effective_score_fn` (`model/likelihood.py:200-215`) the physics blend wraps the *corrected* model, and the blend weight w → 1 as σ → 0, so the trained (a, b) head is multiplied by (1 − w) → 0 exactly in the small-σ regime where the terminal density gap lives. The head never had leverage where it was needed.

---

## 2. Confirmed bugs

None invalidate published numbers, but they should be fixed before artifacts are considered reproducible.

### Active

| # | Location | Problem | Impact |
|---|---|---|---|
| B1 | `model/train.py:227-274` | Validation loss (best-checkpoint criterion and early-stop signal) is computed on the **raw** model, but `save_checkpoint` saves the **EMA** weights; additionally the in-memory return (`model.load_state_dict(ema_state)`, line 274) is *final-epoch* EMA while the disk checkpoint holds *best-epoch* EMA. | Best-epoch selection measures the wrong curve; return value and artifact disagree on early-stopped runs. ~1 h fix: validate with EMA weights, and seed the val-noise `randn` so selection isn't jittered by noise realization. |
| B2 | `model/likelihood.py:248` | `conditional_log_likelihood` passes the same `seed` to every batch chunk (unlike `conditional_ode_sample`, which offsets `seed + start` at line 286). | Hutchinson probes correlated across the ensemble — still unbiased, but the noise-averaging over configs is weaker than it looks. |
| B3 | `model/likelihood.py:103,150` | `torch.manual_seed(seed)` inside library functions clobbers **global** RNG state. | Anything using global RNG later in-process is silently coupled to the ODE seed. Script 19 escapes only because `independence_metropolis` uses its own generator. Footgun for the SU(2) port — use a local `torch.Generator`. |
| B4 | `scripts/24_smc_ladder.py:150` | Resampled-column observables use naive `std/sqrt(n)` sem, treating post-resampling duplicates as independent. | At unique-fraction ~0.5 the sem is understated ~√2×; resampled z-scores look better than they are. Unique fraction is reported but never folded in. |
| B5 | `scripts/23_ess_progress_figures.py:181` | Reads `r["monitor"]["log_w_std"]`, but current `22_multicase_rkl.py` writes plural `out["monitors"]` (22:197). Works today only because the on-disk history has the old singular schema. Also hardcodes log-scraped constants (`-0.8867` line 159, `136.86` line 185). | Re-running 22 then 23 raises `KeyError: 'monitor'`; constants silently wrong if runs are redone. |
| B6 | `out/u1_2d/data/matching.json` | Overwritten, not appended — only the 4 scale-up entries (β_f 43.9–50.2) remain. | Anything re-reading matching results for the original ladder is missing entries. Check before regenerating anything that depends on it. |
| B7 | `out/u1_2d/run.log` | Terminal state is the VERDICT stage crashing (FileNotFoundError, `CHAIN_DONE_WITH_ERRORS`) on 07-31. `verdict.md` exists, so it was evidently rerun, but the log of record ends in an error. | Cosmetic/reproducibility. Rerun verdict via the fixed script so the log closes clean. |

### Latent (don't fire in the shipped pipeline, but are traps)

| # | Location | Problem |
|---|---|---|
| L1 | `model/train.py:250,268` | With `checkpoint_path=None` and `early_stop_patience>0`, `best_epoch` stays −1 and training halts at epoch patience−1 regardless of loss. |
| L2 | `model/schedule.py:71-73` | `discrete_sigmas` does `float(low)` — crashes on per-sample tensor beta, contradicting `effective_sigma_min`'s documented tensor support. |
| L3 | `model/score_net.py:74-75` | `coarse_conditioning_channels` unsqueezes a `[2, L/2, L/2]` input but never squeezes the output back — returns `[1, C, L, L]`, violating the batched/unbatched convention. |
| L4 | `model/score_correction.py` | `CorrectedScore` exposes only `.score()`, no `forward` — any future attempt to DSM-anchor the corrected model via `train.denoising_loss` fails confusingly. |
| L5 | `scripts/22_multicase_rkl.py:73` | "Disjoint rotating slices" overlap after wraparound (`(round_idx * n_eval) % (pool - n_eval + 1)`). Never wraps at current settings (300 steps / eval-every 50); docstring overclaims. |
| L6 | `scripts/19_ode_reweighting.py:55-57` | `unweighted_mean` sem for the `hmc_ref` column: 16 chains, thin=5, no autocorrelation correction — understated exactly at high β where thin=5 does not decorrelate topology. (Generated-ensemble column is fine; those are independent.) |

Cosmetic: `lgt/exact.py:42-43` `_q_cutoff` ignores its `volume` argument; `lgt/hmc.py:135-137` folds burn-in into reported `acceptance_rate`; `BatchedHMC.force` returns +∇S despite the name (usage is sign-correct).

---

## 3. Statistical rigor of the paper-facing validation

This is where the most defensible external criticism of the current numbers lives.

1. **The main validation table never uses τ_int.** `validate/report.py:131-150` computes every error via `binned_mean_err` with a fixed 20 bins and no autocorrelation-aware bin sizing. `integrated_autocorrelation_time` exists (`stats.py:84`) but is only used in `freezing_diagnostics`. For the deliberately no-Q-hop reference HMC at high β, τ_int(Q) is enormous by design, so `ref_error` on Q²/χ_top is badly underestimated and every topology `z_ref` is unreliable. Fix: scale binned errors by √(2τ_int) or auto-size bins to ~2τ_int draws per chain. Bin length in draws vs τ is currently never checked.
2. **The default report validates the charge-transport machinery, not the model.** `enforce_coarse_charge=True` is the ladder default (`pipeline/ladder.py:84`) and `scripts/04_validate.py:88` explicitly filters out the `_raw_` ensembles that `03_run_ladder.py` already saves. The Q-histogram χ² test is largely testing the coarse base histogram plus the instanton map. The report needs a labeled **raw pre-enforcement column** — data is already on disk; remove the glob exclusion in a second pass. This is the single most important honesty upgrade for the topology claims.
3. **τ_int(Q) of the ladder ensemble is computed on the interleaved chain-major ordering** (`04_validate.py:130-135`), where correlated samples sit n_chains apart, so windowed τ_int reads ~0.5 regardless. The report-header claim "ladder ensemble is i.i.d. across configs by construction" (line 147) is wrong — fine configs inherit the coarse HMC chain's autocorrelation through conditioning. Reshape to `[n_draws, n_chains]` and compute per chain (`normalized_autocorrelation` already supports batched chains).
4. **KS and χ² p-values assume i.i.d. samples** (report.py:149, 207). With an autocorrelated reference the effective N is smaller; p-values overstate significance (anti-flatters the model — spurious rejections — but untrustworthy either way). Use n_eff = N/(2τ_int) or drop them.
5. **Reference-topology columns at high β compare against a deliberately frozen baseline** — fine for the freezing narrative, but the table doesn't distinguish "reference is wrong" from genuine disagreement; only the exact columns carry weight there and a reader of report.md can't tell. Label it.
6. Minor: χ_top row centers per-config values on the full-sample mean before binning (report.py:196-198) — mild double-dipping, negligible at these N. Creutz jackknife (observables.py:69-74) assumes independent configs — same τ_int caveat.

---

## 4. Theoretical / methodological concerns (documented, mostly acknowledged in-code)

1. **The exactness weights are the density of an approximation to the sampler, not of the sampler.** Samples come from the *discrete* Heun map; `log q` is the trapezoid integral of the continuous divergence — the exact log-Jacobian of the discrete map differs at O(h³)/step. Hutchinson noise adds a config-dependent Jensen bias that self-normalization does not fully remove (biases reweighted estimates) while the extra log-weight variance *deflates* measured ESS — the effects don't cancel. These shrink with steps/probes, not with N. Acknowledged in `model/likelihood.py:36-41`; the probes8/steps240 stability points bound it. If exactness were ever a headline claim, either compute the exact discrete log-Jacobian once as calibration (L=8/16) or make the step/probe-doubling stability check a required automated assertion on any quoted ESS.
2. **`log q` at σ_min is the density of a smeared model, and the smearing width varies with β** (σ_min = min(0.03, 0.1/√β)). ESS is unaffected (samples and density both live at σ_min), but any cross-β "mean log q" comparison conflates model quality with reference-measure choice. Needs a one-line caveat wherever quoted.
3. **Sampling below the trained noise floor.** Training used `sigma_min_beta_coef: 0.3`; the ladder/ESS scripts rebuild schedules with `0.1`. For β ∈ (11, 100] the grid reaches σ where the network never saw targets; the physics blend covers it (w ≈ 0.99), but for β ≈ 5–11 the gate factor is only ~0.5–0.8. This is a deliberate wrinkle, but it silently couples "ladder floor coefficient" to "blend must stay on" — an implicit contract that **will not transfer to SU(2)** (no analytic small-σ score there).
4. **Consistency guidance is a non-score drift** — valid for the PF-ODE change-of-variables (holds for any smooth drift), so weights remain exact as built; but any future modification that makes guidance non-smooth or clamped silently breaks CoV validity. Charge projection is correctly excluded from the density for exactly this reason.
5. **SMC transport arm at level ≥ 2 is biased, not merely noisy.** The per-level weight assumes coarse ~ exp(−S_{β_{l−1}}), which fails for the transport arm (unweighted lift with unknown density); SNIS there corrects only the last lift. The module docstring in `24_smc_ladder.py` states this correctly; the report line at 24:191 ("noisy rather than biased") overclaims for that arm — fix the wording.
6. **Exact-sector mode leans on the exactly known finite-volume P(Q)** — a crutch specific to this solvable theory. (2D SU(2) has trivial π₁, so the successor sidesteps rather than tests this; say so explicitly in the paper.)

Explicitly verified as **non-issues**: wrapped-Gaussian score at large σ (11 windings at σ=6, error ~e⁻⁸); curl head exactly orthogonal to holonomy zero-modes; blend/guidance line-for-line identical between sampling (`pipeline/ladder.py:137-151`) and likelihood (`likelihood.py:200-214`); β_eff = β/(1+4βσ²) variance-addition argument; symmetry-op index formulas; Tweedie denoise in the topo penalty; ancestral SMLD variance schedule; `reverse_kl_terms` pathwise gradient; systematic resampling scheme in 24.

---

## 5. Results-side weaknesses (from the artifacts, with numbers)

1. **ESS never lifts off the 1/N floor on the real theory.** Every fresh-seed verification row: ESS/N = 0.0156 (= 1/64) for baseline, mlft, rklft, rkl2 at all four reference cases (`ess_chain/chain_report.md`, `scale_report.md`). Sole exception: σ_min-coef 0.03 knob, ESS/N 0.0309 (log-w std 42.1 → 24.0 at 16:55). Per-site density gap after the whole program: 0.02–0.07 nats/site vs the ~0.005 bar the appendix sets. Every reweighted z-score in `exactness_report.md` is NaN or single-sample degenerate (e.g. 32:110 reweighted Q² = 4 ± 1.5e-22 — one weight dominating). The exactness route is machinery-validated on the wrapped-Gaussian toy only; frame ODE-likelihood strictly as a diagnostic (the appendix's closing paragraph already does — check earlier sections don't oversell).
2. **Raw ODE samples fail observables outright; correctness is 100% carried by the MCMC wrapping.** Frontier tables (no retherm, no projection): Wilson z-scores −14.3 (16:8), −13.0 (16:14.1), −11.1 (16:55) for rkl2; +12.5 (8:2), +10.3 (16:4) for the v2 checkpoint; raw plaquette z = **−68.4** at 32:110. Stated honestly in the appendix; it is the structural weakness of the generative model per se.
3. **Head-to-head vs instanton-HMC is single-volume (L=32, Table S1).** The entry-cost-explosion claim has no L-scaling evidence; the tail-cost volume-independence claim rests on one L=64 point (Table S4). One L=64 column (β = 55 and/or 218.6) would harden the paper's core claim; the machinery exists.
4. **Raw spurious Q² excess grows with volume**: mean excess **28.15** at L=64/128 (part C), 7.14 (part F), vs 1.7–2.7 for L=32 tracks; raw charge-match rate 0.21. Exact-sector mode rescues (χ² failures 5/35 → 1/35, worst |z| 11.8 → 2.8) but via the theory-specific P(Q) crutch. This is the one model deficiency that grows in exactly the scaling direction the method exists for — the obvious referee question. At minimum, one plot of raw excess vs V.
5. **Marginal Wilson failures slightly above the multiple-testing expectation**: D_bc14.1464 (β_f = 55.02) fails plaq (z = −2.93) *and* W22 (z = −3.47) together; B_bt20 plaq −3.19; A_bc8 −2.71; F_L64 seed-1 W22 +3.03 (seed-2 −0.69). ~0.2 expected beyond 3σ over ~76 tests. Fresh-seed higher-stats reruns classify these in hours; the D-track first rung failing both together is the priority.
6. **Fine-tune history summary** (all flat after ~step 50 — plateaus are real, not undertraining):

   | Variant | Outcome | Numbers |
   |---|---|---|
   | σ_min 0.03 knob | small win | std 42.1 → 24.0; ESS/N 0.030 → 0.031 |
   | mlft | negative | val log q improved, deployed std worse everywhere (32:218.6: 163.7 → 293.6) |
   | rklft | negative | own eval ESS 0.031 → 0.062, but 32:218.6 std **2202** (extrapolation destroyed) |
   | rkl2 (guarded multi-case) | only real win | halves spread at every case (17.9→15.1, 42.1→19.7, 84.3→40.8, 163.7→102.6); guard blocked 4/6 saves; ESS/N still 0.0156 |
   | score_correction | negative | 2–6× worse on disjoint grid (16:25: 18.1 → 105.8); see §1 shadowing |
   | big net + RKL | negative | never improved under guards; no checkpoint saved (legitimately empty row in `scale_report.md`) |

7. **SMC ladder: dead negative.** Per-level ESS/N = 0.005, unique-ancestor fraction 0.01, SNIS z up to 10⁶. No weight diversity to harvest; correctly discarded.
8. **Wording inconsistency:** appendix says "consistent with all-zero charge content" for deep-frozen F cases while the verdict table records Q² z = **+inf** (F_L32_bc100, F_L32_bc218.58). Exact ⟨Q²⟩ ≈ 0 makes z ill-defined — say that instead.
9. **Scale chain status:** finished (CHAIN_DONE 2026-08-02 03:44). Big net (hidden 80, depth 5, +24 L=32 rungs) helps in-distribution (32:55 std 49.6 vs 84.3) but **worsens extrapolation** (32:218.6: 211.9 vs 163.7). Observable-level ladder passed through L=64 (β=55) and L=128 (Wilson passes; topology at L=128 only via exact-sector mode, p 0.005 → 0.39).

---

## 6. Untried mechanisms with credible payoff

1. **AIS / tempered-transition correction at the fine level** — the one genuinely different mechanism not yet attempted. Retherm is excluded from the exactness route because it breaks density tracking; but MCMC transitions leaving interpolating distributions invariant need *no* density tracking (annealed importance sampling / stochastic-normalizing-flow / CRAFT pattern). From each ODE sample with its valid log q, run K short local-update/HMC sweeps through a geometric bridge q^{1−t}p^t, accumulating standard AIS incremental weights — splitting one 10–40-nat gap into K small increments. All ingredients exist (`lgt/local_updates`, HMC, valid initial density). Honest caveat: expect wins at moderate β; topological-sector errors will not anneal away cheaply at L=32, β≳200. Medium cost; highest expected ESS payoff of anything left; distinctly *not* another fine-tune.
2. **Exact log-Z / free-energy certificate — free, and unique to this theory.** 2D U(1) has exact Z = Σ_q c_q^V via the character expansion already in `lgt/exact.py`. The SMC ladder's unnormalized incremental weights already estimate Z_l/Z_{l−1} (one extra line in script 24), and the mean SNIS log-weight should reproduce the exact ΔF between matched and target couplings — an independent certification of the whole `snis_log_weights`/`importance_ess` stack beyond the toy unit tests. No SU(2) follow-up will have this check.
3. **ESS-measurement robustness (small):** stability controls (8 probes, 240 steps) were run at only one case (16:55); n=64 throughout. Cheap to widen if final numbers are quoted.

---

## 7. Test coverage gaps

- `validate/stats.py` nearly untested: `integrated_autocorrelation_time` (feeds the freezing claims) has no test — an AR(1) chain gives closed-form τ_int = (1+φ)/(2(1−φ)). `binned_mean_err`, `jackknife`, `fit_exponential_relaxation`, `z_score` untested.
- No HMC reversibility or dH ~ dt² test (both were run by hand in this audit and pass; cheap to pin).
- No exact-P(Q)-vs-sampling test (existing tests check normalization/internal consistency only; β=1.5, L=8 heatbath+OR+Q-hop matches exact ⟨Q²⟩ 1.769(25) vs 1.768 — a good ~60 s test at reduced statistics).
- `rectangle_x/y_angles`, `polyakov_loop_angles`, `plaquette_correlator`, `freezing_diagnostics`: zero coverage (the rectangle identities are one-line asserts against `wilson_loop_angles`).
- No numerical-row-correctness test for `validate_ensemble` (only plot-smoke tests).
- If the Villain control (§1) is pursued: an end-to-end Villain-action SNIS test would make the whole weight chain testable against exact observables with no matching confound.

---

## 8. Do NOT spend more time on

- **More fine-tune variants.** Five honest negatives (ML at two capacities, single/multi-case RKL, capacity scale-up, correction head) at ~0.02 nats/site is a converged answer for this model class.
- **σ_min-coef below 0.03** (0.01 already lost in the sweep; below the training floor only the blend covers the score).
- **More Hutchinson probes at eval** (stability points already bound that contribution).
- **SMC restructuring** (no weight diversity exists to harvest at achievable n).
- **Multilevel/cluster updates or fancier HMC topology handling** (heatbath + OR + smooth-instanton Q-hops already saturate 2D U(1); verified exact P(Q) reproduction at will).
- **Solver/capacity changes for the ESS gap** (both capacity directions came back negative; only revisit if a step-count sweep shows discretization, not score, dominates the spread).

---

## 9. Verified solid — leave alone

- `lgt/lattice.py` — all index/sign conventions verified mutually consistent (W(1,1) ≡ plaquette, rectangles ≡ W(2,1)/W(1,2) to 1e-12); gauge transform, winding loops, correlator correct.
- `lgt/exact.py` — character-expansion machinery numerically careful (scaled Bessel `ive`, log-domain finite-V sums); verified against independent MC.
- `lgt/blocking.py` — telescoping identity tested; the exponential-family/min-KL argument for mean-plaquette matching is the right one-parameter choice; `matching_residuals` is an honest simulation-free error budget. Publication-grade.
- `lgt/hmc.py`, `lgt/local_updates.py` — Omelyan exactly reversible (4e-15 round-trip in float64), staples/heatbath/OR/instanton field/Q-hop all correct; `torch.distributions.VonMises` verified stable to κ = 2000 in float32.
- `model/wrapped.py` + DSM target — full winding-weighted kernel score, stable at both σ extremes.
- Curl-form gauge head (`model/score_net.py:88-93`) — exact invariance, orbit orthogonality, holonomy-zero-mode orthogonality all verified.
- Blend/guidance consistency between sampling and likelihood — line-for-line identical; the single most important consistency requirement for the ESS story, and it holds.
- `model/likelihood.py` core math and its own caveat list; `model/likelihood_train.py` objectives (deliberately searched for a sign/gradient bug that would explain the fine-tune failures: there isn't one).
- ChannelNorm rationale; guarded-checkpoint protocol in script 22 (rotating evals, never-trained monitor, mean-ESS save criterion) — port to SU(2) verbatim.
- Ladder charge-transport design — deliberate and self-aware; the gap is only that the default report doesn't surface the raw counterpart (§3.2).

---

## 10. Recommended order of work before SU(2) (~2–4 days)

1. **Matching-residual decomposition** (regression on stored log-weights + Villain control run) — ½ day; potentially reframes the exactness chapter.
2. **Validation rigor:** τ_int-aware errors, raw-ensemble report column, fix interleaved τ_int + "i.i.d. by construction" claim — ~1 day; strengthens every quantitative claim in the campaign outputs.
3. **Compute:** L=64 head-to-head (β = 55, 218.6), fresh-seed reruns of the 3σ Wilson cases, log-Z certificate line in script 24 — 1–2 days, mostly unattended.
4. **Bug sweep:** B1–B7 above — a few hours; makes artifacts reproducible for referees.
5. **Optional (new science):** AIS-corrected transport — only if the U(1) paper should contain a positive exactness result rather than a well-documented negative.