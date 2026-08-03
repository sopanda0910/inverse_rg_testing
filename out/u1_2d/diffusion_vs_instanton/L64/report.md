# Diffusion pipeline vs instanton HMC

Instanton HMC (global Q-hop Metropolis move, dS ~ 2 pi^2 beta / V -- the uniform Q-shift of Albandea-style topology moves) is the strongest classical baseline this project has: it keeps tunneling to beta = 256 where standard HMC froze at beta = 16 (script 13). The question here is whether the diffusion ladder still wins against *it* on wall-clock cost per independent configuration while matching exact observables.

Arm B cost includes everything: matched-coarse HMC base (with Q-hops), conditional diffusion sampling, and rethermalization (honest default: no Q-hops during retherm). Arm A cost per config is 2 tau_int x sec/traj / n_chains, i.e. its marginal equilibrium cost, with burn-in reported separately as the one-time entry fee.

| beta_f | arm | quality (z vs exact) | <Q^2> (exact) | tau_int slowest | s / independent config | one-time cost s |
|---|---|---|---|---|---|---|
| 55.0237 | instanton HMC | max|z|=10.0 | 1.96 +- 0.13 (1.9) | 3.9 | 0.036 | 27 (burn-in) |
| 55.0237 | diffusion | pass | 2.06 +- 0.27 (1.9) | n/a (independent draws) | 8.558 | 0 (amortized in per-config) |
| 218.58 | instanton HMC | max|z|=24.8 | 0.457 +- 0.014 (0.474) | 3.3 | 0.060 | 53 (burn-in) |
| 218.58 | diffusion | pass | 0.51 +- 0.089 (0.474) | n/a (independent draws) | 9.529 | 0 (amortized in per-config) |

Notes. (1) Diffusion configs are conditionally independent given the coarse ensemble; residual correlation enters only through the thinned coarse HMC chains. (2) Instanton-HMC tau_int is per-observable Madras-Sokal on per-chain series, discarding the first 25%; its Q mixing is genuine (tunnelings counted), unlike the pipeline's structurally transported sector. (3) Quality threshold |z| <= 2.5. (4) The diffusion per-config cost amortizes the coarse base over the batch; scaling the batch up lowers it further, while the HMC interval cost is irreducible per config.

Settings: chains=16, burn-in=400, production=320 traj, n_gen=96, seed=20260731, checkpoint=out/u1_2d/checkpoints/score_net.pt.