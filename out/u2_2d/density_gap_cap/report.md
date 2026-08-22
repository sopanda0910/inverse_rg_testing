# The determinant lift's density gap, in nats per site

Because the SU(2) conditional is sampled EXACTLY, it is the same distribution on both sides of the KL and cancels identically:

$$\mathrm{KL}\big(m(\psi)\,p(q|\psi)\,\|\,p(\psi)\,p(q|\psi)\big) = \mathrm{KL}\big(m(\psi)\,\|\,p(\psi)\big).$$

So the number below is **the whole pipeline's** density gap, not one sector's -- with no inequality and no residual term.

| case | $L$ | $\beta_f$ | model $\beta$ | KL (nats) | **nats/site** | certificate gap | ESS/$N$ |
|---|---|---|---|---|---|---|---|
| 8:3.5:14 | 16 | 14 | 3.56 | 581.5 $\pm$ 2.2 | **1.136** | -524.85 | 0.0305 |
| 8:7:28 | 16 | 28 | 7.02 | 581.0 $\pm$ 1.7 | **1.135** | -556.23 | 0.0176 |
| 16:28:105.651 | 32 | 105.651 | 26.42 | 2328.1 $\pm$ 2.4 | **1.137** | -2288.82 | 0.0164 |
| 32:105.651:416.524 | 64 | 416.524 | 104.13 | 9327.7 $\pm$ 10.0 | **1.139** | -9235.77 | 0.0298 |

## How to read it

**Read the first row first.** It is the instrument validation: the smallest, most weakly coupled case, comfortably inside the training range. Its certificate gap is -524.85 nats at ESS/$N$ = 0.0305. The `gap` is the certificate and must go to zero as the ESS goes to one; where the ESS has collapsed the log-mean-exp sits near $\max \log w$ and the gap reads roughly $-$KL, which is a diagnostic of weight degeneracy and not a defect of the free energy.

**The KL column is the measurement and survives ESS collapse.** The identity $E[\log w] - \Delta F_{\rm exact} = -\mathrm{KL}$ holds whatever the weights do, so `nats/site` stays quantitative long after `ESS/N` has bottomed out. That is why this replaces ESS as the reported quantity -- a saturated ESS says only "too small to measure".

**Charge projection is absent from the sampler here, deliberately.** It is not a diffeomorphism, so including it would invalidate the density the ODE reports. The configurations priced here are therefore the model's raw output, which is the thing whose density one wants to know.

Source: `u2_2d/scripts/18_density_gap.py`, `u2_2d/model/det_likelihood.py`.
