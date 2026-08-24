# Transport vs generation: the thesis test

`u2_2d/scripts/51_transport_ablation.py`, run 2026-08-24. Same checkpoint, same
data, same schedule, one switch: `enforce_coarse_charge`.

Until this run, `enforce_coarse_charge` had been a config flag for the whole
life of the study and **no run had ever set it false**. u1 measured the
equivalent (NARRATIVE 21.6); u2 -- the non-abelian setting that is the
extension's novelty -- had not.

## The result

| rung | L | beta | exact `<Q^2>` | TRANSPORTED | GENERATED | generated/exact | raw sector match |
|---|---|---|---|---|---|---|---|
| 0 | 32 | 105.651 | 1.0012 | 1.0156 (z = +0.32) | 4.2881 (z = **+17.67**) | **4.28x** | 0.229 |
| 1 | 64 | 416.524 | 1.0012 | 1.0156 (z = +0.32) | 17.0410 (z = **+21.16**) | **17.02x** | 0.082 |

Four things to read off it.

**1. The model manufactures topological charge, and it gets worse with volume.**
4.3x at L = 32 and **17x at L = 64**. The raw sector match -- the fraction of
fine configurations that would have landed in their own coarse partner's sector
unaided -- falls 0.229 -> 0.082. This reproduces u1's volume trend (29% ->
11.5% -> 6.2% at L = 32 -> 64 -> 128, NARRATIVE 21.6) in a non-abelian theory,
and it is a LARGER effect than anything published: u1's own raw lift runs to
2.5-5.4x and Zhu et al.'s published histograms give 2.36x.

**2. An exact symmetry is violated at 5.4 sigma, and this needs no closed form.**
The action is invariant under U -> U*, which sends Q -> -Q, so P(Q) is exactly
even and `mean(sign Q)` must vanish. Transport-off at the top rung gives
**C-asymmetry z = -5.40**; transport-on gives +0.28. So the generated topology
is demonstrably wrong by a test that cannot be blamed on the reference and that
PORTS TO ANY THEORY WITH A TOPOLOGICAL CHARGE -- including 4D SU(3), where no
closed-form P(Q) exists. This is the single most transferable line in the study.

**3. Sector count inflates too:** 27 occupied sectors against 7. "Explores a
wider range of topological sectors" is exactly what Zhu et al. report as their
success criterion, and against the exact answer it is a 17x overshoot. Width is
not correctness.

**4. The transport identity is visible in the table itself.** The transported
`<Q^2>` is **1.0156 +- 0.0457 at BOTH rungs, identical to four digits** --
because they are literally the same charges, carried up unchanged. The ladder
fixed point makes that the right answer at both couplings, and it is 0.3 sigma
from exact at each.

## The control that caught a bug

`transport_on`'s sector match must be 1.000 by construction, so it is reported
as a control rather than a result. On the first run it read **0.592** at rung 0.
Cause: `03_run_ladder` subsamples the base by taking the LAST 1024 of its 4096
(CLAUDE.md records this), and the script took the first 1024 -- comparing
unrelated pairs. Fixed; both rungs now read 1.000. Note the `<Q^2>` columns were
never affected, since they do not depend on pairing; only the match-rate column
was, and only at rung 0 (0.174 -> 0.229).

**Keep controls that must return a known constant.** This one cost nothing and
caught a silent misalignment that would have understated the match rate.

## Why the raw output does NOT already carry the coarse charge

The obvious objection: the determinant telescope says the coarse plaquette is the
wrapped sum of its four fine ones, so `Q_fine = Q_coarse` should be automatic.
**The identity is exact. The model's satisfaction of its PREMISE is not.**

The telescope holds for configurations that are exactly blocking-consistent.
`generate_fine_from_coarse` only guides toward that: `consistency_weight = 1.0`
adds `blocking_consistency_score` as a SCORE TERM, not a constraint. That term
is active in BOTH arms -- `enforce_coarse_charge` removes only the charge
projection (in-sampler every 10 steps below `sigma = 0.5`, plus a final one) --
so this ablation isolates transport and does not also strip reconstruction
guidance.

Measured on the raw output:

| | rung 0 (L = 32) | rung 1 (L = 64) |
|---|---|---|
| per-cell telescope error, mean | 0.44 rad | 0.22 rad |
| cells off by > 0.5 rad | 36.6% | 7.2% |
| **std(Q_fine - Q_coarse)** | **1.79** | **3.36** |
| Q matches coarse exactly | 22.9% | 10.4% |

The model gets each cell's flux approximately right, but **Q is a GLOBAL INTEGER
summing over 1024 / 4096 coarse cells**, so the per-cell residuals accumulate.
Coarse cells go 1024 -> 4096 (4x) and the charge error grows 1.79 -> 3.36
(1.88x): a **sqrt(V) random walk**, to within 6%.

(The LINK-level blocking error is mean pi/2, essentially uniform. That is gauge
freedom, not error -- the guidance acts on plaquettes, and a gauge transformation
moves links without moving flux. Do not quote it as a failure.)

**The arithmetic closes, which pins the mechanism.** With
`<Q^2> = <Q_c^2> + 2<Q_c d> + <d^2>`:

* rung 0: 1.0156 + 3.215 = **4.23** against a measured **4.288**, so
  `<Q_c d> ~ 0.03` -- the error is uncorrelated with the true charge;
* rung 1: its coarse input is rung 0's OWN transport-off output, so
  `<Q_c^2> = 4.288`, giving 4.288 + 11.82 = **16.1** against a measured
  **17.04**.

**So the 17x is not one lift's error -- it is two lifts of random walk
compounding.** That is the sharp statement, and it is the exact complement of
`45_multi_lift_compounding.py`, which measures charge preserved in **100%** of
configurations at 1, 2 and 3 lifts WITH transport on:

> With transport, composition is exactly charge-preserving at any depth.
> Without it, the charge error compounds as a sqrt(V) random walk per lift.

`apply_coarse_charge` is therefore not reading off a charge the model already
has. It is what MAKES THE IDENTITY'S PREMISE TRUE, and it is the only thing
standing between an exact transport identity and a compounding random walk.
That is a stronger argument for the architecture than "the model gets topology
wrong", and it is the form the paper should use.

Provenance: measured 2026-08-24 on `out/u2_2d/ladder_transport_off/`, blocking
error via `u1_2d.lgt.blocking.block_links` on `det_links(...)`, telescope error
as the wrapped difference between each coarse plaquette angle and the sum of its
four fine ones.
