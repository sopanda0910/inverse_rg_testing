# Diffusion pipeline vs instanton HMC

Instanton HMC (global Q-hop Metropolis move, dS ~ 2 pi^2 beta / V -- the uniform Q-shift of Albandea-style topology moves) is the strongest classical baseline this project has: it keeps tunneling to beta = 256 where standard HMC froze at beta = 16 (script 13). The question here is whether the diffusion ladder still wins against *it* on wall-clock cost per independent configuration while matching exact observables.

Arm B cost includes everything: matched-coarse HMC base (with Q-hops), conditional diffusion sampling, and rethermalization (honest default: no Q-hops during retherm). Arm A cost per config is 2 tau_int x sec/traj / n_chains, i.e. its marginal equilibrium cost, with burn-in reported separately as the one-time entry fee.

| beta_f | arm | quality (z vs exact) | <Q^2> (exact) | tau_int slowest | s / independent config | one-time cost s |
|---|---|---|---|---|---|---|
| 4.44 | instanton HMC | pass | 6.73 +- 0.35 (6.8) | 4.7 | 0.008 | 12 (burn-in) |
| 4.44 | diffusion | max|z|=14.2 | 6.62 +- 0.78 (6.8) | n/a (independent draws) | 0.206 | 0 (amortized in per-config) |
| 14.1464 | instanton HMC | pass | 1.92 +- 0.057 (1.9) | 4.2 | 0.012 | 24 (burn-in) |
| 14.1464 | diffusion | max|z|=3.4 | 1.8 +- 0.19 (1.9) | n/a (independent draws) | 0.190 | 0 (amortized in per-config) |
| 55.0237 | instanton HMC | max|z|=13.1 | 0.461 +- 0.0093 (0.474) | 6.9 | 0.036 | 38 (burn-in) |
| 55.0237 | diffusion | max|z|=3.8 | 0.406 +- 0.051 (0.474) | n/a (independent draws) | 0.395 | 0 (amortized in per-config) |
| 118.5 | instanton HMC | max|z|=6.2 | 0.165 +- 0.0059 (0.171) | 5.1 | 0.039 | 59 (burn-in) |
| 118.5 | diffusion | max|z|=8.1 | 0.18 +- 0.034 (0.171) | n/a (independent draws) | 1.134 | 0 (amortized in per-config) |
| 218.58 | instanton HMC | max|z|=22.1 | 0.0238 +- 0.0021 (0.029) | 7.3 | 0.072 | 75 (burn-in) |
| 218.58 | diffusion | max|z|=5.7 | 0.0391 +- 0.017 (0.029) | n/a (independent draws) | 1.475 | 0 (amortized in per-config) |

Notes. (1) Diffusion configs are conditionally independent given the coarse ensemble; residual correlation enters only through the thinned coarse HMC chains. (2) Instanton-HMC tau_int is per-observable Madras-Sokal on per-chain series, discarding the first 25%; its Q mixing is genuine (tunnelings counted), unlike the pipeline's structurally transported sector. (3) Quality threshold |z| <= 2.5. (4) The diffusion per-config cost amortizes the coarse base over the batch; scaling the batch up lowers it further, while the HMC interval cost is irreducible per config.

Settings: chains=32, burn-in=500, production=640 traj, n_gen=128, seed=20260731, checkpoint=out/u1_2d/checkpoints/score_net.pt.