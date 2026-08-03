"""Tier-0 ESS sweep: tune the sampling-time proposal family, no retraining.

The ODE proposal q(x|c) is parameterized by sampling-time knobs (terminal
sigma_min coefficient, exact-score blend, consistency guidance); every setting
yields valid importance weights, so ESS/N can be tuned directly. Each point
invokes 19_ode_reweighting.py on the cheap case (L=16, beta=55.0237) in its
own output dir; finished points (reweighting_results.json present) are
skipped, so the sweep is resumable. Two stability points (8 probes, 240
steps) bound the estimator-noise contribution to the log-weight spread.

    .venv/Scripts/python.exe diffusion_v2/scripts/run_ode_sweep.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "diffusion_v2" / "scripts" / "19_ode_reweighting.py"
OUT = REPO / "out" / "diffusion_v2" / "ode_reweighting_sweep"
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
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for label, extra in POINTS:
        point_dir = OUT / label
        result_file = point_dir / "reweighting_results.json"
        if not result_file.exists():
            print(f"[sweep] {label}: {' '.join(extra) or '(defaults)'}", flush=True)
            t0 = time.time()
            rc = subprocess.run(
                [sys.executable, str(SCRIPT), "--cases", CASE, "--n-configs", "64",
                 "--out", str(point_dir), *extra],
                cwd=REPO,
            ).returncode
            print(f"[sweep] {label}: rc={rc} ({time.time() - t0:.0f}s)", flush=True)
            if rc != 0:
                continue
        r = json.loads(result_file.read_text())[0]
        rows.append((label, r))

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
