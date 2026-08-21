# Challenger vs incumbent

Incumbent: `out/u2_2d/checkpoints/det_score_net.pt` (12 fixed couplings)
Challenger: `out/u2_2d/checkpoints/det_score_net_v2.pt` (114 rungs, 3 volumes, random beta, sector augmentation)

| criterion                  |    incumbent |   challenger | verdict | note |
| -------------------------- | ------------:| ------------:| --- | --- |
| (a) <Q^2> ladder base      |       0.9668 |       0.9822 | PASS | exact 1.0012, SEM 0.044; z -0.78 -> -0.43 |
|     <Q^2> top rung         |       1.1406 |       0.9375 | info | transported identity: subsample draw, NOT a model test |
| (b) t_therm L32            |       0.0000 |       0.0000 | FAIL | tuned sweeps 5 -> 30 |
| (b) t_therm L64            |       1.0000 |       6.0000 | FAIL | tuned sweeps 5 -> 35 |
| (c) ext loops L=32         |       0.1866 |       0.2919 | FAIL | mean |z| vs exact, area >= 16 (5% tolerance) |
| (c) ext loops L=64         |       1.1341 |       1.2252 | FAIL | mean |z| vs exact, area >= 16 (5% tolerance) |
| (d) KL/site 8:3.5:14       |       1.1099 |       1.1291 | FAIL |  |
| (d) KL/site 8:7:28         |       1.1172 |       1.1309 | FAIL |  |
| (d) KL/site 16:28:105.651  |       1.1362 |       1.1396 | FAIL |  |
| (d) KL/site 32:105.651:416.524 |       1.1467 |       1.1409 | PASS |  |
| (d) density gap overall    |         --   |         --   | FAIL | 3 of 4 cases worse |

## Verdict

**TRADE, NOT AN IMPROVEMENT** -- target met, 8 guard(s) regressed. Incumbent stays deployed unless the regressions are argued case by case.

Promotion is a separate deliberate act: copy `det_score_net_v2.pt` over `det_score_net.pt` and re-run the downstream stages against `default.yaml`.
