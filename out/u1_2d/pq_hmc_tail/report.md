# P(Q): transported batch vs after an instanton-HMC tail

The pipeline's product is a starting batch for HMC. Structural charge
transport delivers the coarse base's empirical sector histogram;
a fixed 200-trajectory HMC continuation WITH the instanton Q-hop
re-equilibrates sectors toward the exact P(Q) at the target coupling
(the hop's dS ~ 2 pi^2 beta / V keeps acceptance finite at all couplings
studied). Adaptive stopping: chi^2 p >= 0.05 vs exact P(Q) (where
testable) and ensemble <Q^2> within tolerance of exact, on two
consecutive checks. chi^2 p-values are against the exact finite-volume
P(Q).

| case | L | beta_f | Q^2 before | after | exact | chi2 p before | after | traj | converged | tail s |
|---|---|---|---|---|---|---|---|---|---|---|
| B_bt6 | 32 | 6 | 1.88 | 4.92 | 4.78 | 0.000 | 0.380 | 200 | yes | 7 |
| A_bc1.5 | 32 | 4.44493 | 7.83 | 7.04 | 6.79 | 0.511 | 0.862 | 200 | yes | 5 |
| E_bc11.8 | 32 | 45.6238 | 0.57 | 0.461 | 0.575 | 0.911 | 0.096 | 200 | yes | 13 |
| D_bc55.0237 | 32 | 218.58 | 0.0156 | 0.0312 | 0.029 | -- | -- | 200 | yes | 28 |
| C_L64 | 64 | 14.1464 | 6.22 | 7.42 | 7.62 | 0.244 | 0.998 | 200 | yes | 7 |