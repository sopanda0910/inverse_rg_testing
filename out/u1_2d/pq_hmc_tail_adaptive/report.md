# P(Q): transported batch vs after an instanton-HMC tail

The pipeline's product is a starting batch for HMC. Structural charge
transport delivers the coarse base's empirical sector histogram;
an adaptive (cap 2000, checked every 50) HMC continuation WITH the instanton Q-hop
re-equilibrates sectors toward the exact P(Q) at the target coupling
(the hop's dS ~ 2 pi^2 beta / V keeps acceptance finite at all couplings
studied). Adaptive stopping: chi^2 p >= 0.05 vs exact P(Q) (where
testable) and ensemble <Q^2> within tolerance of exact, on two
consecutive checks. chi^2 p-values are against the exact finite-volume
P(Q).

| case | L | beta_f | Q^2 before | after | exact | chi2 p before | after | traj | converged | tail s |
|---|---|---|---|---|---|---|---|---|---|---|
| B_bt6 | 32 | 6 | 1.88 | 5.77 | 4.78 | 0.000 | 0.276 | 150 | yes | 19 |
| A_bc1.5 | 32 | 4.44493 | 7.83 | 8.2 | 6.79 | 0.511 | 0.360 | 150 | yes | 15 |
| E_bc11.8 | 32 | 45.6238 | 0.57 | 0.492 | 0.575 | 0.911 | 0.754 | 150 | yes | 40 |
| D_bc55.0237 | 32 | 218.58 | 0.0156 | 0.0391 | 0.029 | -- | -- | 200 | yes | 134 |
| C_L64 | 64 | 14.1464 | 6.22 | 10.2 | 7.62 | 0.244 | 0.830 | 200 | yes | 108 |