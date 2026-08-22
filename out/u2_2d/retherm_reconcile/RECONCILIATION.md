# The W(8x8) rethermalization disagreement: both numbers were noise

`42_retherm_reconcile.py`, L = 64, beta = 416.524, 256 configurations, the two
statistics measured on the SAME configurations in one pass.

## The answer

Neither source measurement was resolved. At W(8x8) the single-configuration
spread is **19500 ppm**, so with 256 configurations the standard error on the
mean is **1219 ppm**. Against that:

| claim | value | z | resolved? |
|---|---|---|---|
| `31_division_of_labour.py`, seed PRE-retherm | 378 ppm | **0.31** | no |
| `31_division_of_labour.py`, seed POST 10 sweeps | 1581 ppm | **1.30** | no |
| this run, raw lift | -949 ppm | -0.78 | no |
| this run, after 10 sweeps | +1.6 ppm | 0.00 | no |

The sign flips with sweep count in this run -- -949, -2498, +424, +1.6, +723,
-1614 ppm at 0/2/5/10/20/40 sweeps -- which is what an unresolved quantity does.

So `31`'s "rethermalization makes W(8x8) four times worse" was 0.31 sigma
against 1.30 sigma, and `33_retherm_scan.py`'s "2.3x better" was the same
quantity fluctuating the other way. **Both scripts are arithmetically correct
and neither result exists.** `31`'s N* reproduces here to within ensemble noise
(2661 against its 2501 pre, 152 against its 137 post), confirming this is the
same measurement rather than a different one.

## What is retracted

**The "ACTIONABLE DEFECT" finding is withdrawn.** It read: post-retherm
`N* = 137` at W(8x8) while the delivered L = 64 ensemble carries 256
configurations, therefore the ensemble is already past the point where its own
W(8x8) systematic exceeds its statistical error, therefore `n_retherm` should be
tuned against that. `N* = (sigma/bias)^2` computed from a bias consistent with
zero is unbounded -- at 10 sweeps here it evaluates to 1.4e8 -- so the finding
was an artefact of squaring a noise fluctuation. There is no measured basis for
retuning `n_retherm`, and no measured basis for the claim that
rethermalization damages the infrared in u2.

The claim that rethermalization damages the infrared was already flagged as
u2-only and absent in u1, where the repair factor merely reaches 1.0. It is now
absent in u2 as well.

## What survives

The scale decomposition itself, at the two scales where it is resolved:

| scale | raw bias | SEM | z | verdict |
|---|---|---|---|---|
| W(1x1) | 61.8 ppm | 3.3 | **18.6** | real, and rethermalization removes it (z 18.6 -> -0.16) |
| W(2x2) | 64.9 ppm | 20.1 | **3.2** | real, removed (z 3.2 -> 0.67) |
| W(4x4) | 87.6 ppm | 143.9 | 0.6 | not resolved at 256 configs |
| W(6x6) | -137 ppm | 493 | -0.3 | not resolved |
| W(8x8) | -949 ppm | 1219 | -0.8 | not resolved |

So the honest form of the division-of-labour claim at this coupling is:

> The model's residual is resolvable only at W(1x1) and W(2x2), where it is
> ~62-65 ppm, and ten local rethermalization sweeps remove it at both. At
> W(4x4) and larger the RAW lift is already statistically indistinguishable
> from exact at 256 configurations, so nothing can be said about what the tail
> does there without a much larger ensemble.

That is weaker than the original claim in reach but stronger in standing: the
part that is measured is measured at 18.6 and 3.2 sigma, and the part that is
not measured is now labelled as such rather than reported as a trend.

Note the consequence for the flatness claim ("relative bias 62 / 67 / 69 ppm
across W(1x1) / W(2x2) / W(4x4), flat while the theory's own sigma grows
374x"). Two of those three points are resolved; the third is an upper bound of
~290 ppm at 2 sigma, which is CONSISTENT with 69 ppm but does not confirm it.
State it as two resolved points plus a consistent bound.

## Why the two statistics did not diverge here

`sigma_1config` at W(8x8) moves only from 19503 to 18199 ppm across ten sweeps
(x0.93). The metric-artefact hypothesis -- that rethermalization inflates the
dispersion enough for a flat ppm bias to fall in bias/sigma -- is therefore
refuted directly: the denominator is flat to 7% and cannot carry a 4x
disagreement. The disagreement was in the numerator, and the numerator is noise.

`<Q^2>` is 0.8281 at every sweep count, unchanged to all printed digits --
rethermalization runs with `topological_updates=False`, so transport survives
the tail exactly, as designed.

## Could rethermalization have made a large loop genuinely worse?

Yes -- which is why the retracted claim was plausible rather than absurd, and
why it needed a measurement rather than an argument to kill it.

A Markov chain guarantees monotone decrease of the RELATIVE ENTROPY to its
stationary distribution. It guarantees nothing about the error in any
individual expectation value, which is free to overshoot. And there is a
concrete mechanism available here: local sweeps equilibrate short-wavelength
modes in O(1) sweeps while long-wavelength modes relax diffusively, on O(L^2).
A large Wilson loop is built from many plaquettes, so re-dressing the
ultraviolet changes the loop's measured value while the loop's own slow mode is
still sitting at whatever the seed gave it. A seed that is accidentally close in
the infrared and wrong in the ultraviolet can therefore have its large loops
pushed AWAY from exact by a short tail, and only recover on the slow timescale.

So "rethermalization is a low-pass repair that can damage the infrared" is a
coherent physical story. It is simply not what these data show. At this coupling
and this ensemble size the large loops are unresolved both before and after, and
the resolved scales -- W(1x1) and W(2x2) -- improve monotonically.

Testing the story properly would need either many more configurations (the SEM
falls as 1/sqrt(N), so resolving a 400 ppm effect at W(8x8) takes ~10^4
configurations) or a variance-reduced estimator such as smearing or a
multi-level scheme. Neither is worth doing for a claim that currently has no
evidence behind it.
