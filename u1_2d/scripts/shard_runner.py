"""Shared fan-out helper for the campaign drivers.

WHAT THIS IS FOR
----------------
Two stages in this project dominate a rerun, and both are latency-bound rather
than throughput-bound -- the work per step is too small to fill either
processor, and no per-case setting fixes that because the batch sizes are set
by the physics:

  01_generate_data.py   batched HMC, 16 chains at L<=32. Measured on the
                        Ryzen 7 260: 154 sweeps/s on ONE torch thread, 142 on
                        eight, 91 on twelve. Threads actively HURT -- the
                        tensors are too small to amortize thread sync.
  06_generalization_study.py  alternates 16-chain reference HMC with batch-32
                        ladder sampling. Holds the RTX 5060 at ~32% and the
                        CPU at ~3%.

In both cases the unit of work (a rung, a case) is independent of every other
unit, so the way to use the machine is to run several units at once. That is
the whole idea: fan out over units, not over threads inside one unit.

Stage 01 with 8 single-threaded shards went from 21.7 min (Snapdragon, one
process) to 3.2 min.

THE CONTRACT A SHARDABLE SCRIPT MUST HONOR
------------------------------------------
Both 01 and 06 implement this, and any new stage should too:

  1. --shard I/N selects units where index % N == I. Round-robin, never
     contiguous blocks: expensive units cluster by family (06's D_* cases cost
     ~500 s vs ~160 s for E_*; 01's high-beta rungs carry burn_in 2000), and
     interleaving is what keeps shards balanced.
  2. Each shard writes its OWN result file (matching.shard<I>.json,
     summary.shard<I>.json) -- never the shared one. save_json is atomic so no
     file is ever corrupt, but a shared target would be last-writer-wins and
     would silently drop other shards' units.
  3. --merge-shards folds the per-shard files into the canonical one and
     deletes them.
  4. Anything aggregate -- figures, tables, matched-beta summaries -- is
     DEFERRED to the merge step. A shard sees a fraction of the units, and an
     aggregate built from that fraction looks perfectly valid, which is the
     dangerous part.
  5. A shard still reads the canonical result file first, so it skips units an
     earlier unsharded run finished. Resume works across a change of N.

CHOOSING N
----------
  CPU stages (01): N = physical cores, one torch thread each. Eight here.
  GPU stages (06): N = 3-4 on an 8 GiB card. Each shard carries its own CUDA
     context plus model (~0.5-0.7 GiB), and the speedup flattens once the GPU
     actually saturates -- past that you are only adding contention.

BENIGN RACE, DOCUMENTED SO NOBODY "FIXES" IT
--------------------------------------------
Shards can generate the same cached ensemble concurrently (06's bases/ is keyed
by (L, beta) and several cases share one; 01's rungs do not overlap). Because
save_ensemble writes to a temp file and renames, the loser merely wastes the
work -- the file is never torn. Pre-populating the cache avoids even that.
"""

import os
import subprocess
import time
from pathlib import Path


def run_sharded(
    py: str,
    script: str,
    base_args: list[str],
    n_shards: int,
    repo: Path,
    log,
    threads: str | None = None,
    device: str | None = None,
    merge_args: list[str] | None = None,
) -> bool:
    """Run `script` as n_shards concurrent processes, then merge.

    base_args must NOT contain --shard or --merge-shards; this adds them.
    merge_args defaults to base_args, which is right when the merge pass needs
    the same output paths (it always has so far).
    """
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    for key, val in (("U1_2D_TORCH_THREADS", threads), ("U1_2D_DEVICE", device)):
        if val:
            env[key] = val
        else:
            env.pop(key, None)

    log(f"fan-out: {n_shards} shards of {script}")
    t0 = time.time()
    procs = [
        subprocess.Popen([py, script, *base_args, "--shard", f"{i}/{n_shards}"],
                         cwd=repo, env=env)
        for i in range(n_shards)
    ]
    codes = [p.wait() for p in procs]
    if any(codes):
        log(f"shard failure rcs={codes} after {(time.time()-t0)/60:.1f} min")
        return False

    merge = subprocess.run([py, script, *(merge_args or base_args), "--merge-shards"],
                           cwd=repo, env=env)
    if merge.returncode != 0:
        log(f"shard merge failed rc={merge.returncode}")
        return False
    log(f"fan-out complete in {(time.time()-t0)/60:.1f} min")
    return True
