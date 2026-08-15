# Model ESS via probability-flow ODE likelihood

| L | beta_f | ESS/N (fiber) | log-w std (fiber) | ESS/N (joint) | n | gen s | ODE s |
|---|--------|---------------|-------------------|---------------|---|-------|-------|
| 32 | 218.58 | 0.002 | 122.62 | 0.002 | 512 | 149.2 | 187.4 |

Raw model transport (no charge enforcement, no retherm).
The FIBER column divides out the coarse level's density via the
matched-coupling Wilson action (the project's MLE approximation of the
blocked action) -- the per-level quantity multilevel-flow papers report;
compare it against Q-shift flows' ESS/N ~ 0.5-0.7 (Lattice 2026).
The JOINT column keeps the full coarse-fiber mass in the weights and is
~1/N even for a perfect conditional model; it is reported for
completeness, not comparison.