"""Follow-up chain: waits for the running 19_ode_reweighting job, then runs
the loose-end fixes in sequence.

Stages (sentinels in campaign_state/, prefix FU_):
  0. WAIT      -- poll until no python process is running 19_ode_reweighting
                  (proceeds anyway after a 6 h timeout).
  1. PYTEST    -- full diffusion_v2 test suite (incl. the new ODE tests).
  2. TAIL_ADAPT-- 18 adaptive tails (cap 2000) on the transported ensembles;
                  settles the C_L64 overshoot with a converged tail.
  3. SEED2     -- exact-sector rerun of the one marginal case D_bc20 with an
                  independent seed (false-positive check).
  4. PROBES    -- 19 stability check: same case at 8 probes / 240 steps.
  5. EASY      -- 19 easy case (L=16, beta_f=4.44, 128 configs) where the
                  model gap is smallest -- the estimator-works demonstration.

    .venv/Scripts/python.exe diffusion_v2/scripts/run_followup.py
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
OUT = REPO / "out" / "diffusion_v2" / "v2"
STATE = OUT / "campaign_state"
MAIN_GEN = OUT / "generalization"
SEED2_GEN = OUT / "generalization_exact_sectors_seed2"
SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def ode_job_running() -> bool:
    probe = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "Where-Object {$_.CommandLine -match '19_ode_reweighting'}).Count"],
        capture_output=True, text=True)
    try:
        return int(probe.stdout.strip() or 0) > 0
    except ValueError:
        return False


def run_stage(name, cmd, env_extra=None):
    sentinel = STATE / f"stage_FU_{name}.done"
    if sentinel.exists():
        log(f"STAGE_FU_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_FU_{name}_START: {' '.join(map(str, cmd))}")
    env = {**os.environ, "DIFFUSION_V2_TORCH_THREADS": "6",
           "PYTHONUNBUFFERED": "1", **(env_extra or {})}
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_FU_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_FU_{name}_FAILED rc={rc} ({dt:.1f} min)")
    return False


def main():
    STATE.mkdir(parents=True, exist_ok=True)
    log("FOLLOWUP_START")
    t_wait = time.time()
    while ode_job_running():
        if time.time() - t_wait > 6 * 3600:
            log("WAIT_TIMEOUT: 19_ode_reweighting still running after 6 h, proceeding")
            break
        time.sleep(60)
    log(f"WAIT_DONE ({(time.time() - t_wait) / 60:.0f} min)")

    failures = []
    if not run_stage("PYTEST", [PY, "-m", "pytest", "diffusion_v2/tests", "-q"]):
        failures.append("PYTEST")

    if not run_stage("TAIL_ADAPT", [
            PY, "diffusion_v2/scripts/18_pq_hmc_tail.py",
            "--gen-dir", str(MAIN_GEN), "--max-traj", "2000",
            "--out", str(OUT / "pq_hmc_tail_adaptive")]):
        failures.append("TAIL_ADAPT")

    if not (STATE / "stage_FU_SEED2_CACHE.done").exists():
        for sub in ("bases", "reference"):
            src, dst = MAIN_GEN / sub, SEED2_GEN / sub
            if src.exists():
                dst.mkdir(parents=True, exist_ok=True)
                for f in src.glob("*.pt"):
                    if not (dst / f.name).exists():
                        shutil.copy2(f, dst / f.name)
        (STATE / "stage_FU_SEED2_CACHE.done").write_text("done\n")
    if not run_stage("SEED2", [
            PY, "diffusion_v2/scripts/06_generalization_study.py",
            *SAMPLER_FLAGS, "--seed", "314159",
            "--symmetrize-base", "--sector-mode", "exact",
            "--cases", "D_bc20", "--out-dir", str(SEED2_GEN)]):
        failures.append("SEED2")

    if not run_stage("PROBES", [
            PY, "diffusion_v2/scripts/19_ode_reweighting.py",
            "--cases", "16:14.1464", "--n-configs", "64",
            "--n-probes", "8", "--ode-steps", "240",
            "--out", str(OUT / "ode_reweighting_probes8")]):
        failures.append("PROBES")

    if not run_stage("EASY", [
            PY, "diffusion_v2/scripts/19_ode_reweighting.py",
            "--cases", "16:4.44493", "--n-configs", "128",
            "--out", str(OUT / "ode_reweighting_easy")]):
        failures.append("EASY")

    log(f"FOLLOWUP_DONE_WITH_ERRORS: {failures}" if failures else "FOLLOWUP_DONE")


if __name__ == "__main__":
    main()
