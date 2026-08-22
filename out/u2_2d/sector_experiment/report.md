# Does the training sector distribution matter?

Two arms, identical but for the distribution the training configurations' topological
charges were drawn from. Built by `39_sector_distribution_data.py`, trained from
`configs/sector_{exact,uniform}.yaml`.

## 0. The arms' separation on the training data

- 106 re-seeded ensembles.
- `<Q^2>` uniform / exact: median **5.60x**, range 3.20-88.00.
- mean odd fraction: exact 0.414, uniform 0.504.

**This is the power check.** If these were close there would be nothing to detect and any agreement below would be vacuous.

## 1. Observable agreement after the ladder

| rung | exact: mean \|z\| | uniform: mean \|z\| | exact: ext loops | uniform: ext loops |
|---|---:|---:|---:|---:|
| L=32 beta=105.651 | 0.924 | 0.912 | 1.053 | 0.871 |
| L=64 beta=416.524 | 0.594 | 0.690 | 0.559 | 0.816 |

## 2. Trajectories to thermalization (prolongator, rung 0)

| arm | exact: t_therm | uniform: t_therm |
|---|---:|---:|
| ape | 368.0 | 368.0 |
| diffusion_raw | 2.0 | 5.0 |
| diffusion_tuned | 0.0 | 8.0 |
| smear | 5.0 | 5.0 |

## 3. Verdict

**THE SECTOR DISTRIBUTION DOES NOT MATTER.** The arms agree on observable
agreement to within 0.096 in mean |z| despite training data whose `<Q^2>`
differs by a factor of several. The closed-form P(Q) is therefore a CONVENIENCE for
building training data and a REQUIREMENT for scoring -- not a requirement of the
method. What the training data must supply is sector COVERAGE, which can be
manufactured without a closed form. This is the result that lets the construction
be claimed for 4D SU(3), where no closed-form P(Q) exists.

---

## 4. How strong is this null? (added 2026-08-22)

A null result must come with the size of the effect it could have detected.

**CORRECTED 2026-08-22 -- the first version of this section was wrong by a
factor of 3.3 and quoted a bound three times tighter than the data support.**

Each rung's `mean |z|` averages 41 observables, but they are NOT independent.
Measured with `u2_2d.validate.stats.effective_observable_count`, the correlation
matrix of those 41 has top eigenvalue **18.6** (one mode carries 45% of the
variance) and mean within-family |correlation| **0.62**, because 2D Wilson loops
of different sizes are near-deterministic functions of one another. The
participation ratio gives **N_eff = 3.77**, not 41.

For a correct model with correct errors `|z|` is half-normal: mean
`sqrt(2/pi) = 0.798`, sd `sqrt(1 - 2/pi) = 0.603`. So

* SE of one arm's `mean |z|` = 0.603 / sqrt(3.77) = **0.311** (not 0.094)
* SE of the DIFFERENCE between arms = **0.440** (not 0.133)

The observed differences are 0.012 (L=32) and 0.096 (L=64), i.e. **0.03 and
0.22 sigma**. Both remain consistent with zero, but the smallest difference this
test could resolve at 2 sigma is **0.88** -- larger than the null value itself.

**So the honest statement is much weaker than first written: the sector
distribution has no effect larger than ~0.9 in mean |z|, at training data whose
`<Q^2>` differs by a median factor of 5.6 (range 3.2-88).** That still points
the right way and is still worth reporting, but as a weak bound. The strong form
of the transfer argument should lean on u1's `sector_augment` instead, which
builds charged-sector coverage from fixed instanton shifts and never consults a
closed form at all -- a demonstration by construction rather than a null test.

Note also that the arms' `mean |z|` values (0.594-0.924) straddle the null value
of 0.798, which is the sign of a healthy scorecard. The 0.187 seen in the
capacity comparisons sits 2.0 sigma below the null at `N_eff` -- suggestive of
overestimated error bars, but not the 6.5 sigma it appeared to be when the raw
count of 41 was used.

**One hint runs the other way and should not be buried.** The prolongator's
`t_therm` favours the exact arm at rung 0: `diffusion_tuned` 0 against 8, and
`diffusion_raw` 2 against 5. Those are single t_therm values, and t_therm is now
known to be rugged in coupling -- 59 / 51 / 6 / 50 records at adjacent couplings
in the u2 crossover scan, reproducibly. So this is a hint, not a result, and the
way to settle it is more couplings rather than more trajectories at this one.
