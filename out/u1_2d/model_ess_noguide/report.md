# Model ESS via probability-flow ODE likelihood

| L | beta_f | ESS/N (fiber) | log-w std (fiber) | ESS/N (joint) | n | gen s | ODE s |
|---|--------|---------------|-------------------|---------------|---|-------|-------|
| 16 | 14.1464 | 0.019 | 28.84 | 0.018 | 64 | 179.7 | 179.3 |
| 16 | 55.0237 | 0.021 | 46.75 | 0.016 | 64 | 165.2 | 148.0 |
| 32 | 55.0237 | 0.016 | 83.58 | 0.016 | 64 | 915.1 | 645.0 |
| 32 | 218.58 | 0.016 | 66.58 | 0.016 | 64 | 611.7 | 622.0 |

Raw model transport (no charge enforcement, no retherm).
The FIBER column divides out the coarse level's density via the
matched-coupling Wilson action (the project's MLE approximation of the
blocked action) -- the per-level quantity multilevel-flow papers report;
compare it against Q-shift flows' ESS/N ~ 0.5-0.7 (Lattice 2026).
The JOINT column keeps the full coarse-fiber mass in the weights and is
~1/N even for a perfect conditional model; it is reported for
completeness, not comparison.