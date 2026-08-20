# u1_2d Full Audit — 2026-08-03

Independent end-to-end review of the closed U(1) study: the **conceptual
framework**, the **statistical inference**, the **physics consistency**, the
implementation (`u1_2d/`), and the results of record (`out/u1_2d/`,
especially `paper_appendix/`).

Method: five parallel implementation/reporting review tracks (lattice
physics core; diffusion model; exactness/likelihood machinery;
appendix-vs-data numeric cross-check; validation + structure), each deriving
the math independently and tracing every hand-checkable number to its source
file; plus a direct conceptual and statistical audit performed against
`docs/NARRATIVE.md`, `ladder.py`, the campaign log, and a fresh recomputation
of the z-score distribution from `generalization/summary.json`.
Test suite: **111 passed** (`pytest u1_2d/tests -q`), after the fixes in
Part G.

> **Coverage note.** The two sub-questions initially deferred are now
> complete: the coarse-parent correlation is measured (**S4** — it is *not*
> the explanation for the over-dispersion, which sharpens S2/S3), and the
> prior-work positioning was carried out and written into `NARRATIVE.md`
> Part V (summarized in **Part G**). The literature result is the most
> consequential finding in this audit and is not favourable: the headline
> concept is substantially published.

## Verdict

The **physics and the mathematics are sound** — every kernel, the diffusion
construction, and the exactness machinery check out analytically and
numerically, and the appendix's tables trace to their JSONs almost
line-for-line. The **conceptual framework is coherent and, in `NARRATIVE.md`
§20, unusually honest** about what was and was not achieved.

The substantive criticisms are not of the science but of **how sharply the
claims are stated relative to what was measured**:

1. A **coherent negative bias** in every Wilson observable (mean z ≈ −0.42,
   −2.1σ) sits underneath the phrase "matches exact results" and is never
   reported.
2. The **z-distribution is over-dispersed** (std 1.26 vs 1.0) and the
   dispersion **grows with loop size** (1.09 at 4×4 → 1.44 at 12×12,
   max |z| = 5.91) — a long-wavelength signature that the appendix's chosen
   observable subset does not surface.
3. The **head-to-head omits the diffusion arm's own 8820 s entry cost**.
4. Two implementation bugs in the exactness scripts, one of which
   contaminates a stated premise of Table S6 (materially small), the other of
   which would destroy a result-of-record on rerun.

Nothing found invalidates the study's headline conclusion — that this is the
only one of the three samplers that remains available and correct in the
frozen regime. Several findings *strengthen* the work (§A1: the ladder has an
exact invariant the project never claimed).

**The exception, added after the literature review (Part G):** the threat to
this work is not internal but external. The study was carried out with two
citations and no related-work search, and the headline concept — diffusion +
2D U(1) + β-extrapolation + size generality + MCMC-based exactness — is
substantially published (Zhu et al., JHEP 03 (2026) 111), as is inverse-RG
configuration generation (Bachtis et al., PRL 128, 081603 (2022)) and the
classical coarse→prolongate→rethermalize architecture (Endres et al., PRD 92,
114516 (2015)). The physics here is closed; the *positioning* has not been
started, and it is what determines whether any of this is publishable. The
most defensible contribution is the one the documents treat as secondary: the
exactness-falsification program, which the inverse-RG literature explicitly
lists as open work.

---

# Part A — Conceptual framework

### A1. The ladder has an exact invariant the project never states (a *pro*)

The narrative justifies sector transport with "blocking preserves Q"
(§7) — a statement about the **map**, not about the **measure**. The stronger
fact, which I verified numerically with the project's own `exact.py`:

For Villain with β_f = 4β_c and L_f = 2L_c, the exact finite-volume ⟨Q²⟩ is

| rung | L=8, β=1.3472 | L=16, β=5.389 | L=32, β=21.56 | L=64, β=86.22 |
|---|---|---|---|---|
| ⟨Q²⟩ | 1.20271 | 1.20334 | 1.20334 | 1.20334 |

**⟨Q²⟩ is a fixed point of the matched ladder** (invariant to 5 decimals),
because ⟨Q²⟩ ≈ V/(4π²β) and the ladder multiplies V by 4 and β by 4
simultaneously. The campaign's measured-matching ladder inherits this:
1.986 → 1.934 → 1.904 → 1.903 (4% total drift, concentrated in the first,
strongest-coupling step).

Two consequences worth writing down:
- Sector transport is not an approximation that happens to work — the coarse
  ensemble's P(Q) **is** the fine theory's P(Q), by an exact scaling identity.
- The ladder is therefore a **continuum-limit trajectory at fixed physical
  volume**, not a thermodynamic-limit one. The endpoint (L=64, β=55) answers
  "the same physical system resolved 8× finer," which is the correct physical
  reading of the result and is currently nowhere stated. `grep` for "fixed
  physical volume" / "constant physics" / "continuum limit" in NARRATIVE.md
  returns nothing relevant.

*Fix:* add this identity to §7/§8. It converts the project's central design
intuition into a checkable theorem and is one of the strongest arguments the
work has.

### A2. Exactness: the deployed pipeline is a validated heuristic — and the docs mostly say so

