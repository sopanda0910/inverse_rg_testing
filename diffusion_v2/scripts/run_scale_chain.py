"""Capacity/data scale-up chain for the ESS gap: data -> train -> RKL -> verify.

Stages (sentinels in OUT/ess_chain/scale_state/, resumable):

  DATA         01_generate_data.py --config v3_scale.yaml (skips the 82
               existing v2 ensembles; generates only the 24 new L=32 rungs)
  TRAIN        02_train.py --config v3_scale.yaml -- fresh hidden-80/depth-5
               model -> checkpoints/score_net_big.pt (v2 checkpoint untouched)
  VERIFY_BASE  19_ode_reweighting.py with the big checkpoint (4 std cases)
  RKL          22_multicase_rkl.py from the big checkpoint (all 08-01 guards)
               -> score_net_big_rkl.pt (saved only on guarded improvement)
  VERIFY_RKL   19_ode_reweighting.py with big_rkl (skipped if never saved)
  REPORT       scale_report.md: rkl2 (small net) vs big base vs big+RKL

    .venv/Scripts/python.exe diffusion_v2/scripts/run_scale_chain.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "diffusion_v2" / "scripts"
V2OUT = REPO / "out" / "diffusion_v2"
OUT = V2OUT / "ess_chain"
STATE = OUT / "scale_state"
CONFIG = "diffusion_v2/configs/v3_scale.yaml"
CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], critical: bool = True) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {' '.join(cmd)}")
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env={**os.environ, "PYTHONUNBUFFERED": "1"}).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("CHAIN_FAILED (critical stage)")
        sys.exit(1)
    return False


def write_report() -> None:
    variants = [
        ("multi-case RKL, small net (rkl2)", OUT / "verify_rkl2" / "reweighting_results.json"),
        ("big net, DSM only", OUT / "verify_big_base" / "reweighting_results.json"),
        ("big net + multi-case RKL", OUT / "verify_big_rkl" / "reweighting_results.json"),
    ]
    lines = [
        "# Capacity/data scale-up report",
        "",
        "hidden 56->80, depth 4->5, +24 L=32 rungs; all verifications are",
        "fresh-seed script-19 runs (n = 64, sigma-min-coef 0.03).",
        "",
        "| variant | case | ESS/N (fiber) | log-w std (fiber) | i-MH acc |",
        "|---------|------|---------------|-------------------|----------|",
    ]
    for name, f in variants:
        if not f.exists():
            lines.append(f"| {name} | -- | -- | -- | -- |")
            continue
        for r in json.loads(f.read_text()):
            fib = r.get("ess_per_n_fiber")
            std = r.get("log_weight_std_fiber")
            lines.append(
                f"| {name} | {r['fine_L']}:{r['fine_beta']:g} | "
                f"{fib:.4f} | {std:.2f} | {r.get('imh_acceptance', float('nan')):.2f} |"
            )
    (OUT / "scale_report.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"report: {OUT / 'scale_report.md'}")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    big = V2OUT / "checkpoints" / "score_net_big.pt"
    big_rkl = V2OUT / "checkpoints" / "score_net_big_rkl.pt"

    run_stage("DATA", [sys.executable, str(SCRIPTS / "01_generate_data.py"),
                       "--config", CONFIG])
    run_stage("TRAIN", [sys.executable, str(SCRIPTS / "02_train.py"),
                        "--config", CONFIG])
    run_stage("VERIFY_BASE", [
        sys.executable, str(SCRIPTS / "19_ode_reweighting.py"),
        "--config", CONFIG, "--checkpoint", str(big), "--cases", *CASES,
        "--out", str(OUT / "verify_big_base"),
    ])
    run_stage("RKL", [
        sys.executable, str(SCRIPTS / "22_multicase_rkl.py"),
        "--config", CONFIG, "--checkpoint", str(big),
        "--out-checkpoint", str(big_rkl), "--steps", "300",
    ], critical=False)
    if big_rkl.exists():
        run_stage("VERIFY_RKL", [
            sys.executable, str(SCRIPTS / "19_ode_reweighting.py"),
            "--config", CONFIG, "--checkpoint", str(big_rkl), "--cases", *CASES,
            "--out", str(OUT / "verify_big_rkl"),
        ], critical=False)
    else:
        log("RKL never improved under the guards; skipping its verification")

    write_report()
    log("CHAIN_DONE")


if __name__ == "__main__":
    main()
