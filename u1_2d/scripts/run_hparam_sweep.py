"""Mentor TODO 2: does any never-tuned hyperparameter actually matter?

Five knobs were fixed at their first-guess values for the whole program and
never varied: kernel_size, sigma_max, batch_size, topo_weight, sym_augment.
The one capacity change that was made (v3_scale) moved hidden, depth AND the
L=32 training coverage together, so it cannot attribute its result to any of
them.

The design is one-factor-at-a-time from v2 -- and, more importantly, THREE
SEEDS OF THE UNCHANGED BASELINE. Every comparison in this project that lacked
a noise floor has turned out to be inside it (checkpoint variants move fiber
spreads 2-6x; the projection-sigma arms sit inside seed spread; 2 of 10 AIS
seeds diverge). A knob counts as mattering only if it clears the baseline
seed spread, so that spread is the primary measurement here and the knobs are
read against it.

Scored on deployed fiber log-weight spread (15_model_ess), not on training
loss: the program's central lesson is that in-sample objective improvements
do not transfer to deployment.

Nothing here touches out/u1_2d/checkpoints/score_net.pt -- every arm writes
its own checkpoint under artifacts/hparam/.

    .venv/Scripts/python.exe u1_2d/scripts/run_hparam_sweep.py
    .venv/Scripts/python.exe u1_2d/scripts/run_hparam_sweep.py --report
"""

import argparse
import copy
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCRIPTS = REPO / "u1_2d" / "scripts"
BASE_CFG = REPO / "u1_2d" / "configs" / "v2.yaml"
WORK = REPO / "artifacts" / "hparam"
LOGDIR = REPO / "out" / "u1_2d" / "gpu_verification"
CASES = ["16:14.1464", "16:55.0237", "32:55.0237"]
# 6 fits the six remaining arms into a single wave. Measured cost is ~600 MiB
# per arm (CUDA context plus this small net), so six is ~4 GiB of the 8 GiB
# card with nothing else resident -- and the earlier OOM came from sharing the
# card with a 512-config ESS run, not from the sweep itself. Arms resume from
# their 5-epoch snapshots, so a bad estimate costs epochs, not runs.
WORKERS = 6

