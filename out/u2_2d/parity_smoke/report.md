# Parity transport: sampled at the base, or frozen in and lucky?

## Measured

| ladder | | $L$ | $\beta$ | $n$ | $P({\rm odd})$ | exact | $z$ | $\langle Q^2\rangle$ | exact | $\chi^2$ $p$ |
|---|---|---|---|---|---|---|---|---|---|---|
| - | base | 16 | 14 | 1024 | 0.6025 | 0.5000 | $+6.56$ | 2.4072 | 2.2074 | 0.000 |
| - | base | 16 | 28 | 4096 | 0.5117 | 0.4928 | $+2.42$ | 0.9668 | 1.0012 | 0.069 |
| ladder | rung | 32 | 105.651 | 1024 | 0.5117 | 0.4928 | $+1.21$ | 1.0156 | 1.0012 | 0.723 |
| ladder | rung | 64 | 416.524 | 1024 | 0.5117 | 0.4929 | $+1.21$ | 1.0156 | 1.0012 | 0.723 |

The `ladder_mobile` rows are the positive control: their base ($L = 16$, $\beta = 14$) records 2453 parity flips in stage 15, so its odd/even weight is genuinely **sampled** rather than frozen in at ordering. If sector transport is the identity the design claims, every rung above it must reproduce exact $P({\rm odd})$ -- and the ladder of record, whose base has zero flips, must agree with it.

## Where the frozen-in argument would fail

The defence in section 12.2 is conditional: a frozen-in weight lands near $1/2$, and exact $P({\rm odd})$ is near $1/2$ only while $\langle Q^2\rangle \gtrsim 1$. Below that the two part company, and the quench is simply wrong.

| $L$ | $\beta$ | exact $\langle Q^2\rangle$ | exact $P({\rm odd})$ | error of assuming $1/2$ |
|---|---|---|---|---|
| 8 | 6 | 1.8674 | 0.4999 | $+0.0001$ |
| 8 | 10 | 0.8603 | 0.4854 | $+0.0146$ |
| 8 | 14 | 0.5514 | 0.4341 | $+0.0659$ |
| 8 | 20 | 0.3551 | 0.3335 | $+0.1665$ |
| 8 | 28 | 0.2154 | 0.2133 | $+0.2867$ |
| 16 | 14 | 2.2074 | 0.5000 | $+0.0000$ |
| 16 | 21 | 1.3748 | 0.4989 | $+0.0011$ |
| 16 | 28 | 1.0012 | 0.4928 | $+0.0072$ |
| 16 | 56 | 0.4793 | 0.4067 | $+0.0933$ |

Read the two columns together. Wherever $\langle Q^2\rangle \gtrsim 1$ the error of assuming $1/2$ is under a percent and a hot quench is safe; where $\langle Q^2\rangle$ falls well below 1 it is not. The measured case is $L = 8$, $\beta = 20$: exact $P({\rm odd}) = 0.3335$, hot quench $0.5156$, wrong by $+55\%$. **State the condition, not just the conclusion** -- a base with a narrow $P(Q)$ would fail this badly, and the ladder base is safe because it satisfies the condition, not because quenching samples parity.

Source: `u2_2d/scripts/19_parity_transport.py`.
