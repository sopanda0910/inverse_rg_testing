# Do the geometric prolongators match the learned one on extended observables?

$L = 64$, $\beta = 416.524$, 256 configurations per arm, identical post-processing (30 conditional SU(2) sweeps + 10 rethermalization sweeps).

`17_prolongator_baseline.py` showed local observables cannot separate these arms, and that sector transport is imposed identically on all of them. Extended loops and per-configuration spread are the remaining places a bad lift could still be visible after the exact SU(2) sampler has run.

| arm | extended mean $|z|$ | extended max $|z|$ | plaquette $z$ | $\langle Q^2\rangle$ | $P(Q)$ covered | $\sigma$ ratio $8\times8$ |
|---|---|---|---|---|---|---|
| **diffusion** | 2.11 | 2.17 | -0.28 | 0.891 | 0.995 | 1.061 |
| tile | 0.47 | 0.67 | +0.59 | 0.891 | 0.995 | 1.075 |
| halve | 1.03 | 1.25 | +0.40 | 0.895 | 0.995 | 0.976 |
| flux | 1.30 | 1.41 | -1.86 | 0.891 | 0.995 | 1.077 |
| smear | 0.79 | 1.11 | +0.03 | 0.891 | 0.995 | 0.991 |

## What to read off it

**The learned lift is WORSE on extended loops too.** Mean $|z|$ 2.11 against `tile`'s 0.47. There is then no measured observable on which the model beats a geometric map, and the honest claim is about the ladder and the exact conditional sampler, not the lift.

Read the $P(Q)$ and $\langle Q^2\rangle$ columns as a control, not a result: `apply_coarse_charge` imposes the coarse charge on every arm, so these are expected to be identical and a difference would indicate a bug.

Source: `u2_2d/scripts/21_prolongator_observables.py`.