I checked `ladder.py` directly: **there is no accept/reject on the whole
proposal anywhere.** The only Metropolis steps are *inside*
`retherm_sweeps` (local single-link updates) and the instanton Q-hop. Sixteen
local sweeps reduce bias; they do not make a biased proposal exact, and local
updates are precisely the algorithm that relaxes long-wavelength modes
slowest. The exactness knob and the speedup knob are the same knob: taking
retherm → ∞ recovers exactness at exactly the cost the method exists to avoid.

**`NARRATIVE.md` §20 handles this correctly** and deserves credit — it
separates "as a sampler graded on observables" (validated) from "as an exact
sampler certified by importance weights" (quantified as out of reach), and
states the Markov-chain route as a **design directive** for the successor:

> "Exactness **must** come from Markov-chain machinery wrapped around the
> generative proposal — Metropolis tails, seeded chains — not from the
> proposal's own likelihood."

That is a prescription, correctly tensed. **`CLAUDE.md` compresses it into
"correctness *comes from* Markov-chain machinery (retherm, M-H tails) wrapped
around the proposal"** — converting a forward-looking directive into a claim
about the shipped U(1) pipeline. *Fix: restore the modal verb in CLAUDE.md.*

The genuinely clean claim is the **seeding** mode: a chain seeded from a
diffusion config and run with exact HMC is asymptotically exact *within its
sector*, with the sector supplied by transport (justified by A1). The
appendix states this decomposition honestly ("nothing in the seeded
continuation depends on Q mixing afterward, since the sector is transported,
not evolved"). That is the conceptually solid core of the work.

### A3. The KL-vs-observables tension is real, sharp, and under-discussed

The measured density gap is ~1 nat/**site**. Per configuration that is

- 16:55 → 0.875 × 2·16² = **448 nats**
- 32:218.6 → 1.0245 × 2·32² = **2098 nats**

A KL of 448 nats means the generated ensemble is, information-theoretically,
overwhelmingly distinguishable from the target — yet every measured
observable agrees. §5 below shows the plaquette is measured to a relative
precision of 0.017%, so this is **not** a case of a weak test: the validation
is *sharp* on what it measures, and what it measures simply does not
constrain the density.

The honest statement is therefore stronger and more interesting than the one
in the appendix: *the pipeline reproduces the measured gauge-invariant
observables to ~10⁻⁴ relative precision while provably not sampling the
target measure.* For observable-driven physics that may be entirely
sufficient — but "matches exact results" reads as a distributional claim and
should be scoped. §20 gets this right; the appendix's headline paragraph does
not inherit the scoping.

### A4. Single-coupling projection: the gap is real and Table S6 was the right idea

The true blocked measure of a Wilson theory is not a single-coupling Wilson
theory (it induces rectangle and higher-character couplings). The pipeline
conditions on a coarse config drawn from a single-coupling ensemble. Table S6
is the correct instrument to bound this — but see **M1**: the Villain control
that was supposed to isolate it was run at the *Wilson*-matched β_c, so the
"exact matching by construction" premise did not hold as run.

### A5. Error accumulation across rungs is asserted from three rungs

"Drift does not accumulate across rungs" (Fig 1) rests on a 3-step ladder
(8→16→32→64). There is no theoretical argument for non-accumulation, only the
empirical retherm-pins-the-UV mechanism. Three rungs is thin evidence for an
asymptotic claim, and A1 shows *why* it works for topology but says nothing
about the UV. Recommend scoping to "does not accumulate detectably over the
three rungs tested," or running a 5–6 rung ladder at lower base β.

---

# Part B — Statistical significance

All numbers below are recomputed directly from
`out/u1_2d/generalization/summary.json` (38 cases, `z_exact` field).

### S1. A coherent negative bias runs through every Wilson observable

| observable | mean z | SEM | significance |
|---|---|---|---|
| plaquette | −0.423 | 0.204 | −2.1σ |
| wilson_2x2 | −0.466 | 0.197 | −2.4σ |
| wilson_4x4 | −0.436 | 0.177 | −2.5σ |
| wilson_8x8 | −0.344 | 0.213 | −1.6σ |
| wilson_12x12 | −0.225 | 0.233 | −1.0σ |

**All 20 Wilson-type observables have mean z < 0.** The generated ensembles
are systematically slightly *less ordered* than exact. The observables are
strongly correlated within a case, so this is closer to one measurement than
twenty — but the sign coherence plus −2.1σ on the plaquette alone indicates a
real systematic offset, not noise. It is never reported; "matches exact
results" absorbs it. *Fix: report the mean-z offset explicitly; it is small
and honest, and it is a physics observation (the model slightly under-orders)
rather than an embarrassment.*

### S2. The z-distribution is over-dispersed

Under a correct model with correct error bars, z ~ N(0,1) and std(z) = 1.

| observable | n | std(z) | 95% CI | |
|---|---|---|---|---|
| plaquette | 38 | 1.255 | [1.04, 1.70] | over-dispersed |
| wilson_2x2 | 38 | 1.216 | [1.01, 1.65] | over-dispersed |
| wilson_4x4 | 38 | 1.093 | [0.91, 1.48] | — |
| wilson_8x8 | 38 | 1.316 | [1.09, 1.78] | over-dispersed |
| wilson_12x12 | 38 | 1.438 | [1.19, 1.95] | over-dispersed |
| Q | 38 | 0.748 | [0.62, 1.01] | (under) |
| Q² | 36 | 2.785 | [2.30, 3.82] | over-dispersed |

Either the error bars are underestimated or there is case-to-case model bias.
**S4 below eliminates the error-bar explanations**, leaving genuine model
bias. (M4's missing τ_int-awareness is a real defect but affects `z_ref`, not
the `z_exact` dispersion measured here.)

### S3. The dispersion grows with loop size — a long-wavelength signature

| loop | 2×2 | 4×4 | 6×6 | 8×8 | 10×10 | 12×12 |
|---|---|---|---|---|---|---|
| std(z) | 1.216 | 1.093 | 1.226 | 1.316 | 1.339 | 1.438 |
| max abs z | 3.47 | 3.12 | 3.90 | 5.03 | 5.61 | 5.91 |

This is the most diagnostically valuable number in the audit. The model's
error is **concentrated in extended observables** — exactly what A2 predicts
if 16 local retherm sweeps fail to relax long-wavelength modes, and exactly
where a large KL would hide (A3). The appendix reports plaquette, W(2×2), and
W(4×4) — the three *least* affected — and never shows the trend.

Consequently the appendix's multiplicity accounting is scoped to the
favourable subset:

- narrow set {plaquette, W2×2, W4×4}: **4** beyond 3σ of 114 tests (expect 0.31)
- **all Wilson observables: 29 beyond 3σ of 760 tests (expect 2.05)** — a 14× excess
- largest Wilson |z| anywhere: **5.91** (wilson_12x12)

(The 760 tests are highly correlated across loop sizes within a case, so this
is not 29 independent failures — it is a handful of cases failing *coherently
across all loop sizes*, which is a stronger indictment than scattered noise.)

*Fix:* publish the std(z)-vs-loop-area trend as a figure. It is an honest
negative that materially improves the paper: it localizes the residual model
error in exactly the modes the theory predicts, and it is the natural bridge
to the SU(2) design.

### S4. Independence of generated configs — MEASURED, and it is *not* the explanation

Generated-ensemble errors are per-config SEM, treating configs as i.i.d., but
each fine config inherits a coarse parent from an autocorrelated HMC chain.
Measured directly (fresh HMC at the study's own settings, n_chains=16,
thin=5), the coarse base is essentially decorrelated:

| observable | τ_int (L16, β=4) | max inflation √(2τ) | τ_int (L16, β=14.15) | max inflation |
|---|---|---|---|---|
| plaquette | 0.59 | 1.09× | 0.59 | 1.08× |
| W(2×2) | 0.56 | 1.06× | 0.53 | 1.03× |
| W(4×4) | 0.52 | 1.02× | 0.51 | 1.01× |
| W(8×8) | 0.62 | 1.12× | 0.57 | 1.06× |
| Q² | 0.50 | 1.00× | 0.58 | 1.07× |

(0.5 is the uncorrelated floor; these are *upper* bounds, assuming the fine
observable is fully determined by its parent.) **Thinning at 5 is adequate**,
inflation is ≤ 1.12×, and it does not grow with loop size — so it explains
neither the 1.26–1.44 dispersion nor the loop-size trend.

**This sharpens S2/S3 rather than excusing them.** `z_exact` is
`(value − exact)/error` using *only* the generated-ensemble error (verified
against the JSONs; the exact value is noiseless), so M4's τ_int issue affects
`z_ref` but **cannot** affect the dispersion measured here. With the two
candidate error-bar explanations eliminated, the over-dispersion and its
growth with loop area are **genuine case-to-case model bias**. That is a
stronger and cleaner conclusion than the original framing, which wrongly
offered M4 as the mechanism.

### S5. Post-hoc reruns of only the failing cases

The four 3σ flags were rerun with fresh seeds and declared fluctuations
because they "flip sign or vanish." Rerunning only the *failures* and
accepting the new result is a biased procedure — regression to the mean
guarantees improvement. The unbiased version reruns a matched sample of
*passing* cases too and compares the distributions. The conclusion is likely
correct (the flips are large and the physics is unchanged), but the procedure
as described cannot establish it.

### S6. Power — the validation is sharp where it looks (a *pro*)

- n_configs per case: 64 / 96 / 128
- relative SEM on ⟨cos θ_p⟩: median **0.0087%** (range 0.0004–0.257%)
- smallest relative bias detectable at |z| > 2: **~0.017%**

"Matches exact" therefore means "no bias above ~2 parts in 10⁴ detected on
the plaquette" — a genuinely strong statement, and the correct framing is as
an *upper bound on bias*, which the appendix never uses.

### S7. ESS comparisons at the floor

ESS/N = 1/N is the degenerate minimum. Differences like 0.021 vs 0.016 at
n = 48–64 are within the sampling error of an ESS estimate at that size and
should not be read as ordering. Table S7's held-out ESS column is best
reported as "at floor" throughout rather than to three digits. (Table S5's
*spread* comparisons are meaningful; the ESS column is not.)

---

# Part C — Physics consistency

Verified correct:
- **Ladder coupling ratios** approach tree level from below as β grows —
  2.969 (8→16), 3.537 (16→32), 3.890 (32→64) vs tree-level 4.0 — exactly the
  expected behaviour of a minimum-KL matching that becomes exact at weak
  coupling. Consistent with `blocking.py`'s measured matching.
- **Mean plaquette** rises monotonically along the ladder
  (0.556 → 0.864 → 0.964 → 0.991), consistent with β increasing.
- **Villain ⟨Q²⟩ = V/(4π²β)** reproduced to 5–6 digits by the exact
  finite-volume P(Q) at every rung — an independent check that `exact.py`'s
  character expansion and its P(Q) integral agree.
- **⟨Q²⟩ ladder invariance** (A1).
- 2D U(1) has no phase transition; RG flow toward β → 0 is correctly
  described and correctly exploited (sample where tunneling is free).

Concern:
- **Cost accounting (see M7)** — the physics comparison is fair in
  *correctness*, not in *total cost*, and the appendix's closing verdict
  (availability + correctness in the frozen regime) is the claim that
  survives; Fig 18's framing is not.

---

# Part D — Implementation correctness (verified clean)

**Physics core (`u1_2d/lgt/`).** Plaquette convention exact; HMC force is
autograd through the same action used in the accept step, so it is the exact
gradient by construction; Omelyan PQPQP symmetric/symplectic; end-of-trajectory
`wrap` is measure-preserving; character expansions stable via scaled Bessel;
2×2 blocking telescoping identity verified by expansion; heatbath von Mises
conditional, checkerboarding, microcanonical overrelaxation, and the
instanton Q-hop (symmetric, measure-preserving) all correct.

**Diffusion model (`u1_2d/model/`).** Wrapped-normal score confirmed against
float64 autograd to ~4e-12 across σ ∈ [0.01, 6]; DSM target is the correct
perturbation-kernel score; ancestral sampler is exactly Song's SMLD update;
D4×C symmetry maps derived independently and confirmed site-by-site
(rotation permutes plaquettes, reflection negates them), with coarse
conditioning correctly *re-blocked* from the transformed fine field; the curl
head is the exact adjoint of the plaquette map (2e-16); ChannelNorm is
genuinely per-site; the EMA/validation mismatch from the prior audit is
**fixed**. The "continuous log-uniform β ∈ [1, 60]" claim is accurate at the
distribution level via `utils.expand_rungs` (60+12+6 log-uniform rungs).

**Exactness machinery.** ODE change-of-variables signs correct in both
directions; Hutchinson probes true Rademacher and unbiased in log q; uniform
prior at σ_max = 6 valid to ~1e-8; free-energy identity
KL = ΔF − E[log w] re-derived and matching; AIS increments evaluated at
pre-transition samples with kernels retargeted before transitions and exact
fit-constant cancellation; reverse-KL pathwise estimator is the exact
gradient of the discrete objective; the Fig-25b guard protocol exists in code
exactly as described.

**Validation statistics.** Jackknife, binned SEM, Madras–Sokal τ_int with
automatic windowing, KS with effective sample size, and the chain-major
reshape in `chain_tau_int` are all correct. C-antithetic symmetrization is
exactly measure-preserving.

---

# Part E — Defects and fixes

## Major

**M1 — Villain control used the Wilson-matched coarse β.**
[`27_matching_residual.py:62`](../u1_2d/scripts/27_matching_residual.py#L62)
calls `approx_matched_coarse_beta(fine_beta)` without `action_type` (default
`"wilson"`), so the Villain arm ran at β_c = 4.0 instead of 14.1464/4 =
3.5366 (13% off; 2.8% at β = 55). Table S6's premise — "for Villain the β/4
matching is *exact*, so its spread is pure model error" — is false as run,
and the contamination lands in the R²_c column the decomposition isolates.
**Magnitude:** ~0.6–1.5 nats of spurious spread against measured spreads of
15–24 nats (< 1% of variance), so the conclusion (matching floor negligible)
almost certainly survives.
*Fix:* pass `action_type` (same at
[`19_ode_reweighting.py:81`](../u1_2d/scripts/19_ode_reweighting.py#L81)),
rerun the Villain arm (3 cases × 64 configs — cheap), update Table S6.

**M2 — Rerunning script 28 with defaults destroys the AIS result-of-record.**
`bridge_features` at HEAD ([`ais.py:78-94`](../u1_2d/model/ais.py#L78-L94))
is the **11-feature "rich" basis the appendix records as the failed variant**,
while script 28's default `--out` is `out/u1_2d/ais_transport`
([28:357](../u1_2d/scripts/28_ais_transport.py#L357)) — the directory holding
the final 7-feature Table S7 numbers. HEAD cannot reproduce the quoted result
and a naive rerun overwrites it.
*Fix:* add `--basis {final7,rich11}` defaulting to `final7`; point the default
`--out` at a scratch path.

**M3 — The P(Q) χ² gate vanishes silently exactly when P(Q) is most wrong.**
[`report.py:263-285`](../u1_2d/validate/report.py#L263-L285): the χ² row is
emitted only if ≥2 bins have expected > 2 *and* observed counts land in them.
An ensemble with all charge outside the expected support produces **no row**,
rendered as "-" — indistinguishable from "not applicable." Low-expectation
bins are dropped *with their observed counts discarded*, so the test is blind
to tail mass.
*Fix:* pool low-expectation bins and out-of-range charges into overflow bins;
emit an explicit `FAIL (no overlap with exact support)` when uncomputable.

**M4 — The generalization study is not τ_int-aware, contrary to stated conventions.**
[`06_generalization_study.py:307-312`](../u1_2d/scripts/06_generalization_study.py#L307-L312)
calls `validate_ensemble` without `n_chains`/`ref_n_chains`, so the 38-case
study — the source of the appendix case tables — used fixed 20-bin errors,
not the per-chain τ_int machinery the honesty conventions describe. This is a
concrete mechanism for the S2 over-dispersion.
*Fix:* thread chain counts through and regenerate, or scope the error-bar
claim to the ladder-validation path.

**M5 — `appendix.tex` is a full revision behind `appendix.md`.**
The .tex covers only Figs 1–22 / Tables S1–S4: missing Figs 23–27, Tables
S5–S7, the ESS-gap paragraph, and the entire exactness-endgame section. It
also retains the **wrong Fig 10 caption** that `V2_AUDIT.md` item 8 flagged
and that was fixed in the .md only. Where they overlap, all numbers agree.
*Fix:* regenerate from the .md, or delete the .tex and declare the .md canonical.

**M6 — RETRACTED (2026-08-03): the restructure was already committed.**
This finding came from the git status snapshot taken at the *start* of the
audit session, which does not update as a conversation proceeds. Verified
against live git: HEAD (`cd4a30b`) contains `u1_2d/`, `diffusion_v2` is absent
from HEAD, the index is clean, and `pyproject.toml` already reads
`include = ["u1_2d*", "su2_2d*"]`. Root `README.md` has zero stale references.
Commits `f7cac2f` (restructure), `ca70083` and `cd4a30b` (SU(2)) landed after
the snapshot was taken.

What *was* genuinely stale, and is now fixed: `u1_2d/README.md` (layout block
and every pipeline command pointed at the deleted `diffusion/` package, plus
no note that the study is closed or that reruns must not overwrite
`out/u1_2d/`) and the invocation examples in five script docstrings
(06, 09, 10, 12, 13).

*Lesson for future audits of this repo:* the session-start git status is a
snapshot, not live state. Re-verify with `git log` / `git cat-file` before
reporting any version-control finding.

**M7 — The head-to-head omits the diffusion arm's entry cost.**
From [`run.log`](../out/u1_2d/run.log): `STAGE_DATA` 21.7 min +
`STAGE_TRAIN` 125.3 min = **147 min ≈ 8820 s** one-time. Fig 18 plots the
competitor's *entry* cost (≤ 2534 s) against diffusion's *marginal* cost
(~2.4 s/config) and concludes "the diffusion pipeline has no burn-in." An
honest diffusion entry marker sits at 8820 s — **above every instanton-HMC
point that converges**. At β = 55 for a single ensemble, instanton HMC is
cheaper outright.
The amortization defense is legitimate — one checkpoint served 38 cases
across β = 1.5–872 and L ≤ 128, amortizing to ≈ 1.8 s/config extra (total
≈ 4.2 s/config, still flat in β) — and the closing verdict ("the only sampler
that remains both available and correct in the frozen regime") is the claim
that survives.
*Fix:* add the one-time cost as a marker/annotation on Fig 18, quote the
amortized per-config number, and state the break-even explicitly.

## Appendix text vs data (small edits, no reruns)

| # | Claim | Data says | Fix |
|---|---|---|---|
| A1 | Table S4 / Fig 21: B_bt6 χ² p after = **0.43** | **0.386**; 0.43 appears copied from the exact-sector value 0.425 in Fig 20 | → 0.39 |
| A2 | "mean \|plaquette z\| **1.77 vs 1.74**" | These are z **vs HMC reference**; the stated convention is vs exact, which gives **1.06 / 1.08** | relabel or requote |
| A3 | "thermalize in 0–13 traj in **24 of 29** cases" | **26**/29 (≤13) or 23/29 (below-interval); never 24 | state criterion + correct count |
| A4 | "raw ⟨Q²⟩ excess **5.3 → 2.9**" | 2.9 reproduces only **excluding part C** (all-38 mean = 4.01); v6-side 5.3 not reproducible from surviving files (~4.95–5.05 excl. C) | state the exclusion; recover or soften |
| A5 | Fig 17: "tunneling to β = 256 vs HMC frozen at 16" | **No surviving data anywhere** — only script 13 | rerun script 13 or mark unarchived |
| A6 | "L = 128 (**64×** training area)" | 128²/32² = **16×** | → 16× |
| A7 | Table S3 "\|z(⟨Q²⟩)\|>2: 13 vs 3" | inconsistent inf-counting; consistent = 13 vs 5, or 11 vs 3 | pick one, footnote inf |
| A8 | "ESS/N at the 1/64 floor in every row except knob-only" | baseline 16:14.1 = 0.0230, big-net = 0.0207 (1.3–1.5× floor) | "at or near" |
| A9 | "B: −2.56 then +0.13" | quotes W(2×2); the flag was the **plaquette** (−3.19 → −1.49/−0.04) | quote matching observable |
| A10 | fresh-seed section | s3's A_bc8 shows an unmentioned Q z = +4.18, χ² p = 0.003 | add one sentence |
| A11 | "addresses **four** questions: (1)…(5)" | five enumerated | → five |
| A12 | L64 diffusion "\|z\| ≤ 1.8" | max 1.834 | → "< 2" |

## Minor (code)

- **`train.py:239-244`** — validation draws t ~ U[0,1], ignoring the
  `high_beta_sigma_bias` warp used in training; best-epoch selection
  underweights the small-σ/high-β regime the bias exists to fix.
- **`score_net.py:171` / `train.py:57`** — `norm_type` defaults to `"group"`
  (lattice-size dependent); the no-L-dependence claim survives only because
  shipped configs override to `"channel"`. *Flip the default.*
- **`sampler.py:38-52`** — the Langevin corrector runs *after* the final
  denoise, re-injecting O(σ_min) noise; output is ~p_{σ_min}, not the
  denoised mean.
- **`ais.py:180-182` + script 27** — Tables S6/S7 R² are in-sample, refit on
  all data after CV selection (optimism ~p/n ≈ 9–17% at n = 64). Quote CV R².
- **`28_ais_transport.py:154-207`** — the even/odd honesty split covers only
  ESS/std; observables, certificate, and sector-resolved arms use all samples.
- **`report.py:269-282`** — χ² deflation by 1/(2τ_int) with dof = k−1 matches
  only the first moment; the p-value is approximate but feeds verdict tables.
- **`report.py:221-227`** — `ref_frozen` sums tunnelings over all chains while
  the legend claims a per-chain criterion.
- **`12_campaign_verdict.py:62,123-128`** — NaN and missing rows both render
  "-"; inf footnoted only in the Q² column; no hard |z| gate exists in code at
  all (the ±2 band is figure shading and prose only).
- **`likelihood.py:342-385`** — float32 action evaluation at β·V ~ 2×10⁵
  (~0.03-nat rounding) before the float64 certificate cast.
- **`local_updates.py:121-137`** — `topological_update` on unbatched input
  silently mis-broadcasts to `[2,2,L,L]` garbage instead of raising.
- **Creutz rows** carry i.i.d. jackknife errors with no τ_int inflation.
- **`exact.py`** cutoffs are safe across the project's entire (β, L) range but
  lose tail mass far outside it; `wilson_loop_exact(area=0)` NaNs;
  `match_coarse_beta` brentq bracket raises ungracefully; `thin=0` duplicates.
- **`ladder.py:145`** — β_eff = β/(1+4βσ²) is the λ=4 mode of the exact
  harmonic score; the docstring's "exact at any β" overstates (exact only as
  σ → 0). Ladder σ floor (0.1) also dips below the trained floor (0.3).
