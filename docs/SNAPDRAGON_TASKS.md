# CPU data-generation task for the Snapdragon X Elite machine

Written 2026-09-03 for an agent running on the Snapdragon X Elite laptop
(ARM64, Windows, CPU-only). **This machine has a documented, real failure
history — read this before running anything.**

## Hard constraint: no parallelism, ever

Per `CLAUDE.md`'s "Compute (this machine)" section, historical note for this
exact laptop: **priority elevation + parallel worker processes hard-crashed
this machine twice** on 2026-07-24. Unlike the Mac Mini brief
(`docs/MAC_MINI_TASKS.md`), which shards data generation across physical
cores with concurrent processes, **do NOT do that here**. This machine gets
exactly one thing:

```powershell
$env:U1_2D_TORCH_THREADS = "8"
```

as a single-process thread ceiling, and nothing else. No background `&`
jobs, no `--shard` fan-out, no elevated/high-priority process launch. Leave
Windows' EcoQoS power setting as-is — do not touch it. If in doubt, run
fewer things sequentially rather than more things concurrently.

Do not run `02_train.py`, `03_run_ladder.py`, or anything that loads a
`.pt` checkpoint and samples from it — GPU-bound work belongs on the
Windows machine with the RTX 5060, not here.

## Setup

```powershell
git clone https://github.com/sopanda0910/inverse_rg_testing
cd inverse_rg_testing
python -m venv .venv
.venv\Scripts\pip install torch
.venv\Scripts\pip install -e ".[dev]"
```

## Task: extend u1's random-beta coverage to match its new fixed-rung range

**Why**: `u1_2d/configs/wide2000.yaml` (already trained tonight on the
Windows machine, checkpoint `score_net_wide2000.pt`) added seven new fixed
rungs reaching beta=2000, but its `random_rungs` block was inherited
unchanged from `wide250.yaml` and still only covers beta up to 250 — the
exact same kind of coverage gap the Mac Mini is closing for u2 tonight
(`docs/MAC_MINI_TASKS.md` Task 1: u2's `random_rungs` never generated past
beta=430 either, despite fixed rungs now reaching 2000). Generating this
data does not commit to retraining on it immediately, it just removes the
blocker for a future "wide2000 v2" u1 retrain that has genuinely dense
coverage across its whole range, matching what's being built for u2.

Create `u1_2d/configs/random_rungs_2000_gen.yaml`:

```yaml
seed: 1
device: cpu

data:
  out_dir: out/u1_2d/data_random_2000
  n_chains: 16
  thin: 5
  topological_updates: true
  random_rungs:
    - {n: 24, beta_min: 250.0, beta_max: 2000.0, lattice_size: 16, n_configs: 128}
    - {n: 6,  beta_min: 250.0, beta_max: 2000.0, lattice_size: 32, n_configs: 128}
```

The counts (24 at L=16, 6 at L=32) are a proportional scale-down of the
existing 60/12 rungs `wide250.yaml` already uses for its 1-250 range,
matched roughly by log-coverage density (log(2000/250) is about 0.38x
log(250/1)). This is a first cut, not a validated design — if the Mac
Mini or Windows session has a better-reasoned number by the time this
matters, defer to that instead of what's written here.

Run as a single sequential process (no `--shard`, no background `&`):

```powershell
$env:U1_2D_TORCH_THREADS = "8"
.venv\Scripts\python.exe u1_2d\scripts\01_generate_data.py `
  --config u1_2d\configs\random_rungs_2000_gen.yaml --device cpu
```

This is 30 ensembles at n_configs=128 each, single-threaded-process,
sequential — expect this to take a long time (plausibly the whole night;
L=32 rungs are the expensive ones). That's fine, it's meant to run
unattended. If it doesn't finish by morning, whatever rungs it completed
are still usable — each rung writes its own file, so a partial run is not
wasted, just incomplete coverage.

**Before treating any of it as usable**, sanity-check against the exact
closed form using the pattern already established for the other widening
checks (`u1_2d/scripts/69_widening_test_data_check.py` — note its default
`--n-configs-before-augment` doesn't apply here since this task uses no
`sector_augment`, so it's harmless either way, or just skip that flag).
Flag anything with |z| > 3.

## Shipping data back

Same as the Mac Mini brief: `out/**/*.pt` is gitignored, so this will not
go through `git push`. Transfer `out/u1_2d/data_random_2000/` back by
whatever's convenient (network share, USB, etc.) once generated and
checked — do not force it into git.

## Explicit "do not" list

- Do not run more than one Python process at a time.
- Do not elevate process priority.
- Do not touch power/EcoQoS settings.
- Do not run `02_train.py` / `03_run_ladder.py` / `04_validate.py` with
  checkpoint sampling — GPU work stays on the primary machine.
- Do not write into `out/u1_2d/data_wide/` or any existing data directory
  — use the new, isolated `out_dir` above.
