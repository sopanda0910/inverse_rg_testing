# SUPERSEDED — topology-matched U(1) ladder at a 192-configuration base

This is the first run of the `<Q^2>`-matched U(1) schedule
(`configs/v2_topomatched.yaml`: 3.9174, 13.5864, 52.7535), completed
2026-09-23. It is kept only as the record that the schedule validates. **Do not
quote its topology numbers.**

It established what it was built to establish: topology matching holds the exact
`<Q^2>` at **1.986 on all three rungs** instead of letting it drift
1.934 -> 1.904 -> 1.903 as the deployed plaquette-matched schedule does. Worst
Wilson `|z|` was 1.11 / 2.86 / 1.77, comparable to the deployed ladder's
2.06 / 1.38 / 1.28.

What it could not settle is the topology number itself:

    measured <Q^2> = 1.688 +- 0.201   against exact 1.986   ->   z = -1.49

Because sector transport is exact, every rung reports the *identical* measured
value, so that number is entirely a property of the base draw — 192
configurations at L=8, beta=1.3472, whose independent-sample SEM is ~0.20.
Nothing in the model, the sampler or the ladder can move it, and 1.49 sigma on
the headline topological observable is not publishable when the only available
explanation is the base size.

Superseded by the same config at `n_base_configs: 2048` (SEM ~0.058, a 3.3x
tightening), written to `out/u1_2d/validation_topomatched/`. If that run confirms
the central value near exact, the schedule is promoted into the paper and the
U(1) ladder becomes topology-matched like the U(2) one; if the central value
holds near 1.69 with the tighter error, that is a real finding about the base
ensemble rather than noise — note that `z ~ sqrt(N)`, so more statistics makes a
genuine bias *more* visible, not less.

`status_n192.log` is the wrapper's status log for this run.
