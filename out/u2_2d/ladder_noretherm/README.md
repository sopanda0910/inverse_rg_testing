# CURRENT: the ladder of the deployed pipeline

Built 2026-10-04 from `u2_2d/configs/default_noretherm.yaml`, with no local
repair tail -- the lift is handed to HMC as the model produces it, and local
repair is charged downstream in trajectories.

The superseded `out/u2_2d/ladder/` was built 2026-08-20 with
`n_retherm_sweeps: 10` and is kept only as the record of that earlier pipeline;
see its own README.

Caveat worth knowing: most scripts still default to
`--config u2_2d/configs/default.yaml`, which points at the SUPERSEDED
directory. Pass `--config u2_2d/configs/default_noretherm.yaml` (or an explicit
`--ladder-dir`) for anything that should reflect the current pipeline.
