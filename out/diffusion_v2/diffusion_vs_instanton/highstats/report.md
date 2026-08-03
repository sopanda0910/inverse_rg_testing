# Diffusion pipeline vs instanton HMC

Instanton HMC (global Q-hop Metropolis move, dS ~ 2 pi^2 beta / V -- the uniform Q-shift of Albandea-style topology moves) is the strongest classical baseline this project has: it keeps tunneling to beta = 256 where standard HMC froze at beta = 16 (script 13). The question here is whether the diffusion ladder still wins against *it* on wall-clock cost per independent configuration while matching exact observables.

Arm B cost includes everything: matched-coarse HMC base (with Q-hops), conditional diffusion sampling, and rethermalization (honest default: no Q-hops during retherm). Arm A cost per config is 2 tau_int x sec/traj / n_chains, i.e. its marginal equilibrium cost, with burn-in reported separately as the one-time entry fee.

| beta_f | arm | quality (z vs exact) | <Q^2> (exact) | tau_int slowest | s / independent config | one-time cost s |
|---|---|---|---|---|---|---|
| 55.0237 | instanton HMC | max|z|=3.8 | 0.475 +- 0.0078 (0.474) | 7.5 | 0.080 | 372 (burn-in) |
| 55.0237 | diffusion | pass | 0.461 +- 0.03 (0.474) | n/a (independent draws) | 8.299 | 0 (amortized in per-config) |
| 118.5 | instanton HMC | pass | 0.176 +- 0.005 (0.171) | 4.7 | 0.070 | 808 (burn-in) |
| 118.5 | diffusion | pass | 0.146 +- 0.016 (0.171) | n/a (independent draws) | 9.775 | 0 (amortized in per-config) |
| 218.58 | instanton HMC | max|z|=7.9 | 0.0303 +- 0.002 (0.029) | 7.4 | 0.210 | 878 (burn-in) |
| 218.58 | diffusion | pass | 0.0234 +- 0.0067 (0.029) | n/a (independent draws) | 9.880 | 0 (amortized in per-config) |

Notes. (1) Diffusion configs are conditionally independent given the coarse ensemble; residual correlation enters only through the thinned coarse HMC chains. (2) Instanton-HMC tau_int is per-observable Madras-Sokal on per-chain series, discarding the first 25%; its Q mixing is genuine (tunnelings counted), unlike the pipeline's structurally transported sector. (3) Quality threshold |z| <= 2.5. (4) The diffusion per-config cost amortizes the coarse base over the batch; scaling the batch up lowers it further, while the HMC interval cost is irreducible per config.

Settings: chains=32, burn-in=2000, production=640 traj, n_gen=512, seed=20260731, checkpoint=out/diffusion_v2/v2/checkpoints/score_net.pt.