# Multiple lifts: what the ladder's rung count actually costs

`u2_2d/scripts/45_multi_lift_compounding.py` and
`u1_2d/scripts/60_multi_lift_compounding.py`, figure
`out/u2_2d/figures/fig30_multi_lift.png`. Eight cells: two theories x two
endpoints (one inside training coverage, one past the ceiling) x two settings of
the rethermalization between rungs. Each cell reaches ONE fixed endpoint by 1, 2
and 3 lifts, so the arms differ only in how many times the model was applied.

## 1. Error does not compound

`|z|` of the raw lift at the endpoint, W(1x1), 3 lifts against 1:

| theory | endpoint | 1 lift | 2 lifts | 3 lifts | ratio |
|---|---|---|---|---|---|
| u1 | beta 52.9, in coverage | 45.5 | 43.4 | 45.4 | 1.00x |
| u1 | beta 75.4, +26% past | 182.5 | 190.4 | 178.8 | 0.98x |
| u2 | model beta 61.7, in coverage | 167.4 | 171.5 | 157.4 | 0.94x |
| u2 | model beta 163.8, +57% past | 244.5 | 231.3 | 248.6 | 1.02x |

Without rethermalization between rungs the same holds (0.84-1.00x). **The rung
count is free.** A ladder may be made as long as the base coupling requires.

## 2. The error is injected by the FINAL lift

Per-rung `|z|` of the 3-lift arm, u2 in-coverage chain:

    rung 1 (L=16, model beta  4.4)   z = +15.80
    rung 2 (L=32, model beta 15.8)   z =  +0.91
    rung 3 (L=64, model beta 61.7)   z = -157.44

The intermediate rungs sit deep inside training coverage and land within a few
sigma; the endpoint does not and lands 157 sigma out. So the endpoint's accuracy
is set by the FINAL rung's distance from coverage, not by the number of rungs
climbed. The same shape appears in all four chains.

**Consequence for generalization, and it is a negative result worth stating.**
Laddering does NOT extend the coupling reach. Every lift multiplies beta by
about four, so the last lift always lands at the same fine model beta whatever
path was taken to it, and that rung's coverage is what binds. What the ladder
buys is VOLUME at fixed coupling coverage -- which is what it was for.

## 3. The lift transports topology exactly; the tail re-samples it

Percentage of configurations still carrying their starting charge after 3 lifts:

| | u1 in cov | u1 past | u2 in cov | u2 past |
|---|---|---|---|---|
| no retherm between rungs | **100%** | **100%** | **100%** | **100%** |
| 10 retherm sweeps between rungs | **33.6%** | 81.2% | 98.4% | 100% |

Read the top row first: **the lift itself is exactly charge-preserving**,
configuration by configuration, at 1, 2 and 3 lifts, in both theories, at both
endpoints. That is the strongest form of the transport claim measured so far --
`36_transport_check.py` established it for a single lift, and it survives
composition.

The bottom row is the new fact. The ladder's own rethermalization sweeps move
the charge, and the loss tracks how weakly coupled the intermediate rung is:
u1's 3-lift arm rethermalizes at L = 16 at beta = 3.87 (in-coverage chain) and
beta = 5.24 (ceiling chain), where instantons are cheap and local heatbath moves
Q freely, so it keeps only 33.6% and 81.2%. u2's intermediate rungs are far
stiffer and it keeps 98.4% and 100%. The 1- and 2-lift arms never rethermalize
at a weakly coupled rung and lose nothing.

**This is re-sampling, not corruption**, and the direction proves it: on the u1
ceiling chain `<Q^2>` goes 1.633 at L = 16 to 1.539 at L = 32 against an exact
1.386 -- the sweeps move it TOWARD the exact value, because a rung weak enough
for local moves to change Q is a rung where local moves sample Q correctly.

**But it means one sentence in the framing has to be stated more carefully.**
"The charge is drawn at the base, where sampling works, and carried unchanged to
the top" is exactly true only with intermediate rethermalization off. As
deployed, the ladder re-samples topology at every rung where that remains valid
and transports it unchanged once the coupling is stiff enough that it does not.
That is a better description of the method than the original sentence, and it is
now measured rather than assumed.

## 4. Caveat on the post-tail numbers

Post-rethermalization `|z|` at the endpoint creeps upward with lift count in the
u2 in-coverage chain (0.63 / 0.83 / 1.86) and the u1 ceiling chain
(0.19 / 0.01 / 2.69). Every value is below 2, so this is not resolved at 64-128
configurations and "no compounding" stands as stated -- but it is monotone in
three of four chains and deserves a larger ensemble before anyone claims the
ladder is free in the delivered product as well as in the raw lift.
