# CPU data-generation tasks for a second machine (2018 Mac Mini)

Written 2026-09-03 for an agent running on a 2018 Mac Mini (Intel, no CUDA —
CPU-only, same class of machine as the "Snapdragon X Elite, CPU-only" recipe
in `CLAUDE.md`). Both tasks below are pure HMC data generation: no training,
no diffusion sampling, no GPU dependency. Do not attempt `02_train.py`,
`03_run_ladder.py`, or anything that loads a `.pt` checkpoint and samples from
it — those are GPU-bound stages on the primary (Windows) machine and are
already running there. This machine's job is strictly to produce new raw HMC
ensembles in the background while that GPU work runs elsewhere.

Read `CLAUDE.md` in the repo root first — it is the project's single source
of truth for conventions, and this file assumes you have it loaded. In
particular: **u1_2d and u2_2d must be evaluated/generated with the same
method and no unjustified deviation from what the Windows machine's config
files already establish** — do not improvise a different recipe than what is
specified below without a documented reason.

## Setup

```bash
# clone or pull
git clone https://github.com/sopanda0910/inverse_rg_testing
cd inverse_rg_testing
# (or: git pull, if already cloned)

python3 -m venv .venv
source .venv/bin/activate
pip install torch           # CPU wheel is the default on macOS, no CUDA index needed
pip install -e ".[dev]"
```

Check physical core count and use that many shards, one thread each — this
project's own measurements (`CLAUDE.md`, "Parallelism" section) show
threads-within-one-process do NOT help for this workload (stage 01 measured
154 sweeps/s on 1 thread, 142 on 8, 91 on 12) — the win is concurrent
single-threaded processes, one per physical core:

```bash
sysctl -n hw.physicalcpu   # use this number as N below
export U2_2D_TORCH_THREADS=1
export U1_2D_TORCH_THREADS=1
```

## Task 1 (primary): generate u2's missing `random_rungs` data

**Why**: `u2_2d/configs/default.yaml` already specifies a `random_rungs`
block (102 ensembles: 60×L16 + 12×L32 + 6×L8 + 24×L32, β from 4 to 430) —
but per `CLAUDE.md`, the deployed `det_score_net.pt` checkpoint **predates**
that block and was never trained on it; the data for it was never generated.
This is exactly the gap `CLAUDE.md` identifies as the likely reason u2's own
attempt to port u1's coverage-widening recipe (the `v2` checkpoint)
underperformed: u1's generalization is credited partly to training on
*randomly sampled* beta, not just fixed rungs, and u2 has never actually
done this. Producing this data does not commit anyone to retraining on it
immediately — it just removes the blocker for that experiment.

Create `u2_2d/configs/random_rungs_gen.yaml`:

```yaml
seed: 0
device: cpu

data:
  out_dir: out/u2_2d/data_random
  n_chains: 32
  thin: 5
  topological_updates: true
  winding_charge_step: 1
  random_rungs:
    - {n: 60, beta_min: 4.0,  beta_max: 430.0, lattice_size: 16, n_configs: 128}
    - {n: 12, beta_min: 8.0,  beta_max: 430.0, lattice_size: 32, n_configs: 128}
    - {n: 6,  beta_min: 4.0,  beta_max: 60.0,  lattice_size: 8,  n_configs: 128}
    - {n: 24, beta_min: 8.0,  beta_max: 430.0, lattice_size: 32, n_configs: 128}
```

This is copied verbatim from `default.yaml`'s existing block — do not
redesign the coupling ranges or counts; that recipe is already the project's
considered choice, just never executed. `n_chains`/`thin`/
`topological_updates`/`winding_charge_step` are copied from `default.yaml`'s
`data:` section for consistency (check the live file in case it has moved
since this was written).

**Deliberately a separate `out_dir`** (`data_random`, not `data`) — do not
write into `out/u2_2d/data/`, which is the data of record for the currently
deployed checkpoint on the other machine. Keep this generated data isolated
until it's reviewed and explicitly merged into a training config.

