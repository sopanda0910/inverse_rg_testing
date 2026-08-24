# Test parity between the u1 and u2 studies

**Goal.** The two studies should carry the SAME tests, so that a difference in
result is a statement about the theories rather than about what was measured.
They are expected to disagree -- 2D U(1) and 2D U(2) freeze differently, and
only u2 has a Z_2 monodromy -- but a claim made for one and never tested in the
other is a hole, not a finding.

**Status legend.** `both` = the test exists in both packages. `gap` = missing
where it should exist. `u1 only` / `u2 only` = deliberately theory-specific,
with the reason stated.

Last updated 2026-08-22.

## 1. Shared tests

| test | u2 script | u1 script | status |
|---|---|---|---|
| exact identities (must pass, seconds) | `09_verify_identities.py` | `29_verify_identities.py` | both |
| seed as an HMC starting point | `08_hmc_seed_benchmark.py` | `14_diffusion_vs_instanton_hmc.py`, `16_h2h_burnin_scan.py` | both |
| seed quality vs training coverage | `28_crossover_scan.py` + `30_seed_quality_figure.py` | `50_seed_quality_figure.py` | both |
| volume scan | `28_crossover_scan.py --fine-size 64` + `38_volume_figure.py` | `51_volume_scan_figure.py` | both |
| topology transport | `36_transport_check.py` + `37_transport_figure.py` | `53_transport_figures.py` | both |
| pre/post rethermalization decomposition | `31_division_of_labour.py`, `33_retherm_scan.py`, `42_retherm_reconcile.py` | `59_pre_post_retherm.py` | both |
| cost against the classical baseline | `13_cost_comparison.py` | `55_cost_figures.py` | both |
| density gap / KL per site | `18_density_gap.py` | `15_model_ess.py`, `19_ode_reweighting.py` | both |
| **multi-lift compounding** | **`45_multi_lift_compounding.py`** | **`60_multi_lift_compounding.py`** | **both (NEW 2026-08-21)** |
| **verdict calibration against a synthetic null** | **`48_verdict_calibration.py`** | **`65_therm_criterion_calibration.py`** | **both as of 2026-08-24** -- u1's half calibrates the `t_therm` rule, not the P(Q) verdict; see section 5 item 10 |
| **appendix figure gate** | **`49_assemble_appendix_figures.py --check`** | `30_assemble_appendix_figures.py --check` | **both as of 2026-08-22** -- different staleness tests by necessity, see section 5 item 14 |

## 1b. The prolongator ablation -- AN UNTRACKED GAP, found 2026-08-24

This row was missing from section 1 entirely, and because it was missing the two
studies drifted to **different rigor** on the experiment that decides whether the
learned lift is necessary at all.

| | u2 (`17_`, `21_`) | u1 (`37_tiling_baseline.py`) |
|---|---|---|
| `tile` / `halve` / `flux` | yes | yes |
| `ape` (deterministic smearing, tuned) | yes | yes |
| **`smear` (heatbath + overrelaxation, exact local sampler)** | **yes** | **NO -- added 2026-08-24** |
| **`diffusion_tuned` (the seed put through the SAME tuning)** | **yes** | **STILL MISSING** |
| retherm masking controlled (`--n-retherm 0`) | yes | n/a (arms go straight into HMC) |

**Why it matters.** u2's narrative calls `smear` *"the strongest thing
available"*, and compact U(1) has the identical exact local updates
(`u1_2d.lgt.local_updates.heatbath_sweep`, `overrelaxation_sweep`). u1's Table
S6b therefore concluded *"the learned map wins by an order of magnitude"*
against `ape`, which is **not** the strongest classical arm. Measured after
adding it (L = 32, 64 configs, same coarse ensemble):

