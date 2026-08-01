"""Sector-fix chain: exact-sector study rerun + P(Q) before/after HMC-tail plots.

Stages (sequential, resumable via sentinels in campaign_state/):
  1. SECTOR_CACHECOPY -- reuse the main study's bases and references.
  2. SECTOR_STUDY -- full 38-case rerun with --symmetrize-base --sector-mode
     exact into generalization_exact_sectors/ (P(Q) exact by construction at
     every target, including the mismatch controls).
  3. PQ_TAIL -- P(Q) before/after a 200-trajectory instanton-HMC tail on the
     ORIGINAL transport-honest ensembles (the seeding-claim figure).

    .venv/Scripts/python.exe diffusion_v2/scripts/run_sectors.py
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
OUT = REPO / "out" / "diffusion_v2" / "v2"
STATE = OUT / "campaign_state"
MAIN_GEN = OUT / "generalization"
SEC_GEN = OUT / "generalization_exact_sectors"
SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name, cmd):
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {' '.join(cmd)}")
    env = {**os.environ, "DIFFUSION_V2_TORCH_THREADS": "6", "PYTHONUNBUFFERED": "1"}
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    return False


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    log("SECTORS_START")
    if not (STATE / "stage_SECTOR_CACHECOPY.done").exists():
        for sub in ("bases", "reference"):
            src, dst = MAIN_GEN / sub, SEC_GEN / sub
            if src.exists():
                dst.mkdir(parents=True, exist_ok=True)
                for f in src.glob("*.pt"):
                    if not (dst / f.name).exists():
                        shutil.copy2(f, dst / f.name)
        (STATE / "stage_SECTOR_CACHECOPY.done").write_text("done\n")
        log("STAGE_SECTOR_CACHECOPY_DONE")
    failures = []
    if not run_stage("SECTOR_STUDY", [
            PY, "diffusion_v2/scripts/06_generalization_study.py",
            *SAMPLER_FLAGS, "--seed", "20260730",
            "--symmetrize-base", "--sector-mode", "exact",
            "--out-dir", str(SEC_GEN)]):
        failures.append("SECTOR_STUDY")
    if not run_stage("PQ_TAIL", [
            PY, "diffusion_v2/scripts/18_pq_hmc_tail.py",
            "--gen-dir", str(MAIN_GEN), "--n-traj", "200"]):
        failures.append("PQ_TAIL")
    log(f"SECTORS_DONE_WITH_ERRORS: {failures}" if failures else "SECTORS_DONE")


if __name__ == "__main__":
    main()
