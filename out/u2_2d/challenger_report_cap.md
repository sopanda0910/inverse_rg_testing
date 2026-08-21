# Challenger vs incumbent

Incumbent: `out/u2_2d/checkpoints/det_score_net.pt` (12 fixed couplings)
Challenger: `out/u2_2d/checkpoints/det_score_net_cap.pt` (hidden 96, depth 5, batch 64, 260 epochs, SAME data_v2)

| criterion                  |    incumbent |   challenger | verdict | note |
| -------------------------- | ------------:| ------------:| --- | --- |
| (a) <Q^2> ladder base      |       0.9668 |       0.9822 | PASS | exact 1.0012, SEM 0.044; z -0.78 -> -0.43 |
| (b) seed quality L32       |         --   |         --   | MISSING |  |
| (b) seed quality L64       |         --   |         --   | MISSING |  |
| (c) extended loops         |         --   |         --   | MISSING |  |
| (d) density gap            |         --   |         --   | MISSING |  |

## Verdict

**INCOMPLETE** -- 4 criterion/criteria not yet measured: (b) seed quality L32, (b) seed quality L64, (c) extended loops, (d) density gap. No verdict until all four are in; a missing guard is not a passed guard.

Promotion is a separate deliberate act: copy `det_score_net_cap.pt` over `det_score_net.pt` and re-run the downstream stages against `default.yaml`.
