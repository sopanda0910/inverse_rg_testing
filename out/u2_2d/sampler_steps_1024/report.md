# How many sampler steps does the lift need?

Base L = 16, beta = 28; 1024 configurations up the full schedule 105.651 -> 416.524.

RUNG 0 is the clean measurement: its input is the fixed HMC base, so its
error is one diffusion lift and nothing else. The top rung lifts rung 0's
output, so its plaquette error is two lifts that partially cancel and it
moves the wrong way across the scan. Extended loops at the top rung are
the other honest column.

The post-rethermalization columns are repaired by 10 local sweeps and stay
healthy long past the point where the model has stopped working -- at 8
steps the lift is 1% off and the sweeps hide all of it.

| steps | top-rung s | s/config | vs hmc+winding | r0 pre | r0 post | r1 pre | top W(8x8) |
|---|---|---|---|---|---|---|---|
| 18 | 78.1 | 0.0763 | 0.36x | +1.72e-04 | +1.72e-04 | -8.97e-05 | -6.43e-02 |
| 25 | 89.9 | 0.0878 | 0.41x | +3.51e-04 | +3.51e-04 | +6.16e-05 | -3.58e-02 |
| 50 | 137.1 | 0.1339 | 0.63x | +2.02e-04 | +2.02e-04 | +7.03e-05 | -1.68e-02 |
| 100 | 238.1 | 0.2325 | 1.10x | +1.44e-04 | +1.44e-04 | +6.31e-05 | -8.34e-03 |
| 200 | 427.9 | 0.4179 | 1.97x | +1.18e-04 | +1.18e-04 | +7.46e-05 | -2.59e-03 |
