# AIS surrogate ridge: controlled scan

sigma = std of the log importance weight, nats. ESS/N ~ exp(-sigma^2);
usable reweighting needs sigma <~ 1.52. Every entry below is far
above that -- this scan explains a failure mode, it does not fix the sampler.

The `record` column is the published Table S7 run, which used a DIFFERENT
coarse ensemble (the unseeded-fold RNG stream); it is shown for orientation
and is not a controlled comparison. The numbered columns all share identical
ODE samples and baselines, so only regularization differs across them.

## held-out sigma (nats)

| case | baseline sigma | record | none | 0.01 | 0.03 | 0.1 | 0.3 |
|---|---|---|---|---|---|---|---|
| 16:14.15 | 17.3 | 33.61 | 117.1 | 107.2 | 30.51 | 11.43 | 10.76 |
| 16:55.02 | 30.0 | 18.59 | 228.5 | 228.5 | 228.5 | 408.8 | 552.8 |
| 32:55.02 | 78.0 | 28.42 | 6439 | 3138 | 1510 | 112.8 | 32.84 |
| 32:218.6 | 118.6 | 44.37 | 2132 | 97.73 | 45.68 | 43.1 | 46.48 |

## surrogate coefficient norm

| case | baseline sigma | record | none | 0.01 | 0.03 | 0.1 | 0.3 |
|---|---|---|---|---|---|---|---|
| 16:14.15 | 17.3 | 40.03 | 53.42 | 37.61 | 28.98 | 18.19 | 10.1 |
| 16:55.02 | 30.0 | 3.179 | 38.31 | 38.31 | 38.31 | 25.8 | 16.76 |
| 32:55.02 | 78.0 | 89.68 | 100.3 | 88.03 | 74.35 | 53.84 | 35.95 |
| 32:218.6 | 118.6 | 48.4 | 127.9 | 118.3 | 104.3 | 79.7 | 57.9 |

## minimum HMC acceptance

| case | baseline sigma | record | none | 0.01 | 0.03 | 0.1 | 0.3 |
|---|---|---|---|---|---|---|---|
| 16:14.15 | 17.3 | 0.755 | 0.474 | 0.474 | 0.635 | 0.854 | 0.922 |
| 16:55.02 | 30.0 | 0.979 | 0.875 | 0.875 | 0.875 | 0.958 | 0.979 |
| 32:55.02 | 78.0 | 0.932 | 0.245 | 0.323 | 0.286 | 0.729 | 0.953 |
| 32:218.6 | 118.6 | 0.969 | 0.958 | 0.958 | 0.958 | 0.958 | 0.958 |

## What the scan establishes

* Coefficient norm falls monotonically with the ridge floor in 3 of 4 cases, so the floor does what it is meant to do.
* Held-out sigma improves with regularization in 3 of 4 cases, and REVERSES in 16:55.02 -- more regularization is not universally better, so there is a per-case optimum and no single floor to hard-code.
* **32:218.6 refutes the acceptance guard.** Minimum HMC acceptance is flat at 0.958 across the whole scan while held-out sigma moves 43.1 -> 2132 against a baseline of 118.6. A run can blow up by 18x with a perfectly healthy integrator, so `hmc_acceptance_min` is not a sufficient guard; coefficient norm is the quantity that tracks the failure.

Best achievable spread reduction per case, over the scan:

* 16:14.15: 1.61x at floor 0.3
* 16:55.02: never beats baseline (best 228.5 vs 30.0)
* 32:55.02: 2.38x at floor 0.3
* 32:218.6: 2.75x at floor 0.1

All best-case sigmas remain >= 1.52 by a wide margin, i.e. ESS/N stays indistinguishable from zero.
