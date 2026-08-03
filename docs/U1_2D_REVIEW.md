# u1_2d Full Audit — 2026-08-02 (post-restructure)

Independent end-to-end review of the closed U(1) study: implementation
(`u1_2d/`), results of record (`out/u1_2d/`, especially `paper_appendix/`),
presentation, and repo structure. Method: five parallel review tracks
(lattice physics core; diffusion model; exactness/likelihood machinery;
appendix-vs-data numeric cross-check; validation/statistics + structure),
each deriving the math independently and tracing every hand-checkable
number to its source file, plus a full test-suite run.

**Verdict.** The science core is sound: every physics kernel, the diffusion
math, and the exactness machinery check out analytically and numerically;
the appendix's tables trace to machine-readable outputs almost line-for-line.
The defects found are (a) two implementation bugs in the exactness-program
scripts — one contaminating a stated premise of Table S6 (materially
negligible), one that would overwrite a result-of-record on rerun — (b) a
handful of number/convention slips in the appendix text, (c) a stale
`appendix.tex`, (d) silent-failure modes in the χ² validation gate, and
(e) an uncommitted, half-staged git restructure. Nothing found invalidates
the study's headline conclusions.

Test suite: **110 passed** (`pytest u1_2d/tests -q`, 63 s), two benign
warnings.

---

## 1. What was verified correct (the pros)

### Physics core (`u1_2d/lgt/`) — clean
- **Plaquette/action/force consistency.** `plaquette_angles` implements the
  documented convention exactly; the HMC force is autograd through the same
  action used in the accept step, so it is the exact link-wise gradient by
  construction (`wrap` has derivative 1 everywhere).
- **HMC.** Omelyan PQPQP (λ = 0.1931833) is symmetric/symplectic;
  end-of-trajectory `wrap` is a volume-preserving translation, harmless to
  detailed balance; Metropolis accept and full momentum refresh correct.
- **`exact.py`.** Wilson characters via scaled Bessel (`ive`) are stable at
  arbitrary β; the finite-volume torus character expansion, Villain
  characters, and the P(Q) constrained-sum representation (including the
  sign-handling of ψ(k) < 0 and the k-cutoff) were all re-derived and
  confirmed.
- **`blocking.py`.** The 2×2 link composition satisfies the telescoping
  identity (coarse plaquette = wrapped sum of the four fine plaquettes)
  exactly; Villain β/4 is exact; Wilson matching is the correct
  min-KL/maximum-likelihood projection.
- **`local_updates.py`.** Heatbath von Mises conditional, checkerboarding
  validity, microcanonical overrelaxation, and the instanton Q-hop
  (uniform-sign shift by the smooth Q = 1 field: symmetric,
  measure-preserving, `min(1, e^{−ΔS})` correct) all verified.

### Diffusion model (`u1_2d/model/`) — clean
- Wrapped-normal score confirmed against float64 autograd to ~4e-12 across
  σ ∈ [0.01, 6]; DSM target is the correct perturbation-kernel score with
  standard σ² weighting.
- Ancestral sampler is exactly Song's SMLD update; schedule discretization
  has no off-by-one; the high-β small-σ oversampling (`t^k` warp) does what
  the appendix claims.
- Symmetry ops derived independently and confirmed site-by-site: rotation
  gives an exact plaquette permutation (Q preserved), reflection negates
  plaquettes (Q flips); coarse conditioning is correctly *re-blocked* from
  the transformed fine field (right move, since D4 does not commute with
  even-anchored blocking).
- The curl output head is the exact adjoint of the plaquette map (checked
  against autograd to 2e-16), so the score lies in the gauge-covariant
  subspace; ChannelNorm is genuinely per-site with no L dependence.
- The EMA/validation mismatch from the pre-restructure audit is **fixed**
  (validation swaps in EMA weights with a forked deterministic RNG).
- The "continuous log-uniform β ∈ [1, 60]" training claim is accurate at the
  distribution level: `utils.expand_rungs` draws 60 + 12 + 6 log-uniform
  rungs at L = 16/32/8 (β constant within a rung, continuous across rungs).

### Exactness machinery — math clean
- ODE likelihood: change-of-variables sign conventions correct in both
  integration directions; Hutchinson probes are true Rademacher, fresh per
  eval, unbiased in log q (no cross-batch coupling in the network); uniform
  prior at σ_max = 6 valid to ~1e-8.