Run, sharded across physical cores (replace `8` with your actual
`sysctl -n hw.physicalcpu` count):

```bash
for i in $(seq 0 7); do
  .venv/bin/python u2_2d/scripts/01_generate_data.py \
    --config u2_2d/configs/random_rungs_gen.yaml --shard $i/8 --device cpu &
done
wait
.venv/bin/python u2_2d/scripts/01_generate_data.py \
  --config u2_2d/configs/random_rungs_gen.yaml --merge-shards --out-dir out/u2_2d/data_random
```

This is 102 ensembles at n_configs=128 each — expect this to take a long
time on CPU (hours, plausibly overnight or longer depending on the L=32
rungs, which are the expensive ones per `CLAUDE.md`'s U(2) HMC cost table).
That's fine — this is meant to run unattended in the background.

**Before shipping back**, sanity-check a handful of rungs against the exact
closed form the same way the widening-data checks already do it (see
`u2_2d/scripts/63_widening_test_data_check.py` for the pattern — reuse
`chain_bootstrap` from `u2_2d/scripts/07_pq_sampling.py` and
`u2_2d.lgt.exact.plaquette_exact` / `det_topological_susceptibility`). Flag
anything with |z| > 3, don't silently ship it.

## Task 2 (secondary, quick): fix u1's flagged beta=2000 widening rung

**Why**: `out/u1_2d/data_widening_test/` (config `u1_2d/configs/widening_test.yaml`)
has 7 new rungs, and `u1_2d/scripts/69_widening_test_data_check.py` flagged
the β=2000 rung at z=5.48 on the plaquette — plausible under-thermalization,
since `burn_in` was held flat at 2000 sweeps across all seven rungs rather
than tapered up for the stiffest coupling. The other six rungs are fine.

Create `u1_2d/configs/widening_2000_fix.yaml` — copy
`u1_2d/configs/widening_test.yaml` verbatim but change ONLY the β=2000 rung's
`burn_in` from `2000` to `8000`, and change `out_dir` to
`out/u1_2d/data_widening_2000_fix` (again, isolated — do not overwrite the
existing data until verified).

```bash
.venv/bin/python u1_2d/scripts/01_generate_data.py \
  --config u1_2d/configs/widening_2000_fix.yaml --only-betas 2000 --device cpu
.venv/bin/python u1_2d/scripts/69_widening_test_data_check.py \
  --data-dir out/u1_2d/data_widening_2000_fix
```

Confirm |z| <= 3 before treating it as fixed. If it's still flagged, do not
keep increasing burn_in blindly — report the number back rather than
iterating past 8000 unattended, since a persistent large z at that point
would indicate something other than under-thermalization.

## Shipping data back

`out/**/*.pt` is gitignored (only `out/*/checkpoints/*.pt` is tracked) —
these ensemble files will NOT go through `git push`. Once generated and
verified, transfer `out/u2_2d/data_random/` and (if regenerated)
`out/u1_2d/data_widening_2000_fix/` back to the Windows machine by whatever
means is convenient (AirDrop, a shared network volume, `scp`, USB) — do not
try to force them into git.

## Explicit "do not" list

- Do not run `02_train.py`, `03_run_ladder.py`, `04_validate.py` with
  `generate_reference` sampling from a checkpoint, `05_topology_study.py`,
  or any script that loads a model checkpoint and runs inference/sampling —
  all of that is GPU/diffusion work and belongs on the primary machine.
- Do not run more concurrent shards than physical cores.
- Do not write into `out/u2_2d/data/` or `out/u1_2d/data_wide/` (or any
  existing data directory) — always generate into a new, separate `out_dir`
  and let a human/the other session decide when to merge it in.
- Do not modify `default.yaml`, `wide.yaml`, `wide2000.yaml`, or any config
  already in use by a running job on the other machine.