- **Seed-stream collision** — the same seed feeds the ODE generator and the
  global RNG for the coarse HMC (washed out by burn-in; β_c < 5 only).

## Minor (docs/structure)

- **`u1_2d/README.md:162-190`** — layout block and *every* pipeline command
  still reference the deleted `diffusion/` package; following it fails.
- **Stale invocation examples** in script docstrings (06, 09, 10, 12, 13).
- **`run_campaign.py:136-144`** references deleted `out/diffusion/demo_v6`;
  script 13 writes to nonexistent `out/u1_2d/demo_v6/`.
- `ess_chain/*.log` and `checkpoints/*.history.json` embed old
  `out\diffusion_v2\v2\` paths (historical logs — cosmetic).
- `artifacts/diffusion/...` naming in default/demo/smoke configs (gitignored
  scratch — cosmetic).
- Fig 26a: red annotation collides with legend text. Fig 27a: green
  certificate-band label partly hidden behind the "big net" bar.
- `test_audit_additions.py` triggers a benign `log(0) → -inf` RuntimeWarning
  at `exact.py:54`.
- rkl2 "≈ 80 min" is plausible but not verifiable from logs (~25 min of
  optimizer steps + eval overhead).

---

# Part F — Prioritized actions

1. **Protect the record:** fix M2 (basis flag + default out) — one edit,
   prevents destroying Table S7's provenance. (M6 needs no action: the
   restructure was already committed — see the retraction above.)
2. **One-line bug + cheap rerun:** M1 (`action_type` in scripts 27/19), rerun
   the Villain arm, refresh Table S6.
3. **Report what was measured (highest scientific value):** add the mean-z
   offset (S1), the std(z)-vs-loop-area trend (S3), and the bias-upper-bound
   framing (S6) to the appendix. These are honest negatives that *strengthen*
   the paper by localizing the residual error in the modes theory predicts.
4. **Fix the cost story:** M7 — annotate Fig 18 with the 8820 s entry cost and
   the amortized per-config number.
5. **Claim scoping:** A2/A3 in Part A — restore the modal verb in CLAUDE.md;
   scope "matches exact results" to the observables and precision achieved.
6. **Appendix edits A1–A12**; regenerate or retire `appendix.tex` (M5).
7. **Validation hardening (matters most for SU(2) reuse):** M3 (χ² overflow
   bins), M4 (τ_int-aware study path), S4 (coarse-parent correlation),
   `norm_type` default, validation σ-bias match.
8. **Docs sweep:** `u1_2d/README.md`, script docstrings, `run_campaign.py`.
9. **Optional:** add the A1 ⟨Q²⟩-invariance identity to NARRATIVE §7–8 — the
   single best return on writing effort in this list.

Since `u1_2d` is frozen (bug-parity fixes only), items 1–6 are within the
freeze's letter (record safety, a bug fix, and reporting corrections); item 7
is best applied to the shared machinery as it is carried into `su2_2d`.

---

# Part G — Work completed on this audit (2026-08-03)

Applied in this session; all 111 tests pass (`pytest u1_2d/tests -q`).

## Code fixes

**M2 — AIS basis, record protected.** `u1_2d/model/ais.py` now defines
`FEATURE_NAMES` as the 7-feature basis that produced Table S7 (verified
against `ais_transport/ais_results.json`), with `RICH_FEATURE_NAMES` (11) and
`BASIS_FEATURE_NAMES` retained to reproduce the recorded negative.
`bridge_features(..., basis="final7")` is the default and rejects unknown
bases; `_BridgeAction` and `ais_correct` thread it through. `scripts/28` gains
`--basis {final7,rich11}` (default `final7`), records the basis and width in
its report header, and now defaults `--out` to the gitignored
`artifacts/u1_2d/ais_transport` so a bare rerun can no longer overwrite the
results of record. `ais_correct`'s `n_bridge` default moved 24 → 48 to match
the runs of record. Bonus fix: `fit_surrogate` labelled coefficients by
zipping against the *fine* feature names regardless of width, mislabelling
every coarse regression; it now selects names by width.

**M1 — Villain matching.** `scripts/27` and `scripts/19` now pass
`action_type` to `approx_matched_coarse_beta`. Verified: Villain matching is
now exactly β/4 (14.1464 → 3.5366, 55.0237 → 13.7559, 218.58 → 54.6450, all
0.0000% error) where the old call returned the Wilson values (4.0, 14.1464,
55.0236). **The Table S6 numbers still come from the buggy run** and are
annotated as such in the appendix; rerunning the Villain arm is the remaining
task.

**Test suite.** `test_bridge_action_force_matches_finite_difference` set a
rich-basis coefficient (`g[8]`) and would have silently broken; it now
parameterizes over both bases. Added `test_bridge_basis_widths` pinning
final7 as the default and `RICH_FEATURE_NAMES[:7] == FEATURE_NAMES`. 110 →
111 tests.

## Figure and document fixes

**Fig 18 regenerated** (`scripts/17_appendix_figures.py`): the diffusion arm
is now charged its own entry cost. Added `CAMPAIGN_DATA_SECONDS` (21.7 min)
and `CAMPAIGN_TRAIN_SECONDS` (125.3 min) sourced from `out/u1_2d/run.log`,
drawn as a dashed line at **8820 s** — above every instanton-HMC point that
converges — plus an amortized curve (+1.8 s/config over the 38×128 configs
the checkpoint served, giving ~4.2 s/config). Title and legend rewritten;
layout collisions fixed.

**`CLAUDE.md`** — restored the modal verb: exactness *must* come from
Markov-chain machinery (a design directive for SU(2)) rather than *comes
from* (a false claim about the shipped U(1) pipeline). Added the
no-accept/reject fact, the seeded-mode distinction, the ⟨Q²⟩ ladder-invariance
identity, and the validation caveat. Also corrected "AIS bridging is the
validated exactness mechanism" — AIS saturated its floor but did not lift ESS.

**`appendix.md`** — added the scope-of-claim section (validated heuristic vs
measure; 448/2098 nats per config), the ladder-invariance derivation, a new
"Validation sharpness and the residual bias" section (S1/S2/S3/S6 above), the
Fig 18 entry-cost paragraph, the Table S6 Villain correction notice, the
Table S7 basis/reproduction note with the in-sample-R² caveat, and corrections
A1–A12 (B_bt6 p 0.43→0.39, the 1.77/1.74 vs-reference relabel with vs-exact
1.06/1.08, 24→26 of 29, the track-C exclusion, the Fig 17 unarchived note,
64×→16×, the Table S3 inf-counting footnote, "at or near" the ESS floor, the
B_bt20 observable, the A_bc8 s3 residual, four→five questions, |z| ≤ 1.8 →
max 1.83).

**`appendix.tex`** — was a full revision behind; brought level. Added the
scope subsection, ladder invariant, validation-sharpness subsection, Figs
23–27, Table S5, the exactness-endgame subsection with Tables S6 and S7, the
measured KL, the L=64 head-to-head, and program closure. Fixed the stale Fig
10 caption that `V2_AUDIT.md` item 8 flagged (fixed in .md only until now),
the Fig 18 caption, the intro's missing fifth question, the 1.77/1.74
convention, the 64×→16× area factor, and the track-C exclusion. Now 27
figures / 7 tables, environments and braces balanced, 768 lines (was 438).

**`docs/NARRATIVE.md`** — §8 gains the ⟨Q²⟩ ladder-invariance derivation and
the fixed-physical-volume reading; §20 gains the three scoping qualifications
(bias upper bound, coherent offset, loop-size dispersion) and the cost-honesty
paragraph; the §20 directive now states explicitly that "must" is not "does"
and that the shipped pipeline is an observable-validated heuristic. **Part V
(§23–26) added**: prior art, positioning, referee objections, and a minimum
citation set — see below.

## Literature review (new Part V of NARRATIVE.md)

The study was conducted without a related-work search; the two source
documents contained **two citations total**. A systematic search found:

- **The headline concept is substantially published.** Zhu, Aarts, Wang, Zhou
  & Wang, JHEP 03 (2026) 111 / arXiv:2502.05504 — diffusion for 2D U(1),
  β-extrapolation without topological freezing, size generalization without
  retraining, *and* exactness via Metropolis-adjusted Langevin. All four of
  this project's claimed advantages, plus the exactness it measured as out of
  reach.
- **Inverse-RG configuration generation** is Ron–Swendsen–Brandt (2002) and
  Bachtis–Aarts–Di Renzo–Lucini PRL 128, 081603 (2022); the coarse→fine
  learned map is Bauer et al. arXiv:2412.12842.
- **The classical ancestor is Endres et al. PRD 92, 114516 (2015)** —
  RG-matched coarse → prolongate → rethermalize, with a *charge-preserving*
  prolongator. This project is that with a learned prolongator, and it is
  uncited and uncompared.
- **The instanton/winding baseline is published**: Albandea et al. EPJC 81,
  873 (2021), for this exact theory.
- **Schaefer–Sommer–Virotta NPB 845, 93 (2011)** shows Wilson loops decouple
  from slow topological modes — the published physics explanation for the
  observable-vs-density dissociation measured independently here.
- **What remains novel**: inverse-RG scale doubling applied to *gauge* fields;
  the analytic matched-β ladder plus the ⟨Q²⟩ invariance identity; and above
  all **the falsification program** — Bachtis (arXiv:2310.12631) explicitly
  lists incorporating exactness into inverse-RG methods as open work. The
  project's strongest contribution is its negative result.

**One agent claim was rejected on verification.** The literature agent
reported the project's "Singha et al. Lattice 2026 / Q-shift" memory as a
misattribution. It is not: that work is a **Lattice 2026 conference talk**
(indico, with slide-level references), invisible to an arXiv-only sweep, and
every independently checkable element corroborates — including Albandea et al.
and arXiv:2604.10209, both confirmed by the same sweep. Two consequences
recorded in §23.7: the "ESS/N ≈ 0.5–0.7" figure in the Fig 19 caption is
sourced from *there* and is **flat in volume**, making it a stronger
comparator than the volume-collapsing general-flow literature; and any future
literature search must cover Lattice proceedings, so Part V's *negative*
claims ("nobody has done X") are weaker than its positive ones.

## Remaining

**All items below were closed on 2026-08-15.** The list is kept with its
resolutions rather than deleted, because two of them changed published numbers.

1. **M3 (χ² overflow bins) — FIXED.** `validate/report.py` now pools
   low-expectation bins and out-of-support charge into overflow cells and
   always emits a verdict; `u1_2d/tests/test_pq_chi2_gate.py` pins the
   behaviour. This mattered more than the review estimated: the gate had been
   silently dropping the test at the **three highest couplings in the 38-case
   study** (β = 218.58 / 398.5 / 872.8), which Table S3 reported as "no
   populated bins to test". All three are testable with pooling and all three
   pass. Separately, the deliberately-mismatched track-B controls move from
   marginal to catastrophic (B_bt55.0237: p = 4.3×10⁻⁵ → 3.2×10⁻⁵⁴) once
   out-of-support charge is counted instead of discarded.
2. **M4 (τ_int-aware study path) — FIXED.** `06_generalization_study.py` passes
   `n_chains`/`ref_n_chains`. Re-validating the cached ensembles
   (`48_revalidate_tau_aware.py`, no regeneration needed) moves mean |z_exact|
   0.957 → 0.888 on the transport arm and 0.847 → 0.778 on the exact-sector
   arm, and drops |z| > 3 flags from 38 to 33. Table S3 regenerated.
3. **`norm_type` default — FIXED.** Flipped `"group"` → `"channel"` in
   `score_net.py` (×2) and `train.py`. No recorded result moves: every shipped
   config already overrode it and checkpoints carry `norm_type` in
   `model_kwargs`.
4. **Validation σ-bias match — FIXED.** Validation drew t ~ U[0,1] while
   training raised t to k(β), so best-epoch selection scored a noise
   distribution the model was not trained on. `sample_sigma` gained a `t`
   override so validation reuses the training warp with its own seeded stream.
   Affects future training only.
5. **Part V citations — CHECKED, bibliography added** (NARRATIVE §26.1). 14
   entries verified against arXiv/INSPIRE/publisher; 15 explicitly listed as
   unverified rather than presented as confirmed. Two real errors found: the
   study conflated *two different* Zhu et al. papers (arXiv:2502.05504 = JHEP
   03 (2026) 111, the journal paper, vs arXiv:2410.19602, the NeurIPS workshop
   paper actually digitized in §25.6b), and the Rançon citation dropped an
   author. One apparent error is genuine coincidence and must not be "fixed":
   Zhu JHEP 03 (2026) 111 and Bonanno JHEP 03 (2021) 111.
6. **Publish-only items — both DONE.** The Endres-style prolongator comparison
   is Table S6b; the ESS rerun at N ≫ 64 is in NARRATIVE §25.5 (n = 512 gives
   exactly 1/512 — the estimator tracks 1/N, so it was never merely
   unresolved).

The review's stated justification for prioritizing M3 was `su2_2d` reuse. That
package is set aside, but M3 was worth fixing on its own terms: it was hiding a
sector test in the U(1) study's own headline regime.

**Done in this session** beyond the fixes above: M6 retracted (already
committed); `u1_2d/README.md` and the five script docstrings corrected; the
Villain arm rerun with the M1 fix and Table S6 updated (see below).
