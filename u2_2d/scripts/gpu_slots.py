"""A MACHINE-WIDE GPU slot semaphore, and a wrapper that holds one slot for
the lifetime of a command.

WHY THIS EXISTS. CLAUDE.md records, measured, that this 8 GiB card holds
THREE CUDA contexts of this workload and not four. That ceiling was being
enforced in exactly one place -- `60_run_full_relaxation_matrix.py --budget
N` -- which counts only ITS OWN children. Every other GPU job on this
machine is launched by a separate wrapper that does no slot accounting at
all, so the ceiling was routinely exceeded without anything noticing.

The concrete failure (2026-09-06, five contexts live at once): the
relaxation orchestrator held 2, the rung1 benchmark held 1, and
`run_L128_chain.ps1` added a 4th because its gate was "wait for PID 29128 to
exit" -- a SPECIFIC PROCESS, not a free slot. That gate fired correctly by
its own logic: rung0's worker did exit. But the slot it freed had already
been taken by rung1, so waiting on it bought nothing. A per-process gate
cannot express "wait until the machine has room"; only a shared counter can.
The L=128 job is the one that had already died once under contention
(CUDNN_STATUS_EXECUTION_FAILED_CUDART), so it was also the likeliest
casualty of the overage it caused.

USE IT FOR EVERY GPU JOB:

    .venv/Scripts/python.exe u2_2d/scripts/gpu_slots.py --label L128 -- \
        .venv/Scripts/python.exe u2_2d/scripts/03_run_ladder.py ...

`status` prints who holds what; `--cap` overrides the ceiling.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SLOT_DIR = Path("out/u2_2d/.gpu_slots")
MUTEX = SLOT_DIR / "acquire.lock"
DEFAULT_CAP = 3
MUTEX_STALE_SECONDS = 60.0


def _alive(pid: int) -> bool:
    """Is this PID still running? Windows has no signal-0, so ask tasklist.
    A holder file whose process is gone must not keep a slot reserved -- a
    killed job would otherwise wedge the semaphore permanently."""
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True, timeout=15).stdout
        return str(pid) in out
    except (OSError, subprocess.SubprocessError):
        return True  # fail closed: assume alive rather than double-book a slot


def _holders() -> list[dict]:
    SLOT_DIR.mkdir(parents=True, exist_ok=True)
    live = []
    for f in sorted(SLOT_DIR.glob("*.slot")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            f.unlink(missing_ok=True)
            continue
        if _alive(int(rec["pid"])):
            live.append(rec)
        else:
            f.unlink(missing_ok=True)
    return live


class _Mutex:
    """Exclusive create as a mutex around the check-and-create. Without it two
    waiters can both observe `len(holders) < cap` and both take the last slot."""

    def __enter__(self):
        while True:
            try:
                fd = os.open(MUTEX, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    age = time.time() - MUTEX.stat().st_mtime
                except OSError:
                    continue
                if age > MUTEX_STALE_SECONDS:
                    MUTEX.unlink(missing_ok=True)
                    continue
                time.sleep(0.4)

    def __exit__(self, *exc):
        MUTEX.unlink(missing_ok=True)
        return False


def observed_contexts() -> int:
    """How many CUDA contexts this project actually has on the card right now.

    THE SLOT FILES ALONE ARE NOT A SUFFICIENT COUNT, and assuming they were
    defeated this semaphore the first time it ran (2026-09-06). Three GPU jobs
    were already running when it was introduced; none of them holds a slot,
    because they were launched before it existed and cannot be retrofitted
    without restarting them and losing hours of work. So a fresh job saw
    "0/3 held", acquired slot 1, and started -- taking the card straight back
    to four contexts, the exact overage the semaphore was added to prevent.

    Counting real contexts makes the ceiling hold over jobs that never opted
    in. Occupancy is the MAX of the two counts, not the sum: a participating
    job appears in both (its wrapper holds the file, its child owns the
    context) and must not be charged twice.
    """
    try:
        from gpu_monitor import project_contexts
        return len(project_contexts()[0])
    except Exception:
        return 0  # never let a monitoring failure block a job outright


def acquire(label: str, cap: int, poll: float) -> Path:
    SLOT_DIR.mkdir(parents=True, exist_ok=True)
    announced = False
    while True:
        with _Mutex():
            held = _holders()
            occupancy = max(len(held), observed_contexts())
            if occupancy < cap:
                path = SLOT_DIR / f"{os.getpid()}.slot"
                path.write_text(json.dumps(
                    {"pid": os.getpid(), "label": label, "since": time.time()}),
                    encoding="utf-8")
                print(f"gpu_slots: acquired slot {occupancy + 1}/{cap} for {label} "
                      f"(files={len(held)}, live contexts={observed_contexts()})",
                      flush=True)
                return path
        if not announced:
            names = ", ".join(h["label"] for h in held) or "no slot files"
            print(f"gpu_slots: {label} waiting -- occupancy {occupancy}/{cap} "
                  f"(slot files: [{names}]; live project contexts: "
                  f"{observed_contexts()})", flush=True)
            announced = True
        time.sleep(poll)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", default="unnamed")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--poll", type=float, default=30.0)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    if args.status:
        held = _holders()
        print(f"occupancy {max(len(held), observed_contexts())}/{args.cap} "
              f"({len(held)} slot files, {observed_contexts()} live contexts)")
        for h in held:
            print(f"  pid {h['pid']:>6}  {h['label']:<24} "
                  f"{(time.time() - h['since']) / 60:.0f} min")
        return 0

    cmd = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not cmd:
        print("nothing to run; pass a command after --")
        return 2

    slot = acquire(args.label, args.cap, args.poll)
    try:
        return subprocess.run(cmd).returncode
    finally:
        slot.unlink(missing_ok=True)
        print(f"gpu_slots: released slot for {args.label}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
