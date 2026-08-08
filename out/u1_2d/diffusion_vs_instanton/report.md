# Diffusion pipeline vs instanton HMC

Instanton HMC (global Q-hop Metropolis move, dS ~ 2 pi^2 beta / V -- the uniform Q-shift of Albandea-style topology moves) is the strongest classical baseline this project has: it keeps tunneling to beta = 256 where standard HMC froze at beta = 16 (script 13). The question here is whether the diffusion ladder still wins against *it* on wall-clock cost per independent configuration while matching exact observables.

Arm B cost includes everything: matched-coarse HMC base (with Q-hops), conditional diffusion sampling, and rethermalization (honest default: no Q-hops during retherm). Arm A cost per config is 2 tau_int x sec/traj / n_chains, i.e. its marginal equilibrium cost, with burn-in reported separately as the one-time entry fee.

| beta_f | arm | quality (z vs exact) | <Q^2> (exact) | tau_int slowest | s / independent config | one-time cost s |
|---|---|---|---|---|---|---|
| 4.44 | instanton HMC | pass | 7.08 +- 0.38 (6.8) | 4.3 | 0.006 | 8 (burn-in) |
| 4.44 | diffusion | pass | 6.91 +- 0.98 (6.8) | n/a (independent draws) | 2.279 | 0 (amortized in per-config) |
| 14.1464 | instanton HMC | pass | 1.87 +- 0.058 (1.9) | 5.0 | 0.011 | 16 (burn-in) |
| 14.1464 | diffusion | pass | 1.9 +- 0.23 (1.9) | n/a (independent draws) | 2.393 | 0 (amortized in per-config) |
| 55.0237 | instanton HMC | max|z|=7.1 | 0.47 +- 0.0084 (0.474) | 6.8 | 0.029 | 31 (burn-in) |
| 55.0237 | diffusion | pass | 0.398 +- 0.051 (0.474) | n/a (independent draws) | 2.367 | 0 (amortized in per-config) |
| 118.5 | instanton HMC | max|z|=9.4 | 0.172 +- 0.0042 (0.171) | 4.6 | 0.026 | 42 (burn-in) |
| 118.5 | diffusion | pass | 0.172 +- 0.033 (0.171) | n/a (independent draws) | 2.755 | 0 (amortized in per-config) |
| 218.58 | instanton HMC | max|z|=16.6 | 0.0324 +- 0.0022 (0.029) | 8.6 | 0.065 | 58 (burn-in) |
| 218.58 | diffusion | pass | 0.0156 +- 0.011 (0.029) | n/a (independent draws) | 2.551 | 0 (amortized in per-config) |

Notes. (1) Diffusion configs are conditionally independent given the coarse ensemble; residual correlation enters only through the thinned coarse HMC chains. (2) Instanton-HMC tau_int is per-observable Madras-Sokal on per-chain series, discarding the first 25%; its Q mixing is genuine (tunnelings counted), unlike the pipeline's structurally transported sector. (3) Quality threshold |z| <= 2.5. (4) The diffusion per-config cost amortizes the coarse base over the batch; scaling the batch up lowers it further, while the HMC interval cost is irreducible per config.

Settings: chains=32, burn-in=500, production=640 traj, n_gen=128, seed=20260731, checkpoint=artifacts/gpu_verify/checkpoints/score_net.pt.