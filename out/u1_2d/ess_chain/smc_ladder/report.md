# SMC ladder: per-level weights + resampling vs plain transport

base 8:1.3472, n = 192, checkpoint `out/u1_2d/v2/checkpoints/score_net_rkl2.pt`

| level | arm | ESS/N | log-w std | uniq | obs | raw z | SNIS z | resampled z |
|-------|-----|-------|-----------|------|-----|-------|--------|-------------|
| 16@4 | transport | 0.005 | 11.3 | -- | plaquette | -1.6 | +35.3 | -- |
| | | | | | Q^2 | +2.5 | +9543.2 | -- |
| 16@4 | smc | 0.005 | 11.8 | 0.01 | plaquette | -1.3 | +274011.7 | +3807093.7 |
| | | | | | Q^2 | +3.1 | +1269135.6 | -- |
| 32@14.1464 | transport | 0.005 | 29.8 | -- | plaquette | -19.3 | +5.9 | -- |
| | | | | | Q^2 | +6.0 | +53.8 | -- |
| 32@14.1464 | smc | 0.005 | 37.3 | 0.01 | plaquette | -13.6 | -362.5 | -308.2 |
| | | | | | Q^2 | +9.3 | +275.4 | +176.4 |

z-scores vs exact character-expansion references (finite volume).
The SMC arm resamples by the per-level fiber weights before each next
lift; unique-ancestor fraction shows how much genuine diversity
survives resampling at this n. Where per-level ESS is usable the
resampled ensemble is asymptotically exact at its level; where it is
not, SNIS z-scores are noisy rather than biased.