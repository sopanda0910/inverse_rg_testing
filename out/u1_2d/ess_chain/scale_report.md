# Capacity/data scale-up report

hidden 56->80, depth 4->5, +24 L=32 rungs; all verifications are
fresh-seed script-19 runs (n = 64, sigma-min-coef 0.03).

| variant | case | ESS/N (fiber) | log-w std (fiber) | i-MH acc |
|---------|------|---------------|-------------------|----------|
| multi-case RKL, small net (rkl2) | 16:14.1464 | 0.0161 | 15.06 | 0.10 |
| multi-case RKL, small net (rkl2) | 16:55.0237 | 0.0161 | 19.68 | 0.03 |
| multi-case RKL, small net (rkl2) | 32:55.0237 | 0.0156 | 40.76 | 0.06 |
| multi-case RKL, small net (rkl2) | 32:218.58 | 0.0156 | 102.63 | 0.10 |
| big net, DSM only | 16:14.1464 | 0.0207 | 19.72 | 0.08 |
| big net, DSM only | 16:55.0237 | 0.0156 | 31.59 | 0.05 |
| big net, DSM only | 32:55.0237 | 0.0158 | 49.59 | 0.11 |
| big net, DSM only | 32:218.58 | 0.0156 | 211.85 | 0.03 |
| big net + multi-case RKL | -- | -- | -- | -- |