# Exactness suite report

## Frontier (rkl2 checkpoint)

| case | ESS/N (fiber) | log-w std | i-MH acc | z(raw) plaq | z(rw) plaq | z(raw) Q^2 | z(rw) Q^2 |
|------|---------------|-----------|----------|-------------|------------|------------|-----------|
| 8:2 | 0.004 | 6.9 | 0.03 | +6.1 | +nan | -3.1 | +nan |
| 8:4 | 0.004 | 6.2 | 0.02 | +0.7 | +nan | +3.5 | +nan |
| 8:8 | 0.006 | 7.5 | 0.02 | -7.3 | +nan | +5.8 | +nan |
| 8:14.1464 | 0.009 | 8.6 | 0.05 | -6.5 | +nan | +8.1 | +nan |
| 16:4 | 0.004 | 12.4 | 0.02 | -1.4 | +nan | +3.5 | +nan |
| 16:8 | 0.006 | 15.9 | 0.02 | -14.3 | +nan | +6.4 | +nan |
| 16:14.1464 | 0.008 | 17.6 | 0.02 | -13.0 | +nan | +7.3 | +nan |
| 16:25 | 0.008 | 18.1 | 0.03 | -6.1 | +nan | +9.1 | +nan |
| 16:55.0237 | 0.004 | 19.8 | 0.02 | -11.1 | +nan | +9.5 | +nan |

## Low-beta check (original v2 checkpoint)

| case | ESS/N (fiber) | log-w std | i-MH acc | z(raw) plaq | z(rw) plaq | z(raw) Q^2 | z(rw) Q^2 |
|------|---------------|-----------|----------|-------------|------------|------------|-----------|
| 8:2 | 0.005 | 8.0 | 0.02 | +12.5 | +nan | -3.4 | +nan |
| 8:4 | 0.008 | 6.7 | 0.01 | +8.3 | +nan | +2.2 | +nan |
| 8:14.1464 | 0.012 | 7.6 | 0.02 | +4.6 | +nan | +5.5 | +nan |
| 16:4 | 0.007 | 12.8 | 0.03 | +10.3 | +nan | +1.8 | +nan |
| 16:14.1464 | 0.004 | 21.0 | 0.02 | +2.7 | +nan | +6.3 | +nan |

## SMC ladder

base 8:1.3472, n = 192, checkpoint `out/diffusion_v2/v2/checkpoints/score_net_rkl2.pt`

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