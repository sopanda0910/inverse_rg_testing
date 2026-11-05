# SUPERSEDED: this ladder carries the local repair tail

Built 2026-08-20 from `u2_2d/configs/default.yaml` with
`ladder.n_retherm_sweeps: 10`, i.e. each rung ended with ten sweeps of heatbath
plus overrelaxation on both sectors.

That tail was removed from `generate_ladder` afterwards, on the grounds that it
made each rung's agreement a mixture of what the model produced and what cheap
exact local updates then repaired, not separable from outside and large. The
parameters were removed rather than defaulted to zero so no caller can pass
them, and `03_run_ladder.py` refuses a config that still asks for them.

`summary.json` shows the tail directly: `plaquette` 0.9810292720794678 against
`plaquette_pre_retherm` 0.9811232089996338 at L = 32, and 0.9951967597007751
against 0.9952598810195923 at L = 64.

**The current ladder is `out/u2_2d/ladder_noretherm/`**, built 2026-10-04 from
`u2_2d/configs/default_noretherm.yaml`.

Results produced with the tail are not comparable with results produced without
it. Do not mix numbers from the two directories in one table or figure.
