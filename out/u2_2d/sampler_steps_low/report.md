# How many sampler steps does the lift need?

Base L = 16, beta = 28; 512 configurations up the full schedule 105.651 -> 416.524.

The pre-rethermalization column is the measurement. The post column is
repaired by local sweeps and will look healthy past the point where the
model stopped working; <Q^2> is imposed by `apply_coarse_charge` and
cannot degrade at all.

| steps | top-rung s | s/config | vs hmc+winding | rel err (pre) | rel err (post) | <Q^2> |
|---|---|---|---|---|---|---|
| 8 | 42.6 | 0.0833 | 0.39x | -1.02e-02 | -6.35e-06 | 1.0293 |
| 12 | 46.1 | 0.0900 | 0.42x | -1.84e-03 | -3.89e-06 | 1.0273 |
| 18 | 52.9 | 0.1032 | 0.49x | -1.14e-04 | -2.09e-06 | 1.0273 |
