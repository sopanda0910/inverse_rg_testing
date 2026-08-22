# Challenger vs incumbent

Incumbent: `out/u2_2d/checkpoints/det_score_net.pt` (12 fixed couplings)
Challenger: `out/u2_2d/checkpoints/det_score_net_v2.pt` (114 rungs, 3 volumes, random beta, sector augmentation)

| criterion                  |    incumbent |   challenger | verdict | note |
| -------------------------- | ------------:| ------------:| --- | --- |
| (a) <Q^2> ladder base      |       0.9668 |       0.9822 | PASS | exact 1.0012, SEM 0.044; z -0.78 -> -0.43 |
|     <Q^2> top rung         |       1.1406 |       0.9375 | info | transported identity: subsample draw, NOT a model test |
| (b) t_therm L32            |       0.0000 |       0.0000 | FAIL | tuned sweeps 5 -> 30 |
| (b) t_therm L64            |       1.0000 |       6.0000 | FAIL | tuned sweeps 5 -> 35 |
| (c) ext loops L=32         |       0.1682 |       0.2919 | FAIL | mean |z| vs exact, area >= 16 (5% tolerance); null 0.798, N_eff 1.45 of 13 rows, SE 0.50 -- the move is 0.2 SE, i.e. UNRESOLVED |
| (c) ext loops L=64         |       1.0606 |       1.2252 | FAIL | mean |z| vs exact, area >= 16 (5% tolerance); null 0.798, N_eff 1.27 of 13 rows, SE 0.54 -- the move is 0.3 SE, i.e. UNRESOLVED |
| (d) KL/site 8:3.5:14       |       1.1099 |       1.1291 | FAIL |  |
| (d) KL/site 8:7:28         |       1.1172 |       1.1309 | FAIL |  |
| (d) KL/site 16:28:105.651  |       1.1362 |       1.1396 | FAIL |  |
| (d) KL/site 32:105.651:416.524 |       1.1467 |       1.1409 | PASS |  |
| (d) density gap overall    |         --   |         --   | FAIL | 3 of 4 cases worse |

**Reading criterion (c).** `mean |z|` is not read against zero. |z| is half-normal when the model is exactly right and the error bars are correct, so the null is `sqrt(2/pi) = 0.798`; a score far BELOW it is evidence of overestimated errors or of correlated observables, not of a good model. The resolution of the mean is `sqrt(1 - 2/pi) / sqrt(N_eff)` with `N_eff` the participation ratio of the observables' correlation matrix. Over the whole scorecard that is 3.73 at L = 32 against 41 rows; over the area >= 16 subset this criterion actually averages it is **1.45**, so those thirteen loops are worth about one and a half independent observables and the standard error of their mean |z| is ~0.50. A move of a tenth is a fifth of a standard error and is not a regression.


## Verdict

**TRADE, NOT AN IMPROVEMENT** -- target met, 8 guard(s) regressed. Incumbent stays deployed unless the regressions are argued case by case.

Promotion is a separate deliberate act: copy `det_score_net_v2.pt` over `det_score_net.pt` and re-run the downstream stages against `default.yaml`.
