# U(2) follow-ups after the marginal odd move (2026-08-20)

Opened when `marginal_winding_update` retired the odd-charge obstruction. Each
item is a *consequence* of that change that has not been chased yet. None of them
block the overnight retrain, which is why they are here rather than in the queue.

Ordered by how much they would change what the paper says.

---

## 1. Re-run `07_pq_sampling.py` under the marginal move -- **DONE 2026-08-22**

**RESULT: every coupling tested SAMPLES topology honestly, at both volumes.**
The old verdicts were measured under the retired JOINT proposal, whose odd
acceptance was 0.000, and they said where P(Q) could be sampled *by a move that
no longer exists*. Under the marginal odd move (`--charge-step 1
--winding-interval 5`), 256 chains x 300 draws at L = 16 and 128 x 300 at L = 8:

| L | beta | <Q^2> z | sector changes | parity flips | frozen | gof p | C-asym z | odd/exact | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 16 | 28 | +0.45 | 45909 | 45909 | 0% | 0.287 | -0.48 | 1.0078 | **SAMPLED** |
| 16 | 51.75 | +0.29 | 34152 | 34152 | 0% | 0.612 | -0.61 | 0.9948 | **SAMPLED** |
| 16 | 56 | +0.55 | 32556 | 32556 | 0% | 0.493 | +1.66 | 1.0020 | **SAMPLED** |
| 16 | 56 (seed 4242) | -0.09 | 32406 | 32406 | 0% | 0.743 | -0.84 | 0.9990 | **SAMPLED** |
| 8 | 6 | -0.68 | 30368 | 19330 | 0% | 0.500 | -1.91 | 1.0056 | **SAMPLED** |
| 8 | 10 | -0.99 | 22853 | 20333 | 0% | 0.665 | -0.07 | 0.9919 | **SAMPLED** |
| 8 | 14 | +0.63 | 17924 | 17839 | 0% | 0.345 | +0.89 | 0.9978 | **SAMPLED** |
| 8 | 20 | +0.20 | 12851 | 12851 | 0% | 0.864 | -0.39 | 1.0042 | **SAMPLED** |

`out/u2_2d/pq_sampling_marginal_L{8,16}_v3/`. **beta = 51.75 and 56 at L = 16
are no longer PARITY-STUCK**, so the standing caveat that they were unusable as
a ladder base is lifted -- those rungs convert from *installed* topology to
*sampled* topology, which is the strictly stronger claim this item was opened
for. At L = 16, every sector change IS a parity flip, as it must be for a
dQ = +-1 move.

**BUT THE VERDICTS THEMSELVES HAD TO BE FIXED FIRST, AND THAT IS THE LARGER
FINDING.** Correcting the `odd_z` error bar (it summed multinomial cells in
quadrature) first turned beta = 28 into PARITY-STUCK and beta = 51.75 into
DISAGREES. Neither survived calibration. `48_verdict_calibration.py` feeds the
script synthetic histories drawn from the closed form, so the null is true by
construction, and found that on EXACT data the old verdict misfired **13%** of
the time -- and that on the `parity_frozen` arm, the precise pathology
`PARITY-STUCK` exists to catch, the old `|odd_z| > 2` rule fired at 5%, its NULL
rate, because each chain's parity had been drawn from the correct weight so the
pooled odd fraction came out right. **The old rule had no power on its own
target while rejecting good data.** Three changes followed:

* mobility is now a parity FLIP COUNT, not a significance gate (a z-threshold
  gets arbitrarily strict as statistics grow -- it was calling a chain with
  45909 sector changes and no frozen chains "stuck" over a 0.8% deviation);
* agreement uses `sector_goodness_of_fit`, a Mahalanobis statistic on the
  per-chain sector-frequency vectors with a bootstrapped p-value and per-chain
  bin pooling (`p * n_draws >= 1`); the old rule kept bins expected to hold 7
  configurations out of 76800, empty in every chain, which destabilized the
  pseudo-inverse and is exactly what produced the spurious beta = 51.75 flag --
  re-analysing that coupling under the new binning moved it 0.041 -> 0.732;
