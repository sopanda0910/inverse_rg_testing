# Tier-0 proposal sweep (case 16:55.0237, n=64)

| point | ESS/N (fiber) | log-w std (fiber) | i-MH acc | ODE s |
|-------|---------------|-------------------|----------|-------|
| cw2 | 0.0361 | 37.37 | 0.03 | 114 |
| cw0.5 | 0.0340 | 31.00 | 0.08 | 113 |
| sigmin0.01 | 0.0282 | 41.67 | 0.11 | 112 |
| probes8 | 0.0242 | 35.27 | 0.08 | 340 |
| baseline | 0.0171 | 35.11 | 0.10 | 113 |
| sigmin0.03 | 0.0171 | 35.11 | 0.10 | 112 |
| blend2 | 0.0167 | 52.57 | 0.05 | 110 |
| sigmin0.03_blend2 | 0.0167 | 52.57 | 0.05 | 120 |
| sigmin0.01_blend4 | 0.0156 | 100.52 | 0.06 | 116 |
| blend4 | 0.0156 | 100.37 | 0.05 | 112 |
| steps240 | 0.0156 | 35.39 | 0.06 | 176 |
| cw0 | 0.0156 | 41.40 | 0.03 | 106 |
| sigmin0.03_blend4_cw0.5 | 0.0156 | 90.53 | 0.08 | 118 |

probes8 / steps240 are stability points at baseline knobs: if their
log-w std drops materially below baseline, the spread was partly
estimator noise (Hutchinson / discretization), not model density gap.