"""GPU-port verification driver: data -> train -> ladder -> validate -> compare.

Runs the full v2 pipeline at frozen settings but into isolated paths, so the
result can be compared against the frozen study without overwriting it. Written
to run unattended and detached -- nothing here needs a network connection or an
attached shell.

  * every stage is sentinel-resumable (artifacts/gpu_verify/state/stage_*.done),
    and the underlying scripts resume their own work too: 01 skips existing
    ensembles, 02 continues from its .resume snapshot;
  * device and parallelism per stage come from measurement on this box, not
    assumption (all figures: Ryzen 7 260 8c/16t + RTX 5060 Laptop):
      01 DATA     cpu, 8 single-threaded shards. Batched HMC over 16 chains at
                  L<=32 is launch-bound: 2.7x faster on CPU than GPU, and faster
                  on 1 torch thread (154 sweeps/s) than on 8 (142) or 12 (91).
                  Rungs are independent, so cores are filled by processes.
      02 TRAIN    cuda. Batch 16 uses ~7% of the card, but batch size is a
                  training hyperparameter -- raising it would change the
                  optimization and void the comparison. torch.compile would be
                  the honest win here and is unavailable (no Triton on Windows).
      03 LADDER   cuda, sampler-dominated. sample_batch_size is left at 32: the
                  score net is already saturated there at L=64 (1182 configs/s
                  at batch 32 vs 1176 at 192), so raising it buys nothing.
      04 VALIDATE cpu. Reference HMC at L=16/32 plus measurement; the GPU
                  crossover for HMC is L=64 (L=32 0.50x, L=64 1.12x, L=128 2.30x).
  * all output appends to out/u1_2d/gpu_verification/run.log; the final
    sentinel is CHAIN_DONE or CHAIN_DONE_WITH_ERRORS.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CONFIG = "u1_2d/configs/v2_gpu_verify.yaml"
STATE = REPO / "artifacts" / "gpu_verify" / "state"
OUT = REPO / "out" / "u1_2d" / "gpu_verification"

# Stage 01 fans out to this many single-threaded processes: one per physical
# core on this box. See run_shards() for why threads-per-process is set to 1.
DATA_SHARDS = 8


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], threads: str | None = None,
              critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {' '.join(cmd)}")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if threads:
        env["U1_2D_TORCH_THREADS"] = threads
    else:
        env.pop("U1_2D_TORCH_THREADS", None)
    t0 = time.time()
    result = subprocess.run(cmd, cwd=REPO, env=env)
    dt = (time.time() - t0) / 60
    if result.returncode == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={result.returncode} ({dt:.1f} min)")
    if critical:
        log("CHAIN_FAILED (critical stage)")
        sys.exit(1)
    return False


def run_shards(name: str, n_shards: int, critical: bool = False) -> bool:
    """Stage 01 as N concurrent single-threaded processes.

    Measured on this box (Ryzen 7 260, 8 physical cores): batched HMC over 16
    chains at L<=32 runs at 154 sweeps/s on ONE torch thread and 142 on eight --
    the tensors are far too small to amortize thread synchronization, so the
    intra-process thread pool is worse than useless. The parallelism that does
    pay is across rungs, which are fully independent.

    This is a per-machine call, not a reversal of the project rule: the ban on
    parallel workers in CLAUDE.md is specific to the Snapdragon, where
    parallelism *combined with priority elevation* caused hardware crashes. No
    priority is elevated here and that laptop is not this one.
    """
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {n_shards} single-threaded shards")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_TORCH_THREADS": "1"}
    t0 = time.time()
    procs = []
    for i in range(n_shards):
        cmd = [PY, "u1_2d/scripts/01_generate_data.py", "--config", CONFIG,
               "--device", "cpu", "--shard", f"{i}/{n_shards}"]
        procs.append(subprocess.Popen(cmd, cwd=REPO, env=env))
    codes = [p.wait() for p in procs]
    dt = (time.time() - t0) / 60
    if any(codes):
        log(f"STAGE_{name}_FAILED shard rcs={codes} ({dt:.1f} min)")
        if critical:
            log("CHAIN_FAILED (critical stage)")
            sys.exit(1)
        return False
    # Fold the per-shard matching files into the single matching.json the rest
    # of the pipeline reads.
    merge = subprocess.run([PY, "u1_2d/scripts/01_generate_data.py", "--config",
                            CONFIG, "--device", "cpu", "--merge-shards"],
                           cwd=REPO, env=env)
    if merge.returncode != 0:
        log(f"STAGE_{name}_FAILED at shard merge ({dt:.1f} min)")
        if critical:
            sys.exit(1)
        return False
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min, "
                        f"{n_shards} shards)\n")
    log(f"STAGE_{name}_DONE ({dt:.1f} min)")
    return True


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"CHAIN_START config={CONFIG}")

    ok = True
    # HMC only -- measured 2.7x faster on CPU at these lattice sizes.
    ok &= run_shards("DATA", DATA_SHARDS, critical=True)
    # --resume is safe on a fresh run: it is a no-op when no .resume exists.
    ok &= run_stage("TRAIN", [PY, "u1_2d/scripts/02_train.py",
                              "--config", CONFIG, "--device", "cuda", "--resume"],
                    critical=True)
    # No sampler flags: v2_gpu_verify.yaml already carries the campaign's
    # physics_blend_coef / physics_blend_beta_min / sigma_min_beta_coef, and the
    # CLI flags only exist to override those. Letting the config drive removes a
    # way for this run to silently differ from the frozen one.
    ok &= run_stage("LADDER", [PY, "u1_2d/scripts/03_run_ladder.py",
                               "--config", CONFIG, "--device", "cuda"],
                    critical=True)
    # CPU: this stage is reference HMC at L=16/32 plus observable measurement --
    # no score-net sampling. Measured sweeps/s by size (16 chains) put the GPU
    # crossover at L=64: L=32 0.50x, L=64 1.12x, L=128 2.30x. Two of the three
    # reference rungs sit below the crossover.
    ok &= run_stage("VALIDATE", [PY, "u1_2d/scripts/04_validate.py",
                                 "--config", CONFIG, "--device", "cpu"],
                    threads="8", critical=True)
    ok &= run_stage("COMPARE", [PY, "u1_2d/scripts/31_compare_verification.py"])

    log("CHAIN_DONE" if ok else "CHAIN_DONE_WITH_ERRORS")


if __name__ == "__main__":
    main()
