"""Phase 4: the two remaining ESS-program arms, then figures 23-27.

Phase 3 regenerated 25 of the 27 appendix figures. Figures 23-25 (23) and 26-27
(26) additionally need two arms that NO existing driver produces end to end:

    ess_chain/verify_rkl2      multi-case reverse-KL on the SMALL (v2) net.
                               22_multicase_rkl.py defaults --out-checkpoint to
                               score_net_rkl2.pt beside its input, then 19
                               verifies it. Labelled "KEPT (final)" in fig 27.
    ess_chain/verify_big_base  the v3 capacity scale-up: hidden 80 / depth 5
                               trained fresh on v2's rungs plus 24 more at
                               L=32. run_scale_chain.py does this end to end.
                               Labelled "discarded" in fig 27 -- it is a
                               comparison arm, NOT a replacement for the
                               deployed checkpoint, which is why generalization
                               and thermalization are NOT regenerated from it.

Both arms read the promoted canonical checkpoint/data, so this must run after
phase 3's PROMOTE.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase4.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCRIPTS = REPO / "u1_2d" / "scripts"
CONFIG = "u1_2d/configs/v2_gpu_verify.yaml"
V3_CONFIG = "u1_2d/configs/v3_scale.yaml"
STATE = REPO / "artifacts" / "gpu_verify" / "state"
CANON = REPO / "out" / "u1_2d"
CKPT = CANON / "checkpoints" / "score_net.pt"
RKL2 = CANON / "checkpoints" / "score_net_rkl2.pt"
CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]
# v3 adds 24 L=32 rungs to v2's 82. expand_rungs seeds each spec independently,
# so the existing ensembles are reused verbatim and only the new rungs are
# generated -- sharded, since that stage is pure HMC and one-thread-per-process.
V3_DATA_SHARDS = 8


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], device: str | None = None,
              threads: str | None = None, critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    for key, val in (("U1_2D_DEVICE", device), ("U1_2D_TORCH_THREADS", threads)):
        if val:
            env[key] = val
        else:
            env.pop(key, None)
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("PHASE4_ABORTED: downstream stages depend on this one")
        sys.exit(1)
    return False


def run_v3_data() -> bool:
    """v3's extra rungs, fanned out one single-threaded process per core."""
    sentinel = STATE / "stage_V3_DATA.done"
    if sentinel.exists():
        log("STAGE_V3_DATA: sentinel present, skipping")
        return True
    log(f"STAGE_V3_DATA_START: {V3_DATA_SHARDS} shards")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_TORCH_THREADS": "1"}
    base = [PY, "u1_2d/scripts/01_generate_data.py", "--config", V3_CONFIG,
            "--device", "cpu"]
    t0 = time.time()
    procs = [subprocess.Popen([*base, "--shard", f"{i}/{V3_DATA_SHARDS}"],
                              cwd=REPO, env=env) for i in range(V3_DATA_SHARDS)]
    if any(p.wait() for p in procs):
        log("STAGE_V3_DATA_FAILED in shards")
        return False
    if subprocess.run([*base, "--merge-shards"], cwd=REPO, env=env).returncode != 0:
        log("STAGE_V3_DATA_FAILED at merge")
        return False
    dt = (time.time() - t0) / 60
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({dt:.1f} min, {V3_DATA_SHARDS} shards)\n")
    log(f"STAGE_V3_DATA_DONE ({dt:.1f} min)")
    return True


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("PHASE4_START")
    if not (STATE / "stage_PROMOTE.done").exists():
        log("PHASE4_ABORTED: phase 3 has not promoted the checkpoint yet")
        sys.exit(1)
    if not CKPT.exists():
        log(f"PHASE4_ABORTED: no checkpoint at {CKPT}")
        sys.exit(1)

    failures = []
    if not run_v3_data():
        failures.append("V3_DATA")

    # The rkl2 arm, on the small (deployed) net. run_scale_chain covers the big
    # net but nothing covers this one, so it is spelled out here.
    if not run_stage("RKL2", [PY, str(SCRIPTS / "22_multicase_rkl.py"),
                              "--config", CONFIG, "--checkpoint", str(CKPT),
                              "--out-checkpoint", str(RKL2), "--steps", "300"],
                     device="cuda"):
        failures.append("RKL2")
    elif RKL2.exists():
        if not run_stage("VERIFY_RKL2", [PY, str(SCRIPTS / "19_ode_reweighting.py"),
                                         "--config", CONFIG,
                                         "--checkpoint", str(RKL2),
                                         "--cases", *CASES,
                                         "--out", str(CANON / "ess_chain" / "verify_rkl2")],
                         device="cuda"):
            failures.append("VERIFY_RKL2")
    else:
        # 22 only writes the checkpoint on a guarded improvement, exactly as
        # RKLFT did in phase 3. If it never improves there is no rkl2 arm to
        # verify, and figs 23/26 will be short one series.
        log("RKL2 never improved under the guards; no checkpoint to verify")
        failures.append("VERIFY_RKL2 (no rkl2 checkpoint)")

    # The v3 capacity arm, end to end: v3 train -> verify_big_base -> RKL ->
    # verify_big_rkl. Its DATA stage re-runs 01 but every ensemble is already on
    # disk from V3_DATA, so it costs seconds.
    if not run_stage("SCALE_CHAIN", [PY, str(SCRIPTS / "run_scale_chain.py")],
                     device="cuda"):
        failures.append("SCALE_CHAIN")

    for name, cmd in [
        ("FIG_23", [PY, "u1_2d/scripts/23_ess_progress_figures.py"]),
        ("FIG_26", [PY, "u1_2d/scripts/26_final_results_figures.py"]),
        ("ASSEMBLE", [PY, "u1_2d/scripts/30_assemble_appendix_figures.py"]),
    ]:
        if not run_stage(name, cmd):
            failures.append(name)

    log(f"PHASE4_DONE_WITH_ERRORS: {failures}" if failures else "PHASE4_DONE")


if __name__ == "__main__":
    main()
