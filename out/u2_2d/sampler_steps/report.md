# How many sampler steps does the lift need?

Base L = 16, beta = 28; 512 configurations up the full schedule 105.651 -> 416.524.

The pre-rethermalization column is the measurement. The post column is
repaired by local sweeps and will look healthy past the point where the
model stopped working; <Q^2> is imposed by `apply_coarse_charge` and
cannot degrade at all.

| steps | top-rung s | s/config | vs hmc+winding | rel err (pre) | rel err (post) | <Q^2> |
|---|---|---|---|---|---|---|
| 25 | 78.6 | 0.1535 | 0.72x | +2.44e-05 | -6.56e-07 | 1.0273 |
| 50 | 85.5 | 0.1670 | 0.79x | +5.31e-05 | -5.74e-08 | 1.0273 |
| 100 | 137.3 | 0.2681 | 1.26x | +4.68e-05 | +1.98e-06 | 1.0273 |
| 200 | 240.8 | 0.4703 | 2.22x | +6.83e-05 | -5.21e-06 | 1.0273 |
| 400 | 448.9 | 0.8768 | 4.13x | +7.53e-05 | -6.56e-07 | 1.0273 |