* one bin is dropped before the statistic is formed, removing the
  sum-to-one redundancy (see the flag below -- this was the third and
  last of the statistics bugs);
* a CHARGE-CONJUGATION test was added, `mean(sign Q)` bootstrapped over chains.
  P(Q) must be exactly even in Q, so this needs no closed form at all and cannot
  be blamed on the reference. It is the sharpest diagnostic here.

**Final calibration, all 12 cells at 300 replicas**
(`out/u2_2d/verdict_calibration_v3/`); rejection at alpha = 0.01 against a
nominal 1%, and median goodness-of-fit p against a target of 0.5:

| beta | iid | sticky | parity_frozen caught | odd_bias power |
|---|---|---|---|---|
| 28 | 2% (p 0.527) | 1% (p 0.499) | **100%** | 22% |
| 51.75 | 1% (p 0.493) | 1% (p 0.463) | **100%** | 19% |
| 56 | 1% (p 0.507) | 0% (p 0.525) | **100%** | 15% |

Calibrated on true nulls at every coupling and under autocorrelation, with full
power on the pathology -- against the old test's 13% misfire rate and ~5% power.

**One question this LEAVES OPEN, deliberately.** The `odd_bias` column is the
power at the 0.8% odd-weight deviation actually seen at L = 16, beta = 28, and
it is only 15-22%. So that coupling's `odd_z = +2.61` is neither dismissible nor
established: it is a weak hint of a small real bias in the marginal winding
move. Settling it needs roughly 5-10x the statistics at that one coupling.
Nothing downstream depends on it -- `<Q^2>` is right (z = +0.45), the sector
histogram is right (p = 0.287), and topology is TRANSPORTED from the base rather
than regenerated -- so this is a question about the move's precision, not about
the ladder.

**THE ONE FLAG WAS A THIRD STATISTICS BUG, AND AN INDEPENDENT SEED IS WHAT
FOUND IT.** L = 16, beta = 56 first came back at gof p = 0.022 -- above the
alpha = 0.01 gate but lowest in the set. A confirmation run at seed 4242 came
back at **p = 0.0002, X^2 = 51.6**, with `<Q^2>` z = -0.09 and odd/exact z =
-0.21, and with NO individual sector deviating by more than 1.2 sigma. A
`DISAGREES` with no disagreement anywhere in it is not a physics result, and the
mechanism was the pseudo-inverse: sector frequencies are multinomial and sum to
a constant, so the all-ones direction carries essentially zero variance, and
`rcond = 1e-10` inverted it, dividing a tiny mean offset by a tinier variance.
Dropping ONE bin removes the redundancy exactly -- the textbook multinomial
treatment, and unlike raising `rcond` it has no tuning parameter. The same two
datasets then give X^2 = 3.46 (p = 0.493) and 1.97 (p = 0.743).

Note what did NOT catch this: the pooled-tail rule, which was the first
suspect and turned out to make no difference at all (dropping the near-empty
tail bin changed X^2 by less than 0.01). The bug was found by an independent
SEED disagreeing with the first, not by inspection.

**And the charge histories are now saved**, with a sidecar recording the move
that produced them, so a further change to these statistics costs a
`--reanalyse` (seconds) rather than another afternoon of HMC. That mechanism
paid for itself the same day: the binning-rule change above was applied by
re-analysis, not by re-running.

## 2. Regenerate seed-benchmark arms A–D at 400 trajectories

The arm cache is keyed on arm *name*, not trajectory count, so A–D were reused at
300 while E–H ran at 400. Equilibration is fine either way (2τ_int = 3.2), but
`n_sectors_visited` is cumulative and can only grow with trajectory number, so
A–D are understated on that one column. Visible as the short lines in figure 7.

Cost: ~25 min GPU. Delete `out/u2_2d/seed_benchmark/arm_[A-D]*.json` and re-run
stage 08.

## 3. Re-run `15_base_parity.py` with `charge_step = 1`

`fig09_parity_mobility` and the "odd mobility dies between β = 14 and 20" result
in CLAUDE.md are measurements of the **old proposal's mispricing**, not of the
theory. They are still worth having as the record of why the old move failed, but
the figure should say so on its face. Queued as `stage15_base_parity` in
`run_overnight.ps1` against `out/u2_2d/base_parity_v2`.