| beta_f | `ape` | **`smear`** | diffusion seed |
|---|---|---|---|
| 4.44 | 49 (S6b) | **0** (5 sweeps) | 8 |
| 14.15 | 136 | **10** (10 sweeps) | 0 |
| 55.02 | 252 | **> 640** (10 sweeps, under-tuned) | 0 |
| 218.58 | 148 | see `out/u1_2d/smear_baseline/` | 7 |

At beta_f = 4.44 the classical arm **beats** the seed; at 14.15 the baseline was
understated 13.6x. The beta_f = 55.02 cell is a protocol artefact, not a result:
`tune_smear` stops when the PLAQUETTE crosses exact, which is right for APE
(monotone, overshoots) and wrong for heatbath (an exact sampler cannot
overshoot, so more sweeps are never worse). `--smear-sweeps` now runs a fixed
count instead.

**The obligation this creates.** A margin measured against a weaker arm is not a
margin. The comparison that survives is u2's **matched-budget** one -- both
starts through the identical tuning procedure, compared on sweeps of local
repair needed (u2: `diffusion_tuned` 5 against `smear`'s 35 and 15). **u1 has no
matched-budget arm and needs one before submission.**

General rule, and the reason this row now exists: **an ablation is only as
strong as its strongest arm, so the arm list itself is a parity obligation.**
Tracking only script names would not have caught this -- both studies had "a
prolongator ablation".

## 2. Gaps being closed

| test | u2 | u1 | note |
|---|---|---|---|
| sweeps vs trajectories as the repair move | `44_sweeps_vs_trajectories.py` | **`61_sweeps_vs_trajectories.py`** | **CLOSED 2026-08-22, and the two agree** -- see section 6. |
| observable agreement across beta, with z | `43_observable_scan.py` (fig29) | **`62_observable_scan.py`** (fig 46) | **CLOSED 2026-08-22.** u1's ceiling is a sharp step because its coverage is dense to beta = 60, not a set of isolated rungs. |
| sector-distribution ablation (exact P(Q) vs uniform) | `39_/40_sector_*` | **NOT NEEDED -- see section 3** | u1 has no closed-form dependency to ablate. |
| reverse-diffusion step count as a cost dial | `14_sampler_steps.py` | **`63_sampler_steps.py`** | **CLOSED 2026-08-22, and u1's win is bigger than u2's.** u1's post-retherm |z| is flat from 18 steps to the deployed 200 (1.39 -> 1.39 at beta_f = 55.02; 1.24 -> 1.21 at 218.58) for a 10-14x cheaper lift, against u2's ~3x at 25 steps. **And the column to score is the opposite one**: in u1 the RAW bias changes sign between 12 and 18 steps and raw |z| GROWS with step count, so a raw-scored knee picks the cheapest setting for the wrong reason -- score the POST column. u2's dial says the reverse. `v3_scale.yaml` moves to 18 steps once `configs/v3_scale_s18.yaml` verifies end to end. |

## 3. Why the sector ablation does NOT port to u1 -- and that is a result

The u2 experiment (`39_/40_sector_*`) asked whether the closed-form P(Q) used to
install charges in TRAINING data is load-bearing, by rebuilding the data with a
deliberately wrong (uniform) sector distribution. **That question is already
answered in u1, and more strongly, by u1's shipped pipeline.**

`u1_2d/scripts/01_generate_data.py::sector_augment` takes a random half of the
configurations at a rung and appends copies shifted by a FIXED instanton charge
of +-1 or +-2, then relaxes the strain with 8 sweeps at `topological_updates=
False`. It never draws from P(Q); it never consults a closed form. It
manufactures COVERAGE and nothing else. It is active on all four high-beta
anchors of the deployed `v3_scale.yaml`, so every u1 result of record was
produced with sector coverage built without an exact P(Q).

So:

* u2 measured that a WRONG sector distribution costs nothing, at data whose
  `<Q^2>` differs by a median 5.6x. **The bound is weak, though, and the number
  first written here was wrong by 3.3x**: the arms differ by 0.096 in mean |z|,
  which at `N_eff = 3.77` excludes only effects larger than **~0.88**, not the
  ~0.27 quoted originally at the raw count of 41. It is a null result, but a
  loose one -- see section 5 item 3.
* u1 demonstrates the stronger statement by construction -- NO sector
  distribution is needed at all, and the pipeline that produced the paper's
  results is the existence proof.

Both point the same way, which is what the 4D SU(3) transfer argument needs:
what training data must supply is sector COVERAGE, and coverage can be
manufactured by applying known topological shifts to existing configurations.
That construction needs a way to CHANGE the charge, not a way to WEIGHT it, and
an instanton shift is available in any theory with a topological charge.

Note also that u2's score net models `psi = arg det U`, which is an honest
compact U(1) gauge field. The u2 sector experiment is therefore already a U(1)
experiment in substance; running a second one in `u1_2d` would largely repeat it
with a different action and a different net size.

## 4. Deliberately theory-specific

| test | where | why it does not port |
|---|---|---|
| exactness program: AIS transport, ESS, MALA, PTBC, Zhu head-to-head | u1 only (`28`, `15`, `45`, `43`, `46`) | u1 is the paper's exactness argument. u2 inherits the conclusion rather than re-deriving it; re-running PTBC in particular measures nothing, since both theories have an exact global move. |
| parity / Z_2 monodromy: parity-flip counting, marginal odd move, joint-vs-marginal head-to-head | u2 only (`15_base_parity.py`, `34_marginal_move_bias.py`) | 2D U(1) has no monodromy. There is no odd/even distinction to freeze. |
| U(2) character expansion, `matched_u1_beta`, determinant-sector P(Q) | u2 only (`lgt/exact.py`) | u1's exact results are the classical ones; the U(2) analogues had to be derived. |
| conditional SU(2) sampler | u2 only | u1 has no non-abelian sector. |

## 5. Method audits that must be applied to BOTH

These are not scripts but obligations, and each was found by an error in one
study that the other then had to be checked for.

1. **Never quote a bias without its SEM.** A u2 finding -- rethermalization
   making W(8x8) "four times worse" -- was retracted on 2026-08-21 when both
   disputed numbers turned out to sit at z = 0.31 and z = 1.30 against a SEM of
   1219 ppm. See `out/u2_2d/retherm_reconcile/RECONCILIATION.md`.
   * u1 audit, done 2026-08-21: `59_pre_post_retherm.py` already records `z`,
     `relative_sem`, `sigma_1config` and `n_star`, so it survives better. At
     beta_f = 55.02 the repair-factor trend (64x / 14x / 3.9x / 1.6x) IS on
     resolved raw numbers at W(1x1)-W(6x6), but the headline endpoint --
     "ten sweeps do nothing at all for W(8x8)", factor 0.99 -- rests on a raw
     z of **1.17**, which is NOT resolved. State that entry as unresolved.
     **DONE 2026-08-22:** the Figure 38 caption in
     `out/u1_2d/paper_appendix/appendix.md` now carries the whole
     resolution table (raw z 29.33 / 8.07 / 3.64 / 2.04 / 1.17) and marks the
     W(8x8) endpoint as not resolved. `u2_2d/scripts/31_division_of_labour.py`
     (fig22) does the u2 half: unresolved scales are drawn HOLLOW, the shaded
     band marks where the raw lift is already consistent with exact, and the
     retracted "actionable defect" is struck from its docstring.
   * At beta_f = 218.58 every raw value is resolved (z = -256 to -34) but every
     POST-retherm z is <= 0.41, so the repair factors there (up to 256094x) are
     **lower bounds**, not measurements.

2. **`N* = (sigma/bias)^2` squares the bias**, so it is unbounded wherever the
   bias is unresolved. Quote N* only at scales that pass the SEM test.

3. **`mean |z|` has a null value of sqrt(2/pi) = 0.798** -- AND its standard
   error must use the EFFECTIVE number of observables, not the raw count. This
   item was itself wrong when first written here, by a factor of 3.3, and the
   correction is the more important half.

   Measured 2026-08-22 (`u2_2d.validate.stats.effective_observable_count`): the
   41 observables scored at L = 32 have a correlation matrix whose top
   eigenvalue is **18.6** -- one mode carries 45% of the variance -- and a mean
   within-family |correlation| of **0.62**, because 2D Wilson loops of different
   sizes are near-deterministic functions of one another. The participation
   ratio gives **N_eff = 3.77** at L = 32 and **3.25** at L = 64, so
   `SE(mean |z|) = sqrt(1 - 2/pi) / sqrt(N_eff)` is **0.31**, not 0.09.

   Everything that used the raw count was overstated by 3.3x:

   | claim | with N = 41 | with N_eff | verdict |
   |---|---|---|---|
   | validation L=32, mean abs z = 0.484 | 3.3 sigma below null | **1.0 sigma** | unremarkable |
   | capacity ext loops, 0.187 | 6.5 sigma | **2.0 sigma** | suggestive, not damning |
   | sector ablation, arms differ 0.096 | 0.72 sigma, excludes > 0.27 | **0.22 sigma, excludes only > 0.88** | far weaker bound |

   So the "scorecard four times better than perfect" alarm was largely an
   artefact of treating correlated observables as independent.
   **Never quote a `mean |z|` without `N_eff` beside it.**

   **And on a SUBSET the count collapses further.** Measured the same day on the
   thirteen area >= 16 Wilson loops that `25_challenger_report.py` guard (c)
   averages: **N_eff = 1.45 at L = 32 and 1.27 at L = 64**. Those thirteen loops
   are worth about one and a half independent observables, so the standard error
   on that column is ~0.50 and every challenger comparison run through it is
   unresolved -- the v2 moves are 0.2 and 0.3 SE, the capacity moves 1.0 and
   1.4 SE. The residual "2 sigma" quoted above was itself computed at the
   all-observable N_eff and is really **1.0 SE**; it is not worth acting on.
   The capacity verdict does not depend on it -- that rests on the tuned sweep
   count and the density gap, neither of which is a z.

   **CLOSED IN CODE, 2026-08-22.** `validate.report.compare` records
   `n_effective` and `n_effective_extended` on every summary it writes;
   `u2_2d/scripts/47_effective_observables.py` back-fills the artefacts that
   predate it; `25_challenger_report.py` prints the resolution beside every
   guard-(c) verdict and refuses to let a fifth-of-a-sigma move read as a
   regression. The declared 5% gate itself is unchanged, deliberately.

4. **tau_int-aware errors are the right convention but were NOT the explanation
   here.** u2 adopted u1's estimator (`u2_2d/validate/stats.py`, wired through
   `04_validate.py --generated-n-chains`). Measured effect on the ladder of
   record: `mean |z|` 0.522 -> 0.484 at L = 32 and 0.789 -> 0.728 at L = 64, a
   7-8% correction -- real, worth keeping, and far too small to account for the
   sub-null scores; item 3 does that. Two traps found while wiring it: the
   estimator assumes chain-major ordering (`index = draw * n_chains + chain`,
   which u2's `sample` does satisfy) and silently returns a plausible ~0.5 if
   that is violated; and the deployed ensembles predate the `n_chains` metadata
   field, so `03_run_ladder`'s subsample guard had been inactive without saying so.

5. **Relative deviation is not comparable across beta.** The theory's own
   per-configuration spread falls by orders of magnitude as beta rises, so an
   unnormalized ratio drifts downward whether or not the model improves --
   Spearman -0.82 against model beta in u2's fig29, which REVERSES to +0.80 in
   z. Report both, or report z.

6. **A single t_therm is not interpolatable to a neighbouring coupling.**
   Measured in u2: 59 / 51 / 6 / 50 records at adjacent couplings, reproducible
   across two independent rounds and across two independent implementations.
   Correlations over a scan are fine; named example points are not.

7. **Mark in-sample couplings on every figure.** u2's fig21 and fig29 now do.
   Any point whose coarse AND fine side are both training rungs is not evidence
   of generalization.

8. **A measurement of a tunable is only about the deployed system if it READS
   the deployed configuration.** Found 2026-08-22 in u1:
   `63_sampler_steps.py` scanned the reverse-diffusion step count using
   `generate_fine_from_coarse`'s bare defaults instead of the config's, so it
   measured a sampler with `physics_blend_coef = 0.0` while the pipeline runs
   1.0 with a beta-aware sigma floor. It recommended a 10-14x cheaper setting
   that in fact degrades the RAW lift 3-4x. The deployed 16 rethermalization
   sweeps hid that in the delivered ensemble, so an ensemble-level check would
   have passed it -- verified, `out/u1_2d/validation_s18/` matches the record
   while its raw lift is 4x worse.
   * u1: fixed; the script now takes `--config` and reads every knob from it.
   * u2 audit, same day: `14_sampler_steps.py` calls the real `generate_ladder`
     and reads `ladder_cfg` throughout, and its schedule comes from the
     checkpoint -- clean.
   * **Corollary, and it is the sharper half: score the RAW product when the raw
     product is what is sold.** u1 sells the seed, so its knee is set by the raw
     column (200 steps), not the post column (18). u2's script already says to
     read the RUNG 0 pre-retherm column for the same reason. A single "knee" is
     the wrong shape of answer when the pipeline has two consumers.

10. **A VERDICT IS A TEST, AND AN UNCALIBRATED TEST IS NOT EVIDENCE.** Found
    2026-08-22 in u2, and it is the sharpest methodological item in this file.
    `07_pq_sampling.py` had emitted `SAMPLED` / `PARITY-STUCK` / `DISAGREES`
    labels for months, and those labels gated `seed_exact_sectors` and the
    choice of ladder base. None of them had ever been checked against data whose
    answer was known. `48_verdict_calibration.py` does that -- it feeds the
    script synthetic charge histories drawn from the closed-form P(Q) itself, so
    the null is true by construction, and counts how often each verdict fires.

    On EXACT data the verdict misfired **13%** of the time. Worse, on the arm
    where every chain is pinned to one parity forever -- the precise pathology
    `PARITY-STUCK` exists to catch -- the old `|odd_z| > 2` rule fired at 5%,
    its null rate, because each chain's parity had been drawn from the CORRECT
    weight so the pooled odd fraction came out right. It had no power on its own
    target while rejecting good data. After the rebuild (flip counts for
    mobility, a bootstrap-calibrated goodness-of-fit for agreement) the true
    nulls pass 99% and the pathology is caught 100%.

    * The general rule: **any script that emits a categorical verdict needs a
      synthetic-null harness beside it.** Cheap -- this one runs no simulation
      at all, it only needs a generator for the null and the script's own
      `analyse`/`verdict` functions imported by path.
    * u1 audit obligation, **PARTLY CLOSED 2026-08-24**:
      `65_therm_criterion_calibration.py` calibrates the `t_therm` rule against
      synthetic series drawn under the null (correct mean, correct errors, AR(1)
      autocorrelation), 1500 replicas at the deployed 64-chain shape. **A
      PERFECTLY THERMALIZED ENSEMBLE REPORTS t_therm = 0 ONLY 79-85% OF THE
      TIME, with a 90th percentile of 3-4.** So `t_therm <= 3` is the resolution
      floor of the metric and differences inside it are not measurements. Two
      consequences: PAPER_OUTLINE contribution 1's "median 4 across 35
      couplings" sits AT the floor, and the honest claim is "the seed arrives
      already at equilibrium, within the resolution of the metric" -- stronger
      than the number it replaces; and the seed's t_therm = 7 at
      beta_f = 218.58 is only weakly resolved. Power is fine where it matters:
      a 2-SEM offset gives median 41, a 4-SEM offset never converges.
      Still OPEN: `12_campaign_verdict.py` and the chi-squared sector gate
      behind Table S3.
    * Corollary that came out of it: **significance is not effect size.** A
      z-threshold gets arbitrarily strict as statistics grow, so a gate meant to
      catch a gross structural failure will eventually fire on a 0.8% deviation.
      Where the pathology is structural, COUNT it (parity flips) rather than
      testing it.

11. **A LOW-BUT-PASSING p-VALUE IS WORTH A SECOND SEED, NOT A FOOTNOTE.** The
    sharpest of the 2026-08-22 u2 lessons, and the cheapest to act on. After the
    verdict rebuild, L = 16 beta = 56 returned a goodness-of-fit p of 0.022 --
    above the alpha = 0.01 gate, so it PASSED, and it was written up as
    "SAMPLED-but-watch". An independent-seed confirmation returned p = 0.0002
    with `<Q^2>` z = -0.09, odd/exact z = -0.21 and no individual sector past
    1.2 sigma: a rejection with no disagreement anywhere in it.

    The cause was a third bug in the same statistic -- sector frequencies are
    multinomial and sum to a constant, so the all-ones direction carries
    essentially zero variance, and a pseudo-inverse at `rcond = 1e-10` inverted
    it, dividing a tiny mean offset by a tinier variance. Dropping one bin
    removes the redundancy exactly (no tuning parameter, unlike raising
    `rcond`), and both datasets then read X^2 = 3.46 and 1.97.

    Two things to carry:
    * **Inspection did not find it.** The pooled-tail rule was the obvious
      suspect and made no difference at all (< 0.01 in X^2). Re-running at a
      different seed found it in one shot.
    * **A borderline p-value is a cheap experiment away from being settled.**
      Where a verdict is close to its threshold, the right response is another
      seed, not a hedge in the write-up.

12. **Save the expensive intermediate, not just the summary.** The u2 statistics
    above were rebuilt twice in one day, and each rebuild cost hours of HMC to
    regenerate verdicts because `07_pq_sampling.py` wrote only its summary. It
    now saves the `[n_draws, n_chains]` charge histories and takes
    `--reanalyse`, which recomputes every verdict from them with no simulation.
    The rule generalizes: if the analysis is a pure function of a cheap-to-store
    intermediate, store it -- an analysis bug then costs a re-analysis instead
    of a re-run. u1 audit obligation, OPEN: check which u1 stages discard their
    per-configuration series.

13. **Superseded artefacts get a README, not a deletion.** When u2's validation
   moved to tau_int-aware errors on 2026-08-22, the naive-SEM run was kept at
   `out/u2_2d/validation_naive_superseded/` with a README saying what is wrong
   with it, and the promoted directory got one saying what changed and how to
   read `mean |z|` against the null. Same for `configs/v3_scale_s18.yaml`, which
   is kept as the record of a negative result. A deleted artefact cannot be
   audited and a silently promoted one cannot be trusted.

14. **A FIGURE DIRECTORY NEEDS A GATE, AND THE GATE MUST MATCH HOW THE
    FIGURES ARE PRODUCED.** u1 had `30_assemble_appendix_figures.py --check`
    from the start; u2 had 39 figures written in place by sixteen scripts with
    no manifest, no captions and no way to tell whether a figure predated its
    data. `docs/u2_2d/FIGURE_PARITY.md` tracks which CLAIMS have a figure and
    says nothing about whether the file on disk is current.
    `u2_2d/scripts/49_assemble_appendix_figures.py` (2026-08-22) closes it, but
    NOT by copying u1's test: u1's figures are copies, so staleness is a hash
    mismatch against the source; u2's are written in place, so there is no
    second copy and the comparable quantity is TIME -- a figure is stale when
    it is older than the newest input it was drawn from. **The port would have
    been vacuous done literally.** It caught three figures on its first run
    (`fig08`, `fig12`, `fig23`, all drawn from the naive-SEM validation before
    the tau_int-aware promotion). Captions are single-sourced in the script and
    `--write-appendix` generates the markdown appendix from them, so a caption
    cannot drift between manifest and appendix.
    **u1 audit obligation, OPEN, and state it precisely.** For the 20 u1
    figures that are COPIES the hash test already covers this: a regenerated
    source changes the hash and reports STALE. But **26 of u1's 46 are written
    directly into the figure directory by their own script** (`SOURCES[name] is
    None`), exactly like every u2 figure, and for those u1 records no inputs and
    performs no staleness test whatsoever -- it only checks the file exists. So
    the gap is confined to those 26, and closing it means giving u1 the input
    table u2 now has.

## 6. Results where the two studies AGREE (added 2026-08-22)

Parity is only worth the effort if it produces statements about the METHOD
rather than about one theory. Three now qualify.

### 6.1 Local sweeps repair the raw lift; trajectories do not

Same experiment, both packages, costs matched in LINK TOUCHES (one retherm sweep
with two overrelaxation passes = 3; one trajectory = `n_steps`).

| study | coupling | sweeps to \|z\| <= 2 | trajectories | ratio |
|---|---|---|---|---|
| u1 | beta_f = 55.02 | 6 touches (2 sweeps) | 380 (20 traj) | 63x |
| u1 | beta_f = 98.47 | 12 touches | never in 1500 | >125x |
| u1 | beta_f = 218.58 | 24 touches | never in 2220 | >92x |
| u2 | model beta 43.9 | 6 touches | never in 4600 | >767x |
| u2 | model beta 134 (+29% past) | 6 touches | never in 2560 | >427x |
| u2 | model beta 327 (+214% past) | 6 touches | never in 2560 | >427x |

Cold-start trajectories never converge in any cell of either study. **This is a
method statement**: the repair for a raw lift is cheap exact local sweeps, not
more HMC, and "the seed does not thermalize" claims are about the MOVE. It also
means `t_therm` measured in trajectories understates the seed by two orders of
magnitude as a practical matter.

Caveat carried from u2: `t_therm` is rugged in coupling (section 5 item 5), so
these are per-coupling costs and not a smooth function of beta.

### 6.2 Error does not compound up the ladder; the final rung sets accuracy

Eight cells (2 theories x 2 endpoints x retherm on/off): three lifts to a fixed
endpoint land at 0.84-1.02x the one-lift error. The per-rung trace shows the
error injected by the FINAL lift, whose distance from training coverage is what
binds. **Laddering therefore does not extend the coupling reach -- it buys
volume.** Figure `out/u2_2d/figures/fig30_multi_lift.png`, report
`out/u2_2d/multi_lift_incov/MULTI_LIFT_REPORT.md`.

### 6.3 The lift transports topology exactly; the tail re-samples it

100% charge preservation at 1, 2 and 3 lifts in all four chains with no
rethermalization between rungs. With the ladder's own ten sweeps, charge moves
wherever an intermediate rung is weakly coupled -- u1 keeps 33.6% (retherm at
beta = 3.87) and 81.2% (beta = 5.24), u2 keeps 98.4% and 100% because its
intermediate rungs are far stiffer. `<Q^2>` moves TOWARD exact when it happens,
so this is re-sampling at rungs where local updates are valid, not corruption.

### 6.4 One place they DIFFER, and it is instructive

In u2's observable scan the relative-deviation and z columns point OPPOSITE ways
across the coupling axis (Spearman -0.82 against +0.80). In u1's they agree.
The reason is range: u2's scan spans model beta 2.8 to 327, over which the
theory's own per-configuration spread changes by orders of magnitude, while
u1's spans beta 6 to 518 with a much flatter spread. So the reversal is a
property of the RANGE, not of either code -- which is the strongest argument for
section 5 item 4 as a standing rule rather than a u2 footnote.

