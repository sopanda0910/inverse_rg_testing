"""Error bars for the projection-sigma null result.

The single-seed A/B gave mean|z| of 1.710 / 1.810 / 1.732 for
charge_projection_sigma = 0.20 / 0.31 / 0.50, with identical |z|>3 counts and
-- the actual evidence for a null -- no monotone ordering in sigma. But the
arms diverge into different RNG streams the moment their first projection
differs, so every between-arm difference already contains seed noise and the
single run cannot separate the two.

This runs three seeds per threshold. The null is measured (rather than
asserted) iff the between-arm spread sits inside the between-seed spread.

Nine ladder+validate pairs, three at a time: the ladder is sampler-dominated,
so this is GPU work, and 3 concurrent is the documented ceiling for processes
each carrying their own CUDA context.

    .venv/Scripts/python.exe u1_2d/scripts/run_proj_seed_sweep.py
"""

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCRIPTS = REPO / "u1_2d" / "scripts"
LOGDIR = REPO / "out" / "u1_2d" / "gpu_verification"
TAGS = ("020", "031", "050")
SEEDS = (11, 12, 13)
WORKERS = 3


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_arm(tag: str, seed: int) -> tuple[str, bool, float]:
    name = f"s{tag}_seed{seed}"
    cfg = f"u1_2d/configs/v2_proj{tag}_seed{seed}.yaml"
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_DEVICE": "cuda"}
    LOGDIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"{name}: START")
    with open(LOGDIR / f"projseed_{name}.log", "w", encoding="utf-8") as fh:
        for script in ("03_run_ladder.py", "04_validate.py"):
            rc = subprocess.run([PY, str(SCRIPTS / script), "--config", cfg],
                                cwd=REPO, env=env, stdout=fh,
                                stderr=subprocess.STDOUT).returncode
            if rc != 0:
                dt = (time.time() - t0) / 60
                log(f"{name}: FAILED in {script} rc={rc} ({dt:.1f} min)")
                return name, False, dt
    dt = (time.time() - t0) / 60
    log(f"{name}: DONE ({dt:.1f} min)")
    return name, True, dt


def main() -> None:
    log(f"PROJSEED_START: {len(TAGS)}x{len(SEEDS)} arms, {WORKERS} concurrent")
    jobs = [(t, s) for s in SEEDS for t in TAGS]
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = [f.result() for f in [pool.submit(run_arm, t, s) for t, s in jobs]]
    failures = [n for n, ok, _ in results if not ok]
    log(f"wall clock {(time.time() - t0) / 60:.1f} min")
    log(f"PROJSEED_DONE_WITH_ERRORS: {failures}" if failures else "PROJSEED_DONE")


if __name__ == "__main__":
    main()
