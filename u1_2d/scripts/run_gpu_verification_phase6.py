"""Phase 6: the last two producible arms the campaign never rebuilt.

After phase 5 every figure input exists, but two results of record cited in
the appendix prose were still carrying pre-campaign (frozen-checkpoint) data:

  ess_chain/verify_correction   Table S5's last row -- the 354-param score
                                correction head, judged on a grid DISJOINT
                                from anything used to select it (8:8, 16:25,
                                32:14.1464). Producerless in the driver chain;
                                reconstructed here as 25 -> 19 --correction,
                                which is exactly what script 25's docstring
                                prescribes.
  generalization_fresh_s3/_s4   appendix "Fresh-seed classification of the 3
                                sigma Wilson flags". Produced by run_audit_chain
                                GEN_FRESH_S3/S4 -- 06 over the four flagged
                                cases at seeds 20260803 / 20260804.

The two fresh-seed studies are independent, so they run concurrently; each is
sharded 2 ways, giving 4 CUDA contexts -- the documented ceiling on 8 GiB.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase6.py
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
STATE = REPO / "artifacts" / "gpu_verify" / "state"
CANON = REPO / "out" / "u1_2d"
RKL2 = CANON / "checkpoints" / "score_net_rkl2.pt"
CORRECTION = CANON / "checkpoints" / "score_correction.pt"

# The disjoint judging grid quoted in Table S5's correction-head row.
CORRECTION_CASES = ["8:8.0", "16:25.0", "32:14.1464"]
FRESH_CASES = "D_bc14.1464,B_bt20,A_bc8,F_L64_bc55.0237"
FRESH_SEEDS = ((20260803, "s3"), (20260804, "s4"))
FRESH_SHARDS = 2


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def env_for(device: str | None = None, threads: str | None = None) -> dict:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    for key, val in (("U1_2D_DEVICE", device), ("U1_2D_TORCH_THREADS", threads)):
        if val:
            env[key] = val
        else:
            env.pop(key, None)
    return env


def run_stage(name: str, cmd: list[str], device: str | None = None,
              critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START")
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env_for(device)).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("PHASE6_ABORTED")
        sys.exit(1)
    return False


def run_fresh_seeds() -> bool:
    """Both fresh-seed studies at once, each sharded 2 ways (4 contexts total)."""
    sentinel = STATE / "stage_GEN_FRESH.done"
    if sentinel.exists():
        log("STAGE_GEN_FRESH: sentinel present, skipping")
        return True
    log(f"STAGE_GEN_FRESH_START: {len(FRESH_SEEDS)} seeds x {FRESH_SHARDS} shards")
    t0 = time.time()
    env = env_for("cuda")
    procs = []
    for seed, tag in FRESH_SEEDS:
        out_dir = CANON / f"generalization_fresh_{tag}"
        # 06 skips any case already present in summary.json. These directories
        # still hold the PRE-CAMPAIGN run (they survived phase 3's invalidation
        # because nothing in the driver chain owned them), so without this the
        # stage "succeeds" in 30 seconds and silently republishes frozen-
        # checkpoint results as if they were regenerated.
        stale = out_dir / "summary.json"
        if stale.exists():
            stale.rename(out_dir / "summary.preGPU.json")
            log(f"  {tag}: moved pre-campaign summary.json aside")
        for shard_file in out_dir.glob("summary.shard*.json"):
            shard_file.unlink()
        # 06 has no --config: it reads the canonical checkpoint via --checkpoint
        # (defaulting to the promoted out/u1_2d/checkpoints/score_net.pt), which
        # is what the fresh-seed classification is supposed to judge.
        base = [PY, str(SCRIPTS / "06_generalization_study.py"),
                "--cases", FRESH_CASES,
                "--seed", str(seed), "--device", "cuda", "--out-dir", str(out_dir)]
        for i in range(FRESH_SHARDS):
            procs.append(subprocess.Popen([*base, "--shard", f"{i}/{FRESH_SHARDS}"],
                                          cwd=REPO, env=env))
    if any(p.wait() for p in procs):
        log("STAGE_GEN_FRESH_FAILED in shards")
        return False
    for seed, tag in FRESH_SEEDS:
        out_dir = CANON / f"generalization_fresh_{tag}"
        # --cases is REQUIRED on the merge pass. After folding the shards, 06
        # falls through to its case loop and skips only what is already in
        # records; without the filter it would treat the other 34 cases of the
        # full study as missing and run them into this fresh-seed directory.
        rc = subprocess.run([PY, str(SCRIPTS / "06_generalization_study.py"),
                             "--merge-shards",
                             "--cases", FRESH_CASES, "--seed", str(seed),
                             "--device", "cuda", "--out-dir", str(out_dir)],
                            cwd=REPO, env=env).returncode
        if rc != 0:
            log(f"STAGE_GEN_FRESH_FAILED at merge for {tag}")
            return False
    dt = (time.time() - t0) / 60
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
    log(f"STAGE_GEN_FRESH_DONE ({dt:.1f} min)")
    return True


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("PHASE6_START")
    if not RKL2.exists():
        log(f"PHASE6_ABORTED: no rkl2 checkpoint at {RKL2}")
        sys.exit(1)

    failures = []

    if not run_stage("CORRECTION",
                     [PY, str(SCRIPTS / "25_score_correction.py"),
                      "--config", CONFIG, "--checkpoint", str(RKL2),
                      "--out", str(CORRECTION), "--steps", "200"],
                     device="cuda"):
        failures.append("CORRECTION")
    elif CORRECTION.exists():
        if not run_stage("VERIFY_CORRECTION",
                         [PY, str(SCRIPTS / "19_ode_reweighting.py"),
                          "--config", CONFIG, "--checkpoint", str(RKL2),
                          "--correction", str(CORRECTION),
                          "--cases", *CORRECTION_CASES,
                          "--out", str(CANON / "ess_chain" / "verify_correction")],
                         device="cuda"):
            failures.append("VERIFY_CORRECTION")
    else:
        log("CORRECTION produced no file under best-val selection")
        failures.append("VERIFY_CORRECTION (no correction file)")

    if not run_fresh_seeds():
        failures.append("GEN_FRESH")

    log(f"PHASE6_DONE_WITH_ERRORS: {failures}" if failures else "PHASE6_DONE")


if __name__ == "__main__":
    main()
