# Model ESS via probability-flow ODE likelihood

| L | beta_f | ESS/N (fiber) | log-w std (fiber) | ESS/N (joint) | n | gen s | ODE s |
|---|--------|---------------|-------------------|---------------|---|-------|-------|
| 16 | 14.1464 | 0.018 | 45.31 | 0.016 | 64 | 27.4 | 32.0 |
| 16 | 55.0237 | 0.016 | 41.51 | 0.027 | 64 | 27.0 | 30.6 |
| 32 | 55.0237 | 0.016 | 62.38 | 0.016 | 64 | 28.4 | 32.3 |
| 32 | 218.58 | 0.016 | 114.50 | 0.016 | 64 | 27.3 | 29.7 |

Raw model transport (no charge enforcement, no retherm).
The FIBER column divides out the coarse level's density via the
matched-coupling Wilson action (the project's MLE approximation of the
blocked action) -- the per-level quantity multilevel-flow papers report;
compare it against Q-shift flows' ESS/N ~ 0.5-0.7 (Lattice 2026).
The JOINT column keeps the full coarse-fiber mass in the weights and is
~1/N even for a perfect conditional model; it is reported for
completeness, not comparison.