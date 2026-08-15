# Surrogate held-out fit quality vs fit-set size

Floor = sqrt(1 - R2_heldout) * std_before. n_fit = 48 is what the
AIS results of record used.

## 32:55.0237  (std_before 36.0)

| basis | n_fit | R2 in-sample | R2 held-out | implied floor |
|---|---|---|---|---|
| final7 | 24 | 0.636 | +0.492 | 25.7 |
| final7 | 48 | 0.740 | +0.537 | 24.5 |
| final7 | 96 | 0.659 | +0.626 | 22.0 |
| final7 | 192 | 0.700 | +0.632 | 21.8 |
| rich11 | 24 | 0.691 | +0.539 | 24.5 |
| rich11 | 48 | 0.745 | +0.572 | 23.6 |
| rich11 | 96 | 0.675 | +0.613 | 22.4 |
| rich11 | 192 | 0.711 | +0.617 | 22.3 |
