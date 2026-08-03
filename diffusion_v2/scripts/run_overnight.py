"""Overnight follow-up chain: patch the two attackable results from the v2 campaign.

Stages (sequential, single process, resumable via sentinels):
  1. H2H_HIGHSTATS -- rerun the head-to-head at the three high couplings with
     512 diffusion configs (4x tighter Q^2 errors) and burn-in 2000 for the
     instanton arm, into diffusion_vs_instanton/highstats/.
  2. BURNIN_SCAN -- instanton-HMC quality vs burn-in (2000, 8000) at beta =
     55.0237 and 218.58; report merges the original burn-in 500 points.
  3. ESS_NOGUIDE -- ESS with blocking-consistency guidance off, attributing
     the ESS gap between the guidance term and the model itself.

    .venv/Scripts/python.exe diffusion_v2/scripts/run_overnight.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CONFIG = "diffusion_v2/configs/v2.yaml"
OUT = REPO / "out" / "diffusion_v2"
STATE = OUT / "campaign_state"


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str]) -> bool:
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


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("OVERNIGHT_START")
    failures = []
    if not run_stage("H2H_HIGHSTATS", [
            PY, "diffusion_v2/scripts/14_diffusion_vs_instanton_hmc.py",
            "--config", CONFIG,
            "--betas", "55.0237,118.5,218.58",
            "--n-gen", "512", "--burn-in", "2000",
            "--out-dir", str(OUT / "diffusion_vs_instanton" / "highstats")]):
        failures.append("H2H_HIGHSTATS")
    if not run_stage("BURNIN_SCAN", [
            PY, "diffusion_v2/scripts/16_h2h_burnin_scan.py",
            "--config", CONFIG]):
        failures.append("BURNIN_SCAN")
    if not run_stage("ESS_NOGUIDE", [
            PY, "diffusion_v2/scripts/15_model_ess.py",
            "--config", CONFIG,
            "--cases", "16:14.1464", "16:55.0237", "32:55.0237", "32:218.58",
            "--n-configs", "64", "--consistency-weight", "0.0",
            "--out", str(OUT / "model_ess_noguide")]):
        failures.append("ESS_NOGUIDE")
    log(f"OVERNIGHT_DONE_WITH_ERRORS: {failures}" if failures else "OVERNIGHT_DONE")


if __name__ == "__main__":
    main()
