# u2 thermalization and autocorrelation, all rounds (2026-08-24)

`u2_2d/scripts/50_therm_autocorr.py`, 300 trajectories, 64 chains,
`n_retherm = 0` (the ladder's ten sweeps saturate `t_therm` at 0 for every arm
and destroy the comparison's resolution -- `17`'s own docstring records the
trap). `diffusion_tuned` is the learned lift put through the identical
`tune_smear` procedure `smear` gets, so the pair differs only in the lift.

| round | arm | t_therm plaq | t_therm W4x4 | tau_int plaq | tau_int Q^2 | flips | sigma(tail)/exact | sweeps |
|---|---|---|---|---|---|---|---|---|
| L=32 no winding | diffusion_raw | 6 | 0 | 2.70 | inf | 0 | 1.01 | -- |
| L=32 no winding | **diffusion_tuned** | **0** | 0 | 2.67 | inf | 0 | 0.99 | 20 |
| L=32 no winding | **smear** | **0** | 0 | 2.60 | inf | 0 | 1.00 | 10 |
| L=32 no winding | cold | 183 | 152 | 3.11 | inf | 0 | 0.99 | -- |
| L=32 winding | diffusion_raw | 5 | 4 | 2.08 | 3.99 | 2262 | 0.99 | -- |
| L=32 winding | smear | 0 | 0 | 2.09 | 4.21 | 2294 | 1.01 | 10 |
| L=32 winding | cold | 189 | 97 | 2.15 | 4.79 | 2298 | 0.98 | -- |
| L=64 no winding | diffusion_raw | 70 | 0 | 4.81 | inf | 0 | 1.00 | -- |
| L=64 no winding | **diffusion_tuned** | **0** | 0 | 5.27 | inf | 0 | 1.01 | 15 |
| L=64 no winding | **smear** | **0** | 0 | 4.96 | inf | 0 | 1.00 | 15 |
| L=64 winding | diffusion_raw | 20 | 0 | 3.24 | 3.78 | 2358 | 0.99 | -- |
| L=64 winding | smear | 0 | 0 | 3.23 | 4.66 | 2332 | 0.99 | 15 |
| L=64 winding | cold | > 300 | > 300 | 3.29 | 4.73 | 2287 | 0.98 | -- |

A matched supplement at L = 64 with winding gives `diffusion_tuned` t_therm = 0
against `smear`'s 0 -- tied there too.

## Five readings

**1. The learned lift shows NO thermalization advantage at either volume.**
`diffusion_tuned` and `smear` are 0 against 0, at both volumes and with and
without the winding move. Combined with the calibrated `t_therm` floor of 3-4,
NARRATIVE's "0-1 trajectories against 5-6" is not a measurement.

**2. `tau_int` cannot discriminate starting points at all.** It is identical to
~1% across every arm INCLUDING `cold` -- 2.6-3.1 at L = 32, 3.2-5.3 at L = 64.
Autocorrelation is a property of the sampler, not of where the chain started, so
any seeding claim must rest on `t_therm`. Note `cold`'s tau_int is meaningless
where its `t_therm` shows the tail never equilibrated.

**3. The raw lift is already right in the INFRARED.** `diffusion_raw` needs 6
(L=32) and 70 (L=64) trajectories at the plaquette but **0 at W(4x4) at both
volumes**. The model's error is ultraviolet, which is exactly what cheap local
sweeps repair -- the division-of-labour result seen from a new direction.

**4. The freezing contrast, measured rather than asserted.** With no winding
move: `tau_int(Q^2) = inf` and **0** parity flips, every arm. With it: 3.78-4.79
and ~2300 flips. A frozen chain returns `inf` rather than being dropped from the
chain average, which is the coding form of the standing warning that
`tau_int(Q^2)` reports healthy on a parity-frozen chain.

**5. `cold` with a perfect topological move still fails.** At L = 64 it makes
2287 parity flips and never thermalizes locally in 300 trajectories.
**Topological ergodicity does not buy local thermalization** -- reproduced here
at beta = 416.5, and a reminder that a tau_int(Q^2) table alone would rate all
three arms interchangeable while one of them is unusable.

## The tuned sweep count is NOT a stable discriminator

NARRATIVE reports "5 tuned sweeps against 35 and 15". Measured here:

| where | diffusion_tuned | smear |
|---|---|---|
| L = 32 | **20** | **10** |
| L = 64 | 15 | 15 |
| L = 64, seed 0 (`52_`) | 15 | 35 |

The L = 32 row runs the OPPOSITE way to the claim, L = 64 ties, and an
independent seed at L = 64 reproduces the claimed ~3x. `tune_smear` is a
first-passage time on a stochastic quantity, quantized to multiples of
`check_every = 5`, so it has a heavy right tail by construction. **Quote it with
a spread from `52_tuned_sweep_stability.py` or not at all.**

## Caveat on both tuned arms

`tune_smear` stops when the plaquette crosses its EXACT value, so both arms are
tuned against the closed form -- an oracle no 4D SU(3) user has. It is the
conservative choice (it gives the classical arm its best shot rather than a
strawman) but the sweep counts are a lower bound on what either arm needs in
practice.