## 4. Reconsider `seed_exact_sectors` wholesale

Downstream of item 1. If the marginal move samples P(Q) everywhere the ladder
needs, seeding can be switched off for the training rungs too, and the "seeded
ensembles are not evidence" caveat disappears from the study entirely. That is a
config change plus a full data regeneration, so it is a *next* retrain, not this
one.

## 5. Retune the sampler step count against the new move

`14_sampler_steps.py` found 25 reverse-diffusion steps to be the production
setting (1.38× faster than hmc+winding vs 2.22× slower at 200). That comparison
was against `hmc+winding` with the **even** move only. The odd move costs
1609 ms/trajectory against 211 ms, so the classical arm's cost per *correctly
distributed* configuration is now higher than it was when that ratio was
measured, and the ladder's relative standing improves. The ~90 s fixed overhead
per ladder pass (30 SU(2) + 10 retherm sweeps) is still the untouched knob.

## 6. `13_cost_comparison.py` against eight arms

It selects `D_cold_plus_winding` as *the* classical arm. With G available, the
honest classical baseline for a **topological** cost claim is G, not D — D buys
half of P(Q). `16_cost_figures.py` was given the E–H styles and a grey fallback
on 2026-08-20 so it will not KeyError when this happens.

## 7. Tune `n_retherm` against the infrared, not by eye (added 2026-08-21)

**Status: open, and the only item here with a number attached that is already
out of range.**

`31_division_of_labour.py` measures what the rethermalization tail does to each
distance scale at L = 64, beta = 416.524. Relative deviation from exact, in ppm:

| | W(1x1) | W(2x2) | W(4x4) | W(8x8) |
|---|---|---|---|---|
| seed, PRE-retherm | 61.9 | 67.2 | 69.1 | 378 |
| seed, POST 10 sweeps | 1.3 | 1.9 | 68.7 | **1581** |

Local sweeps equilibrate short wavelengths in a few passes and long ones not at
all, so the tail buys ultraviolet accuracy by SPENDING long-distance accuracy:
W(1x1) improves 47x, W(4x4) is untouched, W(8x8) degrades 4.2x.

The consequence is quantitative, via `N* = (sigma/bias)^2` — the number of
configurations usable before the model's systematic exceeds the user's own
statistical error:

    POST-retherm N*:  1443 / 23865 / 1082 / 137     (W1x1 / W2x2 / W4x4 / W8x8)
    delivered ensemble:                       256 configurations

**The shipped L = 64 ensemble is already ~1.9x past its own W(8x8) bottleneck.**
Nothing in the pipeline currently notices, because `n_retherm: 10` was chosen to
fix the plaquette and validated on the plaquette.

What to do:
1. Scan `n_retherm` in {0, 2, 5, 10, 20, 40} at the top rung and record the full
   scale profile at each, not just the plaquette. The optimum is where max over
   scales of (bias / sigma) is minimised, which is a different criterion from
   "the plaquette agrees".
2. Expect a genuine trade rather than a free win: 0 sweeps leaves W(1x1) at
   1.1 sigma_1config, 10 sweeps leaves W(8x8) at 0.085. There may be no setting
   that puts every scale below the floor, in which case the honest output is a
   stated operating point plus the N* ceiling it implies.
3. Report N* per scale in the validation tables. It is the number a user of the
   ensembles actually needs and it is N-independent, unlike z.

Related: this is the mechanism behind u1's Fig. 38 residual (see item 8).

## 8. u1 PRE/POST — RUN 2026-08-21, and the result corrects item 7

`u1_2d/scripts/59_pre_post_retherm.py`, L = 32, 256 configurations, sweep
profile {0, 2, 5, 10, 20, 40} applied CUMULATIVELY to the same configurations so
the rows are paired.

**The reversal reproduces.** At beta_f = 55.02, z by scale
(W1x1 / W2x2 / W4x4 / W6x6 / W8x8):

    0 sweeps (raw lift)   +34.61  +10.17   +4.35   +2.42   +1.42   falls with area
   10 sweeps (deployed)    +0.53   +0.79   +1.17   +1.64   +1.54   grows with area

