"""Parallel sector-fix chain: two 6-thread study workers + merge + P(Q) tail.

Replaces run_sectors.py's single-worker SECTOR_STUDY with a cost-balanced
two-way case split (the validated-safe 2-process recipe). Worker A resumes
generalization_exact_sectors/ (already-done cases skip via summary.json);
worker B runs its subset in generalization_exact_sectors_b/ with cache-copied
bases/references, and MERGE folds B's ensembles/figures/records back into the
main directory before the aggregate report is rebuilt.

    .venv/Scripts/python.exe u1_2d/scripts/run_sectors2.py
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
OUT = REPO / "out" / "u1_2d"
STATE = OUT / "campaign_state"
MAIN_GEN = OUT / "generalization"
SEC_GEN = OUT / "generalization_exact_sectors"
SEC_GEN_B = OUT / "generalization_exact_sectors_b"
SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]
SECTOR_FLAGS = ["--seed", "20260730", "--symmetrize-base", "--sector-mode", "exact"]

CASES_A = ",".join([
    "C_L128",
    "E_bc1.2", "E_bc2.7", "E_bc3.4", "E_bc4.5", "E_bc5.8",
    "E_bc9", "E_bc11.8", "E_bc18", "E_bc35", "E_bc45",
    "A_bc2", "A_bc3", "A_bc4",
])
CASES_B = ",".join([
    "C_L64",
    "F_L32_bc100", "F_L32_bc218.58", "F_L64_bc55.0237",
    "D_bc14.1464", "D_bc20", "D_bc30", "D_bc40", "D_bc55.0237",
    "B_bt6", "B_bt10", "B_bt16", "B_bt20", "B_bt30", "B_bt55.0237", "B_bc2_bt8",
    "A_bc5", "A_bc6", "A_bc8",
])


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def copy_caches(dst_root):
    for sub in ("bases", "reference"):
        src, dst = MAIN_GEN / sub, dst_root / sub
        if src.exists():
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.pt"):
                if not (dst / f.name).exists():
                    shutil.copy2(f, dst / f.name)


def study_cmd(out_dir, cases):
    return [PY, "u1_2d/scripts/06_generalization_study.py",
            *SAMPLER_FLAGS, *SECTOR_FLAGS, "--cases", cases,
            "--out-dir", str(out_dir)]


def run_stage(name, fn):
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START")
    t0 = time.time()
    ok = fn()
    dt = (time.time() - t0) / 60
    if ok:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
    else:
        log(f"STAGE_{name}_FAILED ({dt:.1f} min)")
    return ok


def parallel_study():
    env = {**os.environ, "U1_2D_TORCH_THREADS": "6", "PYTHONUNBUFFERED": "1"}
    log_a = open(OUT / "sectors_worker_a.log", "a", encoding="utf-8")
    log_b = open(OUT / "sectors_worker_b.log", "a", encoding="utf-8")
    pa = subprocess.Popen(study_cmd(SEC_GEN, CASES_A), cwd=REPO, env=env,
                          stdout=log_a, stderr=subprocess.STDOUT)
    pb = subprocess.Popen(study_cmd(SEC_GEN_B, CASES_B), cwd=REPO, env=env,
                          stdout=log_b, stderr=subprocess.STDOUT)
    log(f"workers launched: A pid={pa.pid} ({CASES_A.count(',')+1} cases), "
        f"B pid={pb.pid} ({CASES_B.count(',')+1} cases)")
    rca, rcb = pa.wait(), pb.wait()
    log_a.close(); log_b.close()
    log(f"worker A rc={rca}, worker B rc={rcb}")
    return rca == 0 and rcb == 0


def merge():
    main_path = SEC_GEN / "summary.json"
    b_path = SEC_GEN_B / "summary.json"
    records = json.loads(main_path.read_text(encoding="utf-8"))
    records_b = json.loads(b_path.read_text(encoding="utf-8"))
    records.update(records_b)
    main_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    for sub in ("generated", "figures"):
        src = SEC_GEN_B / sub
        if src.exists():
            dst = SEC_GEN / sub
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.iterdir():
                if f.is_file():
                    shutil.copy2(f, dst / f.name)
    log(f"merged {len(records_b)} worker-B records; total {len(records)}")
    rc = subprocess.run([PY, "u1_2d/scripts/06_generalization_study.py",
                         "--report-only", "--out-dir", str(SEC_GEN)],
                        cwd=REPO, env={**os.environ, "PYTHONUNBUFFERED": "1"}).returncode
    return rc == 0


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    log("SECTORS2_START")
    if not (STATE / "stage_SECTOR_CACHECOPY_B.done").exists():
        copy_caches(SEC_GEN_B)
        (STATE / "stage_SECTOR_CACHECOPY_B.done").write_text("done\n")
        log("STAGE_SECTOR_CACHECOPY_B_DONE")
    failures = []
    if not run_stage("SECTOR_STUDY_PAR", parallel_study):
        failures.append("SECTOR_STUDY_PAR")
    else:
        if not run_stage("SECTOR_MERGE", merge):
            failures.append("SECTOR_MERGE")
    env = {**os.environ, "U1_2D_TORCH_THREADS": "6", "PYTHONUNBUFFERED": "1"}

    def pq_tail():
        rc = subprocess.run([PY, "u1_2d/scripts/18_pq_hmc_tail.py",
                             "--gen-dir", str(MAIN_GEN), "--n-traj", "200"],
                            cwd=REPO, env=env).returncode
        return rc == 0

    if not run_stage("PQ_TAIL", pq_tail):
        failures.append("PQ_TAIL")
    log(f"SECTORS_DONE_WITH_ERRORS: {failures}" if failures else "SECTORS_DONE")


if __name__ == "__main__":
    main()
