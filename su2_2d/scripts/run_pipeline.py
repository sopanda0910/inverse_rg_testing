"""First SU(2) pipeline chain: smoke -> data -> train -> first lift.

Sentinel-resumable (state in out/su2_2d/state/); rerun to resume after any
failure. Expected ~30-35 min total at 8 threads.

    .venv/Scripts/python.exe su2_2d/scripts/run_pipeline.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "su2_2d" / "scripts"
OUT = REPO / "out" / "su2_2d"
STATE = OUT / "state"


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str]) -> None:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return
    log(f"STAGE_{name}_START: {' '.join(cmd)}")
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env={**os.environ, "PYTHONUNBUFFERED": "1"}).returncode
    dt = (time.time() - t0) / 60
    if rc != 0:
        log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
        log("CHAIN_FAILED")
        sys.exit(1)
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
    log(f"STAGE_{name}_DONE ({dt:.1f} min)")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    config = ["--config", "su2_2d/configs/su2.yaml"]
    run_stage("SMOKE", [sys.executable, str(SCRIPTS / "00_smoke.py")])
    run_stage("DATA", [sys.executable, str(SCRIPTS / "01_generate_data.py"), *config])
    run_stage("TRAIN", [sys.executable, str(SCRIPTS / "02_train.py"), *config])
    run_stage("LIFT", [sys.executable, str(SCRIPTS / "03_sample_validate.py"), *config])
    log("CHAIN_DONE")


if __name__ == "__main__":
    main()
