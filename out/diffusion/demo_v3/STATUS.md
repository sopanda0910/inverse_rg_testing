# v3 run status (launched 2026-07-15 19:29)

Detached chain (survives closing VSCode) — watch progress with:

```powershell
Get-Content out\diffusion\demo_v3\run.log -Tail 20 -Wait
```

Stages (sentinels in run.log):

1. `STAGE_DATA` — generate new training rungs: L=8 at beta {1, 2}, L=32 at
   beta {2, 4, 6.5, 14.1464, 55.0237}; the 8 existing L=16 rungs are reused.
2. `STAGE_TRAIN` — retrain score net on all 15 rungs with the new
   soft-topological-charge penalty (`train.topo_weight: 0.1` in
   `diffusion/configs/demo_v3.yaml`).
3. `STAGE_STUDY` — full 20-case generalization study with the new checkpoint,
   output in `out/diffusion/demo/generalization_v3/` (HMC bases/references
   reused from v2 caches).
4. `STAGE_FIGURES` — scaling figures for the v3 study dir.

`CHAIN_DONE` = success, `CHAIN_FAILED` = a stage exited nonzero (log has the traceback).

Rough timeline: data ~0.5-1 h, training ~2 h, study ~6 h (C_L128 dominates) — done
roughly 9-10 h after launch, i.e. early morning 2026-07-16.

Compare against v2: `out/diffusion/demo/generalization_v2/summary_tables.md`
(watch Q^2 / chi_top z-scores, A_bc2 crossover, C_L128 KS columns, D_bc55 charge count).