- Free-energy identity re-derived: E[w] = (2π)^{2L²} Z_f/Z_c and
  KL = ΔF − E[log w] match the code with correct signs.
- AIS: increments evaluated at pre-transition samples, kernels retargeted
  before transitions, fit-constant cancellation exact, step-size adaptation
  causal, even/odd split leak-free for the ESS numbers.
- Fine-tune machinery: discretize-then-optimize gradients valid; reverse-KL
  pathwise estimator is the exact gradient of the discrete objective; the
  guard protocol described in Fig 25b exists in code exactly as described
  (saves blocked at 4 of 6 opportunities, survivor = step 250).

### Validation/statistics — formulas clean
- Jackknife, binned SEM, Madras–Sokal τ_int with automatic windowing,
  KS with effective sample size, and the chain-major reshape in
  `chain_tau_int` (verified against the producer's memory layout) are all
  correct. The measured (not tree-level) β ladder matches the documented
  `[4.0, 14.1464, 55.0237]`; "16 sweeps, no Q-hops" is enforced in config
  and code; C-antithetic symmetrization is exactly measure-preserving.

### Results of record — traceable
- All 27 figures exist; every provenance directory named in the appendix
  exists; **Tables S1, S2, S5, S6, S7 confirmed to every quoted digit**
  against their JSONs; Fig 20's five p-value transitions, Fig 24's sweep,
  Fig 25's dynamics, Fig 27's numbers, the L = 64 head-to-head, and the
  rich-basis AIS blowup all confirmed. Figures visually match their
  captions (spot-checked 4, 10, 18, 19, 26, 27).
- Git: the restructure itself is coherent — `u1_2d/` and all 610
  `out/u1_2d/` files (both checkpoints included) are staged as renames;
  nothing is orphaned.

---

## 2. Defects and fixes (the cons)

No critical (result-invalidating) defects were found. Ranked below.

### 2.1 Major

**M1 — Villain control arm of the matching-residual study used the
Wilson-matched coarse β, not the exact β/4.**
[`27_matching_residual.py:62`](../u1_2d/scripts/27_matching_residual.py#L62)
calls `approx_matched_coarse_beta(fine_beta)` without `action_type`
(default `"wilson"`, [`blocking.py:88`](../u1_2d/lgt/blocking.py#L88)), so
the Villain arm ran at β_c = 4.0 instead of 14.1464/4 = 3.5366 (13% off;
2.8% at β = 55). The weights stay internally valid, but Table S6's premise
"for Villain the β/4 matching is *exact*, so its spread is pure model error
by construction" is false as run — the contamination lands exactly in the
R²_c column the decomposition isolates. **Magnitude estimate:** the
spurious term contributes ~0.6–1.5 nats of total spread against measured
Villain spreads of 15–24 nats, i.e. < 1% of the variance — the conclusion
(matching floor negligible) almost certainly survives.
*Fix:* pass `action_type` at line 62 (same fix in
[`19_ode_reweighting.py:81`](../u1_2d/scripts/19_ode_reweighting.py#L81)),
rerun the Villain arm (~cheap: 3 cases × 64 configs), and update Table S6;
at minimum add a caveat to the appendix that the Villain arm's matching was
Wilson-matched, with the error bound above.

**M2 — Rerunning script 28 with defaults overwrites the AIS
result-of-record with the failed variant.**
`bridge_features` at HEAD ([`ais.py:78-94`](../u1_2d/model/ais.py#L78-L94))
is the 11-feature "rich" basis the appendix records as the negative result;
script 28's default `--out` is `out/u1_2d/ais_transport`
([`28_ais_transport.py:357`](../u1_2d/scripts/28_ais_transport.py#L357)) —
the directory holding the final 7-feature numbers (Table S7). There is no
flag to select the 7-feature basis, so HEAD cannot reproduce the quoted
result and a naive rerun destroys it.
*Fix:* add a `--basis {final7,rich11}` flag with `final7` as default (keep
both feature lists in `ais.py`), and/or change the default `--out` to a
scratch path so the record dir must be named explicitly.

**M3 — The P(Q) χ² gate can silently vanish exactly when the sector
distribution is maximally wrong.**
[`report.py:263-285`](../u1_2d/validate/report.py#L263-L285): the χ² row is
appended only when ≥ 2 bins have expected > 2 counts *and* the observed
counts land in them; an ensemble with all charges outside the expected bins
produces no row at all, which the verdict table renders as "-"
(indistinguishable from "not applicable"). Relatedly, bins with
expected ≤ 2 are dropped *with their observed counts discarded*, so the
test is blind to tail mass.
*Fix:* pool low-expectation bins (and any out-of-range charges) into
overflow bins instead of discarding them; when the test is still not
computable, emit an explicit `FAIL (no overlap with exact support)` row
rather than nothing.

**M4 — The generalization-study path is not τ_int-aware, contrary to the
stated conventions.**
[`06_generalization_study.py:307-312`](../u1_2d/scripts/06_generalization_study.py#L307-L312)
calls `validate_ensemble` without `n_chains`/`ref_n_chains`, so the 38-case
study (the source of the appendix case tables) used fixed 20-bin binned
errors, not the per-chain τ_int machinery that `04_validate.py` uses and
that the appendix's honesty conventions describe. Reference-side errors at
high β (τ_int beyond bin length) are understated, inflating some |z|.
*Fix:* thread the chain counts through the study path and regenerate
`summary.json`/verdict tables, or scope the appendix's error-bar claim to
the ladder-validation path.

**M5 — `appendix.tex` is one full revision behind `appendix.md`.**
The .tex (the paste-into-paper artifact) covers only Figs 1–22 and Tables
S1–S4: missing Figs 23–27, Tables S5–S7, the ESS-gap program paragraph, and
the entire exactness-endgame section. It also retains the *wrong* Fig 10
caption wording ("consistent with the all-zero charge content") that
`docs/V2_AUDIT.md` item 8 flagged and that was fixed in the .md only.
Where the two overlap, all numbers agree.
*Fix:* regenerate the .tex from the .md (or declare the .md canonical and
delete the .tex); carry over the Fig 10 caption fix.

**M6 — The restructure is uncommitted and half-staged.**
Four files are modified but unstaged: `CLAUDE.md`, `README.md`,
`docs/V2_AUDIT.md`, `pyproject.toml`. Committing right now would record
the *old* versions — including a `pyproject.toml` whose
`include = ["diffusion*", "diffusion_v2*"]` matches nothing (broken
`pip install -e .`) and a README describing the deleted layout. The entire
restructure (including the 610 staged `out/u1_2d/` files) exists only in
the index — one `git reset --hard` from losing the rename bookkeeping.
*Fix:* `git add` the four files (after updating `pyproject.toml` to
`include = ["u1_2d*", "su2_2d*"]`), commit, and decide whether `su2_2d/`
(currently fully untracked) should be added in the same commit.

### 2.2 Appendix text vs data (number/convention slips)

All in `out/u1_2d/paper_appendix/appendix.md` unless noted. Each is a small
edit; none require reruns.

| # | Claim in appendix | What the data says | Fix |
|---|---|---|---|
| A1 | Table S4 / Fig 21: B_bt6 χ² p after = **0.43** | Data: **0.386** (`pq_hmc_tail/summary.json`); 0.43 appears cross-contaminated from the exact-sector B_bt6 value 0.425 quoted in Fig 20 | Change to 0.39 in both places |
| A2 | "mean \|plaquette z\| **1.77 vs 1.74**" (sector modes) | Confirmed numerically, but these are z **vs the HMC reference**, while the Honesty Conventions say z-scores are vs exact; vs-exact means are **1.06 / 1.08** | Either quote 1.06/1.08 or label the 1.77/1.74 as vs-reference |
| A3 | Figs 12/26: "seeds thermalize in 0–13 trajectories in **24 of 29** cases" | `thermalization/report.md`: **26**/29 have t_therm ≤ 13 (23/29 under the below-2τ_int criterion); no reading gives 24 | State 26/29 (≤ 13) or 23/29 (below interval), with the criterion |
| A4 | "mean raw spurious ⟨Q²⟩ excess **5.3 → 2.9**" | 2.9 reproduces only as the mean **excluding part C** (the volume track, worst excess 28.15); all-38 mean is 4.01. The v6-side 5.3 is not reproducible from any surviving file (closest: ~4.95–5.05 excluding C) | State the exclusion explicitly ("excluding the volume-scaling track") and either recover the v6 number's provenance from git history or soften to "≈5" |
| A5 | Fig 17: "its Q-hop keeps tunneling to **β = 256** where standard HMC froze at 16" | No `instanton_vs_standard` output survives anywhere (working tree or git history); only script 13 remains | Rerun script 13 (cheap) to regenerate the evidence, or cite it as prior-run/unarchived |
| A6 | "volumes to L = 128 (**64×** the training area)" | 128²/32² = **16×**; 64× is only true vs L = 16, but training included L = 32 | Change to 16× (or "64× the smallest training volume") |
| A7 | Table S3: "cases with \|z(⟨Q²⟩)\| > 2: **13 vs 3**" | Inconsistent counting: transport 13 includes 2 "+inf" rows, exact-sector 3 excludes its own 2 "+inf" rows; consistent counting gives 13 vs 5 or 11 vs 3 | Pick one convention and footnote the inf rows |
| A8 | Table S5 prose: ESS/N "at the 1/64 floor in every row except the knob-only point" | Baseline 16:14.1 = 0.0230 and big-net 16:14.1 = 0.0207 (1.3–1.5× the floor) | Soften to "at or near" |
| A9 | Fresh-seed section: "B: −2.56 then +0.13" | Quotes B_bt20's W(2×2) while the original flag was the plaquette (−3.19; fresh plaq −1.49 / −0.04 — conclusion unchanged) | Quote the matching observable |
| A10 | Fresh-seed section | s3's A_bc8 rerun shows a new Q z = +4.18 with P(Q) χ² p = 0.003, unmentioned | Add one sentence (it is consistent with the known raw-topology weakness; exact-sector mode covers it) |
| A11 | Intro: "addresses **four** questions: (1)…(5)" | Five are enumerated (the .tex has the original four) | "five" |
| A12 | L64 head-to-head: diffusion "\|z\| ≤ 1.8" | Data: max 1.834 | "≤ 1.9" or "< 2" |

### 2.3 Minor (code)

- **`train.py:239-244`** — validation noise draws t ~ U[0,1], ignoring the
  `high_beta_sigma_bias` warp used in training; best-epoch selection
  underweights exactly the small-σ/high-β regime the bias targets. *Fix:*
  apply the same warp in validation draws.
- **`score_net.py:171` / `train.py:57`** — `norm_type` defaults to
  `"group"` (lattice-size-dependent); the no-L-dependence claim holds only
  because the shipped configs override to `"channel"`. *Fix:* flip the
  default to `"channel"`.
- **`sampler.py:38-52`** — the Langevin corrector runs *after* the final
  denoise step, re-injecting O(σ_min) noise; output is ~p_{σ_min}, not the
  denoised mean. Harmless under the MH/retherm wrapper; note it or reorder.
- **`ais.py:180-182` + script 27** — Table S6/S7's R² columns are
  in-sample, refit-on-all-data after CV selection (expected optimism
  ~p/n ≈ 9–17% at n = 64), inflating the "coarse-explainable" share. *Fix:*
  quote the CV R² alongside.
- **`28_ais_transport.py:154-207`** — the even/odd honesty split covers
  only ESS/std; observables, certificate, and sector-resolved estimates use
  the full sample including the fit half.
- **`report.py:269-282`** — deflating χ² by 1/(2τ_int) while keeping
  dof = k−1 matches the first moment only; the quoted p is approximate
  (acknowledged in a comment, but it feeds the verdict tables).
- **`report.py:221-227`** — `ref_frozen` counts tunnelings summed over all
  chains (< 3 total) while the report legend says "the reference chain
  never tunnels"; a per-chain criterion would match the stated semantics.
- **`12_campaign_verdict.py:62,123-128`** — NaN metrics and missing rows
  both render "-" (indistinguishable); inf is footnoted only in the Q²
  column; no hard |z| gate exists anywhere in code (the ±2 band is figure
  shading + prose only).
- **`likelihood.py:342-385`** — actions evaluated in float32 at β·V up to
  ~2×10⁵ (~0.03-nat rounding) before the certificate's float64 cast;
  harmless at current spreads, bites at nat-level gaps.
- **`local_updates.py:121-137`** — `topological_update` on unbatched
  `[2, L, L]` input silently mis-broadcasts to `[2, 2, L, L]` garbage
  instead of raising. *Fix:* assert 4-dim input.
- **Creutz rows** (`observables.py:69-74`) carry i.i.d. jackknife errors
  with no τ_int inflation — optimistic z on autocorrelated chains.
- **Schedule/sampler latent mismatch** — `discrete_sigmas` with tensor β
  returns [n_steps, B], which `sample_ancestral` cannot consume (no current
  caller hits it).
- **`exact.py` cutoffs** (`q_max`, `k_cut`) are sufficient for the
  project's entire (β, L) range but silently lose tail mass far outside it
  (e.g. β ≳ 16·V); `wilson_loop_exact(area=0)` NaNs; `match_coarse_beta`
  brentq bracket (1e-3, 256) raises ungracefully outside its range;
  `thin=0` returns duplicate states.
- **Blend caveat** — `ladder.py:145`'s β_eff = β/(1+4βσ²) is the λ = 4 mode
  of the exact harmonic score β·λ_k/(1+βσ²λ_k); the docstring's "exact at
  any β" overstates (exact only as σ → 0). Ladder σ floor (coef 0.1) also
  dips below the trained floor (0.3) — intentional per the blend design,
  but the model gets 10–50% weight slightly out of its trained σ range at
  β ≈ 9–25.
- **Seed-stream collision** — scripts pass the same seed to the ODE
  sampler's fresh `torch.Generator` and to the global RNG seeding the
  coarse HMC, so chunk-0 prior draws literally equal hot-start init draws
  (washed out by burn-in; matters only at β_c < 5).

### 2.4 Minor (docs/structure)

- **`u1_2d/README.md:162-190`** — the package README's layout block and
  every pipeline command still reference the deleted `diffusion/` package;
  following it fails. *Fix:* search-replace to `u1_2d/`.
- **Stale invocation examples** in script docstrings
  (`06`, `09`, `10`, `12`, `13`) still say `python diffusion/scripts/...`.
- **`run_campaign.py:136-144`** references deleted `out/diffusion/demo_v6`
  paths; script 13 writes to nonexistent `out/u1_2d/demo_v6/`.
- `ess_chain/*.log` and `checkpoints/*.history.json` contain old
  `out\diffusion_v2\v2\` paths — historical logs, cosmetic only.
- `artifacts/diffusion/...` naming in default/demo/smoke configs —
  internally consistent, gitignored scratch, cosmetic.
- Fig 26a: the red "plain-HMC topology frozen" annotation collides with
  legend text; Fig 27a: the green "certificate band" label is partially
  hidden behind the "big net" bar.
- `test_audit_additions.py` triggers a `log(0) → -inf` RuntimeWarning at
  `exact.py:54` for far-tail sectors — mathematically correct limit;
  silence with `errstate` if desired.
- rkl2 "≈ 80 min" training cost is plausible but not directly verifiable
  from the logs (~25 min of optimizer steps + eval overhead).

---

## 3. Prioritized action list

1. **Protect the record:** fix M2 (script 28 basis flag / default out) —
   one edit, prevents destroying Table S7's provenance. Then commit the
   restructure properly (M6: stage the four files, fix `pyproject.toml`).
2. **One-line science fix + cheap rerun:** M1 (pass `action_type` in
   scripts 27/19), rerun the Villain arm, refresh Table S6.
3. **Appendix edits (no reruns):** A1–A12 plus the intro count; regenerate
   or retire `appendix.tex` (M5).
4. **Validation hardening (matters for SU(2) reuse):** M3 (χ² overflow
   bins + explicit not-computable row), M4 (τ_int-aware study path),
   `norm_type` default, validation σ-bias match.
5. **Docs sweep:** `u1_2d/README.md` commands, script docstrings,
   `run_campaign.py` paths.
6. Optional evidence recovery: rerun script 13 to re-materialize the
   Fig 17 "β = 256 vs 16" claim.

Since `u1_2d` is frozen (bug-parity fixes only), items 1–3 are within the
freeze's letter (record safety, a bug fix, and text corrections); item 4 is
best applied to the shared machinery as it is carried into `su2_2d`.
