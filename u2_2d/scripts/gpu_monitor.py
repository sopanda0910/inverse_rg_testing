"""Sample the GPU's live CUDA contexts, attribute each to a script, and log
whenever this project exceeds its measured ceiling of three.

WHY. CLAUDE.md's three-context limit was documented but never OBSERVED: the
only way anyone learned it had been breached was a job dying with
CUDNN_STATUS_EXECUTION_FAILED_CUDART or a CUDA OOM, minutes-to-hours after
the fact and usually killing the most expensive job rather than the one that
caused the overage. This turns that into a timestamped record.

It reports OURS and FOREIGN separately on purpose. The card is shared with
other projects on this machine, and a foreign context consumes memory this
project cannot plan around -- but it is also not something this project may
kill, so conflating the two would produce an alarm with no available action.
The cap applies to ours; foreign contexts are reported as context.

    .venv/Scripts/python.exe u2_2d/scripts/gpu_monitor.py --interval 120
"""
from __future__ import annotations

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Markers that identify a process as belonging to THIS project. The
# obvious test -- does the command line contain the project directory --
# FAILS, and did: wrappers launch the interpreter by a relative path
# (`.venv\Scripts\python.exe u2_2d\scripts\03_run_ladder.py`), so the
# project path never appears, and `ExecutablePath` resolves to the base
# interpreter the venv points at, not to anything under the project. The
# package directory in the script path is the one part always present.
PROJECT_MARKERS = ("inverse_rg_testing", "u1_2d", "u2_2d")


def is_ours(cmd: str) -> bool:
    return any(m in cmd for m in PROJECT_MARKERS)


def project_contexts() -> tuple[list, list]:
    """(ours, foreign) as [(pid, label)], from live CUDA contexts. Shared with
    `gpu_slots.py`, which needs the same answer to count occupancy honestly."""
    table = cmdlines()
    ours, foreign = [], []
    for pid in compute_pids():
        cmd = table.get(pid, "")
        (ours if is_ours(cmd) else foreign).append((pid, label_for(cmd)))
    return ours, foreign


def compute_pids() -> list[int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def memory() -> tuple[float, float, float]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30).stdout.strip().split(",")
        return float(out[0]), float(out[1]), float(out[2])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return float("nan"), float("nan"), float("nan")


def cmdlines() -> dict[int, str]:
    """PID -> command line, via CIM. Needed because nvidia-smi reports only a
    PID, and 'which job is the 5th context' is the whole question here."""
    ps = ("Get-CimInstance Win32_Process | "
          "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for line in out.splitlines():
        pid, _, cmd = line.partition("\t")
        if pid.strip().isdigit():
            table[int(pid.strip())] = cmd.strip()
    return table


def label_for(cmd: str) -> str:
    for token in cmd.replace("\\", "/").split():
        if "/scripts/" in token and token.endswith(".py"):
            return token.rsplit("/", 1)[-1]
    return cmd[:60] if cmd else "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=float, default=120.0)
    ap.add_argument("--cap", type=int, default=3)
    ap.add_argument("--log", default="out/u2_2d/gpu_monitor.log")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    log = Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    while True:
        ours, foreign = project_contexts()
        used, total, util = memory()
        flag = "OVER-CAP" if len(ours) > args.cap else "ok"
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (f"{stamp} {flag:<8} ours={len(ours)}/{args.cap} foreign={len(foreign)} "
                f"mem={used:.0f}/{total:.0f}MiB util={util:.0f}% | "
                + "; ".join(f"{p}:{l}" for p, l in ours + foreign))
        with open(log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line, flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
