"""Orchestrates the full coverage/volume matrix (6 checkpoints x 2 volumes x
2 rounds = 24 jobs) under the new exponential-relaxation-time thermalization
definition (28_crossover_scan.py's fit_relaxation_time), replacing the old
discrete threshold-crossing t_therm entirely. This is a full RE-RUN, not a
reanalysis: tonight's earlier runs did not save raw per-trajectory series, so
the new definition cannot be applied retroactively to them (28 now saves
series going forward, under out-dir/series/, precisely so this never has to
happen again).

Writes to a FRESH directory (out/u2_2d/coverage_scan_relaxation/), not the
old out/u2_2d/coverage_scan/ or out/u2_2d/crossover/ -- deliberately, so
there is no risk of this run's completion checks being confused by files
written under the old t_therm definition.

SINGLE PYTHON ORCHESTRATOR managing internal concurrency via
subprocess.Popen, not multiple PowerShell scheduled tasks. Deliberately
simpler than the earlier multi-task approach after two real incidents
tonight where Stop-ScheduledTask / Unregister-ScheduledTask failed to
actually kill the python.exe child, leaving orphaned duplicate work running
unsupervised. This script owns its children directly (they are its own
subprocesses, not separately scheduled), so stopping THIS process's task
via Task Scheduler kills the whole tree cleanly -- verified: Popen children
are OS children of this interpreter, unlike a `& python ...` call from a
separate PowerShell script instance.

    python u2_2d/scripts/60_run_full_relaxation_matrix.py --budget 3
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

CHECKPOINTS = {
    "cov60": "out/u2_2d/checkpoints/det_score_net_cov60.pt",
    "default": "out/u2_2d/checkpoints/det_score_net.pt",
    "cov30": "out/u2_2d/checkpoints/det_score_net_cov30.pt",
    "cov15": "out/u2_2d/checkpoints/det_score_net_cov15.pt",
    "v2": "out/u2_2d/checkpoints/det_score_net_v2.pt",
    "cap": "out/u2_2d/checkpoints/det_score_net_cap.pt",
}
# Decision-critical pair first (cov60 vs default settles the coverage-cap
# question), then the rest of the coverage ablation, then the two lowest-
# priority/widest-data checkpoints last -- same priority reasoning as
# tonight's earlier (now superseded) queue.
PRIORITY = ["cov60", "default", "cov30", "cov15", "v2", "cap"]
OUT_ROOT = Path("out/u2_2d/coverage_scan_relaxation")
MAX_RETRIES = 2


def n_couplings_for(size: int) -> int:
    return 14 if size == 32 else 8


def job_id(tag: str, size: int, topo: bool) -> str:
    return f"{tag}_L{size}_{'topo' if topo else 'plain'}"


def stem_for(size: int, topo: bool) -> str:
    suffix = "" if size == 32 else f"_L{size}"
    return f"crossover{suffix}{'_topo' if topo else ''}"


def out_path(tag: str, size: int, topo: bool) -> Path:
    return OUT_ROOT / tag / f"{stem_for(size, topo)}.json"


def is_done(tag: str, size: int, topo: bool) -> bool:
    p = out_path(tag, size, topo)
    if not p.exists():
        return False
    try:
        return len(json.loads(p.read_text(encoding="utf-8"))) >= n_couplings_for(size)
    except (json.JSONDecodeError, OSError):
        return False


def build_jobs() -> list[tuple[str, int, bool]]:
    # L=32 before L=64 within a checkpoint: cheaper, faster feedback, and
    # matches the couplings the existing fig59 already reads.
    return [(tag, size, topo)
            for tag in PRIORITY for size in (32, 64) for topo in (False, True)]


def launch(job: tuple[str, int, bool], py: str, log_dir: Path):
    tag, size, topo = job
    stem = stem_for(size, topo)
    out_dir = OUT_ROOT / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [py, "u2_2d/scripts/28_crossover_scan.py",
           "--checkpoint", CHECKPOINTS[tag],
           "--fine-size", str(size),
           "--n-chains", "64",
           "--n-couplings", str(n_couplings_for(size)),
           "--out-dir", str(out_dir),
           "--tag", stem]
    if topo:
        cmd.append("--topological-updates")
    log_path = log_dir / f"{job_id(*job)}.log"
    log_f = open(log_path, "a", encoding="utf-8")
    log_f.write(f"\n=== launch {time.ctime()}: {' '.join(cmd)} ===\n")
    log_f.flush()
    proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)
    return proc, log_f


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=3,
                        help="max concurrent GPU-bound jobs (CLAUDE.md's documented ceiling for this card)")
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()

    py = str(Path(".venv/Scripts/python.exe").resolve())
    log_dir = OUT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    status_path = OUT_ROOT / "status.log"
    failed_path = OUT_ROOT / "failed.log"

    jobs = build_jobs()
    retries: dict[tuple, int] = {}
    active: dict[tuple, tuple] = {}
    failed: list[tuple] = []
    done = [j for j in jobs if is_done(*j)]
    pending = [j for j in jobs if j not in done]

    def write_status():
        lines = [f"tick {time.ctime()}",
                 f"done: {len(done)}/{len(jobs)}  failed: {len(failed)}  "
                 f"active: {len(active)}  pending: {len(pending)}"]
        for j, (proc, _, t0) in active.items():
            lines.append(f"  RUNNING {job_id(*j)}  {time.time() - t0:.0f}s")
        for j in pending:
            lines.append(f"  queued  {job_id(*j)}")
        for j in failed:
            lines.append(f"  FAILED  {job_id(*j)} (exhausted {MAX_RETRIES} retries)")
        status_path.write_text("\n".join(lines), encoding="utf-8")
        print(lines[1], flush=True)

    while pending or active:
        for j in list(active):
            proc, log_f, t0 = active[j]
            if proc.poll() is not None:
                log_f.close()
                if proc.returncode == 0 and is_done(*j):
                    done.append(j)
                else:
                    retries[j] = retries.get(j, 0) + 1
                    msg = (f"{time.ctime()} [{job_id(*j)}] exited "
                           f"{proc.returncode}, attempt {retries[j]}/{MAX_RETRIES}")
                    if retries[j] > MAX_RETRIES:
                        failed.append(j)
                        with open(failed_path, "a", encoding="utf-8") as f:
                            f.write(msg + " -- giving up\n")
                    else:
                        pending.append(j)
                        with open(failed_path, "a", encoding="utf-8") as f:
                            f.write(msg + " -- requeuing\n")
                del active[j]
        while pending and len(active) < args.budget:
            j = pending.pop(0)
            if is_done(*j):
                done.append(j)
                continue
            proc, log_f = launch(j, py, log_dir)
            active[j] = (proc, log_f, time.time())
        write_status()
        if pending or active:
            time.sleep(args.poll_seconds)

    write_status()
    print(f"ALL JOBS ATTEMPTED: {len(done)} done, {len(failed)} failed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
