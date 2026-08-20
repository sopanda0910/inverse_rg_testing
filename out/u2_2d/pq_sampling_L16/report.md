# Sampling P(Q): L = 16

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.

| beta | beta/V | <Q^2> | exact | z | changes | frozen | chi2/dof | odd/exact | z_odd | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 28 | 0.1094 | 1.0088 +- 0.0110 | 1.0012 | +0.69 | 22260 | 0% | 0.27 | 1.030 | +0.69 | SAMPLED |
| 51.75 | 0.2021 | 0.5746 +- 0.0265 | 0.5211 | +2.02 | 14455 | 0% | 2.89 | 1.152 | +2.89 | PARITY-FROZEN |
| 56 | 0.2188 | 0.5331 +- 0.0274 | 0.4793 | +1.96 | 13531 | 0% | 2.72 | 1.152 | +2.82 | PARITY-FROZEN |

Coldest coupling with honestly sampled topology: **beta = 28** at L = 16.
