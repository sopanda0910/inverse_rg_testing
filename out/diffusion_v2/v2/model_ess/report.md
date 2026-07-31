# Model ESS via probability-flow ODE likelihood

| L | beta_f | ESS/N (fiber) | log-w std (fiber) | ESS/N (joint) | n | gen s | ODE s |
|---|--------|---------------|-------------------|---------------|---|-------|-------|
| 16 | 14.1464 | 0.016 | 39.82 | 0.016 | 64 | 102.9 | 69.4 |
| 16 | 55.0237 | 0.016 | 40.03 | 0.016 | 64 | 68.3 | 92.4 |
| 32 | 55.0237 | 0.016 | 72.13 | 0.016 | 64 | 336.5 | 187.5 |
| 32 | 218.58 | 0.016 | 152.08 | 0.016 | 64 | 231.1 | 212.0 |

Raw model transport (no charge enforcement, no retherm).
The FIBER column divides out the coarse level's density via the
matched-coupling Wilson action (the project's MLE approximation of the
blocked action) -- the per-level quantity multilevel-flow papers report;
compare it against Q-shift flows' ESS/N ~ 0.5-0.7 (Lattice 2026).
The JOINT column keeps the full coarse-fiber mass in the weights and is
~1/N even for a perfect conditional model; it is reported for
completeness, not comparison.