So the residual is ULTRAVIOLET-dominated before the tail and INFRARED-dominated
after it. That is the reversal u1's Fig. 38 sees, now with its cause measured
rather than inferred.

**THE REPAIR IS LOW-PASS — this is the quotable table.** Repair factor
(|relative deviation PRE| / |after 10 sweeps|) at beta_f = 55.02:

| W(1x1) | W(2x2) | W(4x4) | W(6x6) | W(8x8) |
|---|---|---|---|---|
| 64x | 14x | 3.9x | 1.6x | **0.99x** |

Monotone in loop size, and exactly 1.0 at W(8x8): ten sweeps do nothing at all
for the largest loop.

**CORRECTION TO ITEM 7.** That item claimed rethermalization DAMAGES the infrared
and that this is the mechanism behind Fig. 38. The damage does NOT reproduce in
u1 — W(8x8) is unchanged (13080 -> 13240 ppm), not 4x worse as in u2 at
beta = 416.5. The correct general statement is weaker and better: the repair is
low-pass, its factor falls monotonically with loop size, reaching 1.0 (no repair)
in u1 and dipping below 1 (active damage) only at the much stiffer u2 coupling.
Item 7's `n_retherm` scan is still worth running for u2; its stated motivation
should be "find where the repair factor crosses 1", not "stop the damage".

**THE DIVISION OF LABOUR IS A REQUIREMENT, NOT AN OBSERVATION.** Because the
repair factor falls to 1 at large scales and is exactly ZERO for Q (retherm runs
`topological_updates=False` and cannot change the sector at all), the accuracy
demanded of the model is scale-dependent and strictest where nothing downstream
can help:

| scale | what the tail does | so the model must be |
|---|---|---|
| Q | nothing, by construction | exact — hence TRANSPORT, not generation |
| W(8x8) | 0.99x | accurate |
| W(4x4) | 3.9x | fairly good |
| W(1x1) | 64x | free to be wrong |

The model meets the obligation where it counts: after ten sweeps W(8x8) is at
+1.54 sigma (beta_f = 55) and +0.14 sigma (beta_f = 218).

**A CAVEAT ON u1'S GENERALIZATION CLAIM, found on the way.** At
beta_f = 218.58 — one of u1's own "validated far outside the training range"
cases — the RAW lift is 257 sigma off on the plaquette and 8.7% off at W(8x8):

    0 sweeps   -257.44  -177.11   -98.09   -62.35   -39.91
   10 sweeps     -0.17    -0.00    +0.09    +0.48    +0.14

with repair factors of 1e3-1e5. Outside the training range the validation is
largely validating the HMC TAIL, not the model. u1's claim is about the
delivered pipeline and stays true as stated, but "the model generalizes far
outside its training range" and "the pipeline's output agrees far outside its
training range" are different sentences and only the second is measured. This
lines up with the u2 beta scan, where the raw lift also collapses past the top
training rung.

**TWO CAVEATS BEFORE THESE NUMBERS GO IN A FIGURE.** (i) The z values use a naive
across-configuration SEM; u1's convention is tau_int-aware error bars
(NARRATIVE 25.7, review item M4). 256 configurations from 16 chains are
correlated, so these |z| are inflated and must be recomputed. N* is NOT affected,
because it uses the single-configuration sigma. (ii) The sweep-to-sweep wobble at
beta_f = 55 (+0.53 -> -2.07 -> -0.13 at 10/20/40) is a correlated walk of one set
of configurations, not a trend; both couplings are converged by ~5 sweeps.

## 9. Should the training loss be reweighted toward long wavelengths? (open)

Speculative, logged because item 8 makes it concrete. Denoising score matching
weights all wavelengths by the noise schedule; nothing in the objective knows
that short-wavelength error is repaired 64x downstream and long-wavelength error
is not repaired at all. A loss reweighted toward long wavelengths would spend
capacity where the repair factor says it is actually needed — and capacity is
exactly what the coverage experiments identified as binding. Do NOT act on this
before the capacity experiment settles; it changes the training objective, and
every previous change to the data side regressed precision at fixed capacity.
