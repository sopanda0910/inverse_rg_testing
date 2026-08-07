"""Phase 2 of the GPU verification: generalization study -> thermalization scan.

These are the two stages that consume the trained checkpoint, and between them
they are the source for appendix figures 04-16 (13 of 27):

    04-07  generalization/fig_{matched,mismatch,size}_scan.png, fig_raw_topology.png
    08-11  generalization/figures/{A_bc1,D_bc55.0237,F_L32_bc218.58,F_L64_bc55.0237}.png
    12-13  thermalization/{timescales,beta_scan}.png
    14-15  thermalization/L32_beta*/D_*_relaxation.png
    16     thermalization/autocorrelation_modes.png   (needs 11_autocorrelation.py)

Run order is fixed: 05 reads the study's output via --generalization, so 06 must
finish first. Both are pointed at the verification checkpoint and isolated output
dirs -- the frozen out/u1_2d/{generalization,thermalization}/ are never written,
so the published appendix stays reproducible from its own sources.

Launched immediately but waits on phase 1's COMPARE sentinel, so the whole chain
can be queued in one go without an attended handoff.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase2.py
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
GEN_DIR = OUT / "generalization"
THERM_DIR = OUT / "thermalization"
# This run's checkpoint, NOT out/u1_2d/checkpoints/score_net.pt. Both scripts
# default to the frozen one, so passing this explicitly is what makes phase 2
# a test of the newly trained model rather than a re-measurement of the old.
CKPT = "artifacts/gpu_verify/checkpoints/score_net.pt"

# The sampler settings the v2 campaign used. Identical here so the only thing
# that differs from the published study is the checkpoint and the hardware.
SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]

WAIT_TIMEOUT_H = 6.0
# 05 shards share the GPU, so this is bounded by VRAM rather than by cores: each
# shard holds its own CUDA context plus the score net (~0.5-0.7 GiB of 8 GiB).
THERM_SHARDS = 4


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def wait_for_phase1() -> bool:
    target = STATE / "stage_COMPARE.done"
    if target.exists():
        log("phase 1 already complete")
        return True
    log(f"waiting for phase 1 ({target.name}), timeout {WAIT_TIMEOUT_H} h")
    deadline = time.time() + WAIT_TIMEOUT_H * 3600
    while time.time() < deadline:
        if target.exists():
            log("phase 1 complete, starting phase 2")
            return True
        time.sleep(60)
    log("PHASE2_ABORTED: timed out waiting for phase 1")
    return False


def run_stage(name: str, cmd: list[str], threads: str | None = None,
              device: str | None = None, critical: bool = False) -> bool:
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
    if device:
        env["U1_2D_DEVICE"] = device
    else:
        env.pop("U1_2D_DEVICE", None)
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("PHASE2_ABORTED: downstream stages depend on this one")
        sys.exit(1)
    return False


def run_therm_sharded(base_args: list[str], n_shards: int) -> bool:
    """05 as N concurrent shards, then one unsharded pass to build the aggregates.

    05 needs no data merge -- each case writes its own L*_beta*/ directory, so
    concurrent shards never contend for a file. Only timescales.png,
    beta_scan.png and report.md are global, and the merge pass rebuilds them by
    re-walking every case through --skip-cached (seconds, since all are cached).
    """
    sentinel = STATE / "stage_THERM.done"
    if sentinel.exists():
        log("STAGE_THERM: sentinel present, skipping")
        return True
    log(f"STAGE_THERM_START: {n_shards} shards")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_DEVICE": "cuda"}
    t0 = time.time()
    procs = [subprocess.Popen([*base_args, "--shard", f"{i}/{n_shards}"],
                              cwd=REPO, env=env) for i in range(n_shards)]
    codes = [p.wait() for p in procs]
    dt = (time.time() - t0) / 60
    if any(codes):
        log(f"STAGE_THERM_FAILED shard rcs={codes} ({dt:.1f} min)")
        return False
    log(f"shards done ({dt:.1f} min); building aggregates")
    merge = subprocess.run(base_args, cwd=REPO, env=env)
    if merge.returncode != 0:
        log(f"STAGE_THERM_FAILED at aggregate pass rc={merge.returncode}")
        return False
    dt = (time.time() - t0) / 60
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({dt:.1f} min, {n_shards} shards)\n")
    log(f"STAGE_THERM_DONE ({dt:.1f} min)")
    return True


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    log("PHASE2_START")
    if not wait_for_phase1():
        sys.exit(1)
    if not Path(REPO / CKPT).exists():
        log(f"PHASE2_ABORTED: no checkpoint at {CKPT}")
        sys.exit(1)

    ok = True
    # cuda: this stage is ladder sampling across many cases, which is exactly
    # the workload the GPU wins. 06 defaulted to cpu because every published run
    # predates this hardware.
    ok &= run_stage("STUDY", [PY, "u1_2d/scripts/06_generalization_study.py",
                              *SAMPLER_FLAGS, "--seed", "20260730",
                              "--device", "cuda",
                              "--checkpoint", CKPT,
                              "--out-dir", str(GEN_DIR)],
                    critical=True)
    # cuda, on measurement rather than the L<=32 rule of thumb: this stage's
    # baseline HMC runs 64 chains, not the 16 the earlier crossover was measured
    # at, and the bigger batch moves the crossover down. At 64 chains the GPU
    # wins from L=32 up (L=32 1.13x, L=64 3.08x).
    #
    # Sharded because serial it uses almost none of the machine: measured one
    # core at 89% (6% of 16 logical) and the GPU at 5%. Both idle for the same
    # reason -- 32-128 chains at L=32 is too small to fill the card, and one
    # Python thread issues the launches. Cases are independent and each owns its
    # own L*_beta*/ directory, so the only thing deferred is the aggregate.
    therm_args = [PY, "u1_2d/scripts/05_hmc_thermalization.py",
                  "--config", CONFIG, f"--generalization={GEN_DIR}",
                  "--parts", "A,D,E,F", "--skip-cached",
                  "--checkpoint", CKPT, *SAMPLER_FLAGS, "--out", str(THERM_DIR)]
    ok &= run_therm_sharded(therm_args, THERM_SHARDS)
    # Figure 16's source; cheap, and reads only THERM_DIR.
    ok &= run_stage("AUTOCORR", [PY, "u1_2d/scripts/11_autocorrelation.py",
                                 "--dir", str(THERM_DIR)])

    log("PHASE2_DONE" if ok else "PHASE2_DONE_WITH_ERRORS")


if __name__ == "__main__":
    main()