# (arm, seed, train-block overrides). The three base_* arms are the noise floor.
ARMS = [
    ("base_s0", 0, {}),
    ("base_s1", 1, {}),
    ("base_s2", 2, {}),
    ("kernel5", 0, {"kernel_size": 5}),
    ("sigmax3", 0, {"sigma_max": 3.0}),
    ("sigmax12", 0, {"sigma_max": 12.0}),
    ("topo03", 0, {"topo_weight": 0.3}),
    ("sym10", 0, {"sym_augment": 1.0}),
    ("batch32", 0, {"batch_size": 32}),
    # Follow-up (2026-08-14). topo_weight=0.3 was the only knob to land outside
    # the baseline seed range, but on one seed, and its margin below the best
    # baseline seed (1.20x) is narrower than the baseline spread itself
    # (1.35x). Two more seeds test replication; topo_weight=0.5 tests
    # dose-response, which is the stronger evidence -- a trend across
    # 0.1 -> 0.3 -> 0.5 cannot be produced by seed noise the way one point can.
    ("topo03_s1", 1, {"topo_weight": 0.3}),
    ("topo03_s2", 2, {"topo_weight": 0.3}),
    ("topo05", 0, {"topo_weight": 0.5}),
    ("topo05_s1", 1, {"topo_weight": 0.5}),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def write_config(arm: str, seed: int, overrides: dict) -> Path:
    cfg = yaml.safe_load(BASE_CFG.read_text(encoding="utf-8"))
    cfg = copy.deepcopy(cfg)
    # Top-level seed stays 0: it also selects the random training rungs, and
    # every arm must train on the SAME data for the comparison to mean
    # anything. train.seed moves initialization/shuffling only.
    cfg["train"]["seed"] = seed
    cfg["train"].update(overrides)
    cfg["train"]["checkpoint"] = f"artifacts/hparam/{arm}/score_net.pt"
    cfg["train"]["history"] = f"artifacts/hparam/{arm}/history.json"
    # Data is reused verbatim from the v2 ensembles; no arm regenerates it.
    path = WORK / arm / "config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def run_arm(arm: str, seed: int, overrides: dict) -> tuple[str, bool, float]:
    # Idempotent: an arm with its ESS result on disk is finished, so a restart
    # after an interruption does not redo completed work.
    if (WORK / arm / "ess" / "ess_results.json").exists():
        log(f"{arm}: SKIP (already complete)")
        return arm, True, 0.0
    cfg = write_config(arm, seed, overrides)
    rel = str(cfg.relative_to(REPO)).replace("\\", "/")
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_DEVICE": "cuda"}
    t0 = time.time()
    log(f"{arm}: START ({overrides or 'baseline'}, seed {seed})")
    LOGDIR.mkdir(parents=True, exist_ok=True)
    with open(LOGDIR / f"hparam_{arm}.log", "w", encoding="utf-8") as fh:
        steps = [
            # --resume is a no-op when no .resume snapshot exists, and picks up
            # from the last 5-epoch snapshot when one does, so an interrupted
            # arm costs at most 5 epochs rather than the whole run.
            [PY, str(SCRIPTS / "02_train.py"), "--config", rel, "--resume"],
            [PY, str(SCRIPTS / "15_model_ess.py"), "--config", rel,
             "--checkpoint", f"artifacts/hparam/{arm}/score_net.pt",
             "--cases", *CASES, "--n-configs", "64",
             "--out", f"artifacts/hparam/{arm}/ess"],
        ]
        for cmd in steps:
            rc = subprocess.run(cmd, cwd=REPO, env=env, stdout=fh,
                                stderr=subprocess.STDOUT).returncode
            if rc != 0:
                dt = (time.time() - t0) / 60
                log(f"{arm}: FAILED rc={rc} in {Path(cmd[1]).name} ({dt:.1f} min)")
                return arm, False, dt
    dt = (time.time() - t0) / 60
    log(f"{arm}: DONE ({dt:.1f} min)")
    return arm, True, dt


def report() -> None:
    import statistics
    rows = {}
    for arm, seed, ov in ARMS:
        p = WORK / arm / "ess" / "ess_results.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        cases = j if isinstance(j, list) else j.get("cases", [j])
        spreads = {}
        for c in cases:
            if not isinstance(c, dict):
                continue
            key = f"{c.get('fine_L')}:{round(c.get('fine_beta', 0), 1)}"
            std = c.get("log_weight_std", c.get("log_weight_std_fiber"))
            if std is not None:
                spreads[key] = std
        rows[arm] = {"overrides": ov, "seed": seed, "spreads": spreads}
    if not rows:
        print("no ess.json yet")
        return

    keys = sorted({k for r in rows.values() for k in r["spreads"]})
    print("\nfiber log-weight std (lower is better)\n")
    print("| arm | change | " + " | ".join(keys) + " | geo mean |")
    print("|---|---|" + "---|" * (len(keys) + 1))
    geo = {}
    for arm, r in rows.items():
        vals = [r["spreads"].get(k) for k in keys]
        got = [v for v in vals if v]
        g = statistics.geometric_mean(got) if got else float("nan")
        geo[arm] = g
        change = ", ".join(f"{k}={v}" for k, v in r["overrides"].items()) or "(baseline)"
        cells = " | ".join("--" if v is None else f"{v:.1f}" for v in vals)
        print(f"| {arm} | {change} | {cells} | {g:.1f} |")

    bases = [geo[a] for a in ("base_s0", "base_s1", "base_s2") if a in geo]
    if len(bases) < 2:
        print("\n(need >=2 baseline seeds for the noise floor)")
        return
    lo, hi = min(bases), max(bases)
    print(f"\nbaseline seed spread (the noise floor): {lo:.1f}-{hi:.1f} "
          f"(ratio {hi / lo:.2f}x)")
    clears = [a for a, g in geo.items()
              if not a.startswith("base_") and (g < lo or g > hi)]
    print("knobs outside the baseline seed range: "
          + (", ".join(clears) if clears else "NONE -- every knob is inside seed noise"))
    out = REPO / "out" / "u1_2d" / "hparam_sweep.json"
    out.write_text(json.dumps({
        "arms": rows, "geo_mean": geo,
        "baseline_range": [lo, hi], "outside_noise": clears,
    }, indent=2), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="summarize, run nothing")
    args = ap.parse_args()
    if args.report:
        report()
        return
    log(f"HPARAM_START: {len(ARMS)} arms, {WORKERS} concurrent")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(run_arm, *a) for a in ARMS]
        results = [f.result() for f in futs]
    bad = [a for a, ok, _ in results if not ok]
    log(f"wall clock {(time.time() - t0) / 60:.1f} min")
    log(f"HPARAM_DONE_WITH_ERRORS: {bad}" if bad else "HPARAM_DONE")
    report()


if __name__ == "__main__":
    main()
