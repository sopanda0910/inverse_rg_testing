"""Waits for the v2 campaign to finish, then decides whether to launch the
norm ablation based on the seed-2 evidence.

Decision rule (written to out/u1_2d/ablation_decision.md either way):
the seed-1 study showed a mid-beta Wilson-loop undershoot (negative plaquette z
concentrated at target beta in [10, 60]). The seed-2 shard runs the E/F cases
with independent noise; the undershoot is CONFIRMED -- and the ablation chain
launched -- when, over seed-2 cases with 10 <= beta_f <= 60:
    mean signed plaquette z <= -0.6,  or  >= 2 cases have z <= -2.
Otherwise the regression is attributed to seed noise and nothing is launched.

Run detached; polls every 5 minutes, gives up after 36 h.

    .venv/Scripts/python.exe u1_2d/scripts/ablation_watcher.py [--check-now]
"""

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out" / "u1_2d"
RUN_LOG = OUT / "run.log"
S2_SUMMARY = OUT / "generalization" / "seeds" / "s2" / "summary.json"
DECISION = OUT / "ablation_decision.md"
LAUNCH_CMD = REPO / "u1_2d" / "scripts" / "launch_ablation.cmd"


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def chain_finished() -> bool:
    if not RUN_LOG.exists():
        return False
    text = RUN_LOG.read_text(encoding="utf-8", errors="replace")
    return "CHAIN_DONE" in text  # matches CHAIN_DONE_WITH_ERRORS too


def get_plaq_z(record: dict):
    for row in record.get("rows", []):
        if str(row.get("observable", "")).lower().startswith("plaquette"):
            z = row.get("z_exact")
            if z is not None and math.isfinite(z):
                return z
    return None


def evaluate() -> tuple[bool, str]:
    if not S2_SUMMARY.exists():
        return False, "seed-2 summary missing -- inconclusive, NOT launching ablation."
    records = json.loads(S2_SUMMARY.read_text(encoding="utf-8"))
    band = []
    for cid, rec in records.items():
        if "rows" not in rec:
            continue
        beta_f = float(rec.get("target_beta", 0))
        if 10.0 <= beta_f <= 60.0:
            z = get_plaq_z(rec)
            if z is not None:
                band.append((cid, beta_f, z))
    if len(band) < 3:
        return False, (f"only {len(band)} seed-2 cases in the 10<=beta_f<=60 band "
                       "-- inconclusive, NOT launching ablation.")
    zs = [z for _, _, z in band]
    mean_z = sum(zs) / len(zs)
    n_low = sum(1 for z in zs if z <= -2.0)
    detail = "\n".join(f"  {cid}: beta_f={b:g}, plaq z={z:+.2f}" for cid, b, z in band)
    confirmed = mean_z <= -0.6 or n_low >= 2
    verdict = "CONFIRMED -> launching norm ablation" if confirmed else \
              "NOT confirmed (seed noise) -> not launching"
    report = (f"mid-beta band ({len(band)} cases): mean plaq z = {mean_z:+.2f}, "
              f"{n_low} cases at z <= -2\n{detail}\n{verdict}")
    return confirmed, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-now", action="store_true",
                        help="evaluate immediately and exit (no waiting, no launch)")
    args = parser.parse_args()
    if args.check_now:
        confirmed, report = evaluate()
        print(report)
        return

    log(f"ablation watcher armed; waiting for CHAIN_DONE in {RUN_LOG}")
    deadline = time.time() + 36 * 3600
    while time.time() < deadline:
        if chain_finished():
            break
        time.sleep(300)
    else:
        DECISION.write_text("watcher timed out after 36 h; no decision made.\n",
                            encoding="utf-8")
        log("watcher timeout")
        sys.exit(1)

    log("campaign finished; evaluating seed-2 evidence")
    confirmed, report = evaluate()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    DECISION.write_text(f"# Ablation decision ({stamp})\n\n{report}\n", encoding="utf-8")
    log(report.replace("\n", " | "))
    if confirmed:
        log(f"launching {LAUNCH_CMD}")
        subprocess.Popen(["cmd.exe", "/c", str(LAUNCH_CMD)],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    log("watcher done")


if __name__ == "__main__":
    main()
