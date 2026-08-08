"""Tier-0 ESS sweep: tune the sampling-time proposal family, no retraining.

The ODE proposal q(x|c) is parameterized by sampling-time knobs (terminal
sigma_min coefficient, exact-score blend, consistency guidance); every setting
yields valid importance weights, so ESS/N can be tuned directly. Each point
invokes 19_ode_reweighting.py on the cheap case (L=16, beta=55.0237) in its
own output dir; finished points (reweighting_results.json present) are
skipped, so the sweep is resumable. Two stability points (8 probes, 240
steps) bound the estimator-noise contribution to the log-weight spread.

    .venv/Scripts/python.exe u1_2d/scripts/run_ode_sweep.py
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "u1_2d" / "scripts" / "19_ode_reweighting.py"
OUT = REPO / "out" / "u1_2d" / "ode_reweighting_sweep"
CASE = "16:55.0237"

POINTS = [
    ("baseline", []),
    ("sigmin0.03", ["--sigma-min-coef", "0.03"]),
    ("sigmin0.01", ["--sigma-min-coef", "0.01"]),
    ("blend2", ["--physics-blend", "2"]),
    ("blend4", ["--physics-blend", "4"]),
    ("cw0", ["--consistency-weight", "0"]),
    ("cw0.5", ["--consistency-weight", "0.5"]),
    ("cw2", ["--consistency-weight", "2"]),
    ("sigmin0.03_blend2", ["--sigma-min-coef", "0.03", "--physics-blend", "2"]),
    ("sigmin0.03_blend4_cw0.5", ["--sigma-min-coef", "0.03", "--physics-blend", "4",
                                 "--consistency-weight", "0.5"]),
    ("sigmin0.01_blend4", ["--sigma-min-coef", "0.01", "--physics-blend", "4"]),
    ("probes8", ["--n-probes", "8"]),
    ("steps240", ["--ode-steps", "240"]),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    # Points are independent and each writes its own OUT/<label>/ directory, so
    # they never contend for a file -- the only shared output, sweep_summary.md,
    # is written after every point is in. Serially this stage leaves the GPU at
    # ~5-30% (one ODE sample at L=16 is far too small to fill it), so running
    # several at once is close to free. Bounded by VRAM, not cores: each job
    # carries its own CUDA context plus the score net, ~0.5-0.7 GiB of 8.
    parser.add_argument("--jobs", type=int, default=4,
                        help="sweep points to run concurrently (default 4)")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    todo = [(label, extra) for label, extra in POINTS
            if not (OUT / label / "reweighting_results.json").exists()]
    for label, _ in POINTS:
        if (label, _) not in todo:
            print(f"[sweep] {label}: cached, skipping", flush=True)

    t_all = time.time()
    running: list[tuple[str, subprocess.Popen, float]] = []
    queue = list(todo)
    while queue or running:
        while queue and len(running) < max(1, args.jobs):
            label, extra = queue.pop(0)
            print(f"[sweep] {label}: {' '.join(extra) or '(defaults)'}", flush=True)
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPT), "--cases", CASE, "--n-configs", "64",
                 "--out", str(OUT / label), *extra],
                cwd=REPO,
            )
            running.append((label, proc, time.time()))
        for entry in list(running):
            label, proc, t0 = entry
            rc = proc.poll()
            if rc is not None:
                print(f"[sweep] {label}: rc={rc} ({time.time() - t0:.0f}s)", flush=True)
                running.remove(entry)
        if running:
            time.sleep(2)
    print(f"[sweep] all points done in {(time.time() - t_all) / 60:.1f} min", flush=True)

    rows = []
    for label, _ in POINTS:
        result_file = OUT / label / "reweighting_results.json"
        if not result_file.exists():
            print(f"[sweep] {label}: no result, omitted from summary", flush=True)
            continue
        rows.append((label, json.loads(result_file.read_text())[0]))

    rows.sort(key=lambda t: -(t[1].get("ess_per_n_fiber") or 0.0))
    lines = [
        f"# Tier-0 proposal sweep (case {CASE}, n=64)",
        "",
        "| point | ESS/N (fiber) | log-w std (fiber) | i-MH acc | ODE s |",
        "|-------|---------------|-------------------|----------|-------|",
    ]
    for label, r in rows:
        lines.append(
            f"| {label} | {r.get('ess_per_n_fiber', float('nan')):.4f} | "
            f"{r.get('log_weight_std_fiber', float('nan')):.2f} | "
            f"{r.get('imh_acceptance', float('nan')):.2f} | "
            f"{r.get('seconds_ode_sample', 0):.0f} |"
        )
    lines += [
        "",
        "probes8 / steps240 are stability points at baseline knobs: if their",
        "log-w std drops materially below baseline, the spread was partly",
        "estimator noise (Hutchinson / discretization), not model density gap.",
    ]
    (OUT / "sweep_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[sweep] wrote {OUT / 'sweep_summary.md'}", flush=True)


if __name__ == "__main__":
    main()
