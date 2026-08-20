# Do the geometric prolongators match the learned one on extended observables?

$L = 64$, $\beta = 416.524$, 256 configurations per arm, identical post-processing (30 conditional SU(2) sweeps + 10 rethermalization sweeps).

`17_prolongator_baseline.py` showed local observables cannot separate these arms, and that sector transport is imposed identically on all of them. Extended loops and per-configuration spread are the remaining places a bad lift could still be visible after the exact SU(2) sampler has run.

| arm | extended mean $|z|$ | extended max $|z|$ | plaquette $z$ | $\langle Q^2\rangle$ | $P(Q)$ covered | $\sigma$ ratio $8\times8$ |
|---|---|---|---|---|---|---|
| **diffusion** | 1.54 | 1.78 | +0.41 | 1.055 | 1.000 | 0.977 |
| tile | 0.53 | 0.58 | +0.42 | 1.055 | 1.000 | 1.036 |
| halve | 1.93 | 1.97 | -0.17 | 1.035 | 1.000 | 0.962 |
| flux | 0.13 | 0.18 | -1.47 | 1.055 | 1.000 | 0.973 |
| smear | 0.37 | 0.70 | +0.07 | 1.055 | 1.000 | 1.010 |

## What to read off it

**The learned lift is WORSE on extended loops too.** Mean $|z|$ 1.54 against `flux`'s 0.13. There is then no measured observable on which the model beats a geometric map, and the honest claim is about the ladder and the exact conditional sampler, not the lift.

Read the $P(Q)$ and $\langle Q^2\rangle$ columns as a control, not a result: `apply_coarse_charge` imposes the coarse charge on every arm, so these are expected to be identical and a difference would indicate a bug.

Source: `u2_2d/scripts/21_prolongator_observables.py`.
