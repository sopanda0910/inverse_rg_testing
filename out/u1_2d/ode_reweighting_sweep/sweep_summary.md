# Tier-0 proposal sweep (case 16:55.0237, n=64)

| point | ESS/N (fiber) | log-w std (fiber) | i-MH acc | ODE s |
|-------|---------------|-------------------|----------|-------|
| sigmin0.03 | 0.0309 | 23.99 | 0.14 | 156 |
| steps240 | 0.0308 | 27.12 | 0.10 | 310 |
| baseline | 0.0304 | 27.48 | 0.13 | 185 |
| cw0.5 | 0.0257 | 31.91 | 0.03 | 153 |
| cw2 | 0.0230 | 38.15 | 0.06 | 163 |
| probes8 | 0.0209 | 27.90 | 0.13 | 541 |
| sigmin0.01 | 0.0197 | 22.37 | 0.11 | 172 |
| cw0 | 0.0157 | 42.44 | 0.03 | 153 |
| sigmin0.03_blend4_cw0.5 | 0.0156 | 87.86 | 0.10 | 178 |
| sigmin0.03_blend2 | 0.0156 | 38.54 | 0.11 | 186 |
| blend2 | 0.0156 | 46.56 | 0.10 | 154 |
| blend4 | 0.0156 | 127.81 | 0.16 | 175 |
| sigmin0.01_blend4 | 0.0156 | 106.21 | 0.14 | 175 |

probes8 / steps240 are stability points at baseline knobs: if their
log-w std drops materially below baseline, the spread was partly
estimator noise (Hutchinson / discretization), not model density gap.