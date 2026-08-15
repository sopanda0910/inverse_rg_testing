# Surrogate held-out fit quality vs fit-set size

Floor = sqrt(1 - R2_heldout) * std_before. n_fit = 48 is what the
AIS results of record used.

## 16:14.1464  (std_before 13.1)

| basis | n_fit | R2 in-sample | R2 held-out | implied floor |
|---|---|---|---|---|
| final7 | 24 | 0.754 | +0.438 | 9.9 |
| final7 | 48 | 0.676 | +0.457 | 9.7 |
| final7 | 96 | 0.615 | +0.469 | 9.6 |
| final7 | 192 | 0.562 | +0.488 | 9.4 |
| final7 | 288 | 0.513 | +0.478 | 9.5 |
| final7 | 384 | 0.570 | +0.494 | 9.3 |
| rich11 | 24 | 0.834 | +0.415 | 10.1 |
| rich11 | 48 | 0.647 | +0.465 | 9.6 |
| rich11 | 96 | 0.654 | +0.475 | 9.5 |
| rich11 | 192 | 0.581 | +0.492 | 9.4 |
| rich11 | 288 | 0.533 | +0.480 | 9.5 |
| rich11 | 384 | 0.607 | +0.501 | 9.3 |
