"""Re-score u1 crossover-window rows from saved per-trajectory series.

Why this exists, and it is the u1 analogue of
`u2_2d/scripts/80_rescore_crossover_from_series.py`.

`u1_2d/validate/stats.py`'s relaxation-time estimator changed on 2026-09-06
(commit 55551a5) and again on 2026-09-07 (d3f4624). The coverage-scan arms in
`out/u1_2d/coverage_scan/` were scored at different times and therefore under
DIFFERENT estimators:

    wide250                     2026-09-03   old
    wide2000                    2026-09-05   old
    wide2000_L16target/*        2026-09-05   old
    wide2000_dense_L16target    2026-09-06 02:50   old
    wide2000_dense_sectorfix    2026-09-08   CURRENT

Comparing a checkpoint scored under one estimator against a checkpoint scored
under another measures the estimator as much as the checkpoint. That mistake was
already made once in u2 and caught; this script exists so it is not repeated in
u1. It re-runs the CURRENT `fit_relaxation_time` over the saved
`*_series.npz`, rebuilds `t_therm` for every arm, and rewrites
`crossover_window.json` using the same row logic as
`35_crossover_window.py` (seed/hot/cold are the SLOWEST of the Wilson
observables; the speedup ratio is against `max(seed, 1)`).

No HMC is re-run: the series were saved precisely so a definition change can be
reanalysed for free. Originals are backed up to `<dir>_preveto/` unless
`--no-backup`.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from u1_2d.lgt import exact  # noqa: E402
from u1_2d.validate.stats import fit_relaxation_time  # noqa: E402

WILSON = ("plaquette", "wilson_2x2", "wilson_4x4")
STARTS = ("diffusion seed", "hot start", "cold start")


def exact_targets(beta: float, action_type: str, lattice_size: int) -> dict[str, float]:
    targets = {"plaquette": exact.plaquette_exact(beta, action_type, lattice_size)}
    for name, (r, t) in {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4),
                         "wilson_6x6": (6, 6)}.items():
        targets[name] = exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)
    chi = exact.topological_susceptibility_exact(beta, action_type, lattice_size)
    targets["Q^2"] = chi * lattice_size * lattice_size
    return targets


def slowest(t_therm: dict, start: str) -> float:
    vals = []
    for n in WILSON:
        v = t_therm.get(start, {}).get(n)
        vals.append(float("inf") if v is None else float(v))
    return max(vals) if vals else float("inf")


def rescore_case(series_path: Path, summary: dict, action_type: str) -> dict:
    data = np.load(series_path, allow_pickle=True)
    targets = exact_targets(summary["beta"], action_type, summary["lattice_size"])
    t_therm: dict[str, dict[str, float]] = {}
    for start in STARTS:
        row = {}
        for name in WILSON:
            key = f"{start}|{name}"
            if key not in data.files:
                continue
            tau, _err = fit_relaxation_time(np.asarray(data[key], dtype=np.float64),
                                            targets[name])[:2]
            row[name] = tau
        if row:
            t_therm[start] = row
    return t_therm


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dirs", nargs="+", required=True,
                    help="coverage_scan arm directories holding thermalization/")
    ap.add_argument("--action-type", default="wilson")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    for d in args.dirs:
        arm = Path(d)
        therm = arm / "thermalization"
        if not therm.is_dir():
            print(f"SKIP {arm}: no thermalization/ subdirectory")
            continue

        out = arm / "crossover_window.json"
        if out.exists() and not args.no_backup:
            bak = arm.parent / (arm.name + "_preveto")
            bak.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out, bak / "crossover_window.json")

        rows, changed = [], 0
        for case in sorted(therm.iterdir()):
            if not case.is_dir():
                continue
            sums = sorted(case.glob("*_summary.json"))
            sers = sorted(case.glob("*_series.npz"))
            if not sums or not sers:
                continue
            summary = json.loads(sums[0].read_text())
            old_seed = slowest(summary.get("t_therm", {}), "diffusion seed")

            t_therm = rescore_case(sers[0], summary, args.action_type)
            seed = slowest(t_therm, "diffusion seed")
            hot = slowest(t_therm, "hot start")
            cold = slowest(t_therm, "cold start")
            best = min(hot, cold)
            ratio = best / max(seed, 1.0)

            finite = [v for v in (hot, cold) if math.isfinite(v)]
            regime = "frozen" if not finite else "mobile"
            rows.append({
                "L": summary["lattice_size"], "beta": summary["beta"],
                "regime": regime, "seed": seed, "hot": hot, "cold": cold,
                "interval": summary.get("hmc_interval_trajectories"),
                "speedup": ratio, "speedup_is_bound": seed == 0,
                "q_frozen": summary.get("q_freezing", {}).get("frozen", True)
                if isinstance(summary.get("q_freezing"), dict)
                else bool(summary.get("q_freezing", True)),
            })
            if not (math.isinf(old_seed) and math.isinf(seed)) and old_seed != seed:
                changed += 1
                print(f"  {summary['label']}: seed {old_seed} -> {seed}")

        rows.sort(key=lambda r: r["beta"])
        out.write_text(json.dumps({"rows": rows}, indent=2))
        n_ok = sum(1 for r in rows if math.isfinite(r["seed"]))
        print(f"{arm.name}: {len(rows)} couplings, seed resolves {n_ok}/{len(rows)}, "
              f"{changed} changed -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
