# P(Q): transported batch vs after an instanton-HMC tail

The pipeline's product is a starting batch for HMC. Structural charge
transport delivers the coarse base's empirical sector histogram; a
continuation of 200 HMC trajectories WITH the instanton Q-hop
re-equilibrates sectors toward the exact P(Q) at the target coupling
(the hop's dS ~ 2 pi^2 beta / V keeps acceptance finite at all couplings
studied). chi^2 p-values are against the exact finite-volume P(Q).

| case | L | beta_f | Q^2 before | after | exact | chi2 p before | after | tail s |
|---|---|---|---|---|---|---|---|---|
| B_bt6 | 32 | 6 | 1.92 | 5.2 | 4.78 | 0.001 | 0.386 | 6 |
| A_bc1.5 | 32 | 4.44493 | 5.1 | 6.88 | 6.79 | 0.872 | 0.237 | 6 |
| E_bc11.8 | 32 | 45.6238 | 0.438 | 0.539 | 0.575 | 0.313 | 0.964 | 16 |
| D_bc55.0237 | 32 | 218.58 | 0.0312 | 0.0391 | 0.029 | -- | -- | 41 |
| C_L64 | 64 | 14.1464 | 6.43 | 10.4 | 7.62 | 0.066 | 0.697 | 19 |