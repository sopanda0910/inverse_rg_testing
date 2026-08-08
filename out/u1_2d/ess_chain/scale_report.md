# Capacity/data scale-up report

hidden 56->80, depth 4->5, +24 L=32 rungs; all verifications are
fresh-seed script-19 runs (n = 64, sigma-min-coef 0.03).

| variant | case | ESS/N (fiber) | log-w std (fiber) | i-MH acc |
|---------|------|---------------|-------------------|----------|
| multi-case RKL, small net (rkl2) | 16:14.1464 | 0.0156 | 19.15 | 0.03 |
| multi-case RKL, small net (rkl2) | 16:55.0237 | 0.0156 | 18.32 | 0.14 |
| multi-case RKL, small net (rkl2) | 32:55.0237 | 0.0164 | 53.87 | 0.05 |
| multi-case RKL, small net (rkl2) | 32:218.58 | 0.0156 | 127.77 | 0.14 |
| big net, DSM only | 16:14.1464 | 0.0167 | 14.98 | 0.05 |
| big net, DSM only | 16:55.0237 | 0.0158 | 32.74 | 0.03 |
| big net, DSM only | 32:55.0237 | 0.0262 | 56.90 | 0.03 |
| big net, DSM only | 32:218.58 | 0.0156 | 153.67 | 0.05 |
| big net + multi-case RKL | 16:14.1464 | 0.0185 | 16.19 | 0.08 |
| big net + multi-case RKL | 16:55.0237 | 0.0156 | 23.10 | 0.03 |
| big net + multi-case RKL | 32:55.0237 | 0.0167 | 42.15 | 0.06 |
| big net + multi-case RKL | 32:218.58 | 0.0156 | 231.13 | 0.05 |