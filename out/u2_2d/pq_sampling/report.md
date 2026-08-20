# Sampling P(Q): L = 8

Unseeded HMC + winding update. Errors bootstrap over CHAINS, so a
frozen chain counts as one independent charge however long it ran.

| beta | <Q^2> | exact | z | changes | frozen | chi2/dof | tau_int | verdict |
|---|---|---|---|---|---|---|---|---|
| 6 | 1.8799 +- 0.0178 | 1.8674 | +0.70 | 15153 | 0% | 0.00 | 0.5 | SAMPLED |
| 8 | 1.1973 +- 0.0120 | 1.2007 | -0.28 | 13956 | 0% | 0.00 | 0.5 | SAMPLED |
| 10 | 0.8533 +- 0.0087 | 0.8603 | -0.80 | 10620 | 0% | 0.00 | 0.6 | SAMPLED |
| 12 | 0.6655 +- 0.0105 | 0.6707 | -0.50 | 7065 | 0% | 0.00 | 1.0 | SAMPLED |
| 14 | 0.5547 +- 0.0209 | 0.5514 | +0.16 | 5263 | 0% | 0.01 | 2.9 | SAMPLED |
| 20 | 0.5775 +- 0.0426 | 0.3551 | +5.22 | 5502 | 17% | 5.84 | 0.9 | DISAGREES |

Coldest coupling with honestly sampled topology: **beta = 14** at L = 8.
