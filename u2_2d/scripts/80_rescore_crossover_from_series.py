"""Rewrite the crossover-scan records for a checkpoint from its SAVED SERIES,
under the CURRENT relaxation-time estimator. No HMC.

WHY THIS EXISTS. The absolute chi2/dof goodness-of-fit veto was added to
`fit_joint_relaxation_time` on 2026-09-06. The `wide_dense` matrix was run
after it; `default` (09-03/09-04), `cov60` (09-03/09-04) and `wide` (09-05)
were all run BEFORE it. So the four checkpoints the paper compares on one
axis were scored by two different estimators -- exactly the methodology drift
CLAUDE.md's standing rule forbids, and in the direction that matters: the
veto turns some "resolved" fits into BAD-FIT, so the pre-veto checkpoints'
resolved counts are biased HIGH relative to wide_dense's.

IT IS NOT ENOUGH TO REFIT `t_therm`. The veto can flip a cold arm from a
finite tau to BAD-FIT, and `cold_ok` gates which chain supplies the
decorrelation interval:

    cold_ok -> interval_source -> interval -> cost_efficiency

so a record whose cold arm fails the veto changes its DENOMINATOR too, and
every cost-efficiency-derived claim (the sign tests, the gap correlation)
moves with it. This script therefore reruns the whole downstream selection,
not just the fit, reusing the stored `tau_int_plaquette` (which the veto does
not touch).

Originals are moved to `<tag>_preveto/` rather than overwritten.

    python u2_2d/scripts/80_rescore_crossover_from_series.py --tags default cov60 wide
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from importlib import import_module
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
scan = import_module("28_crossover_scan")

from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact

NAMES = ("plaquette", "wilson_2x2", "wilson_4x4")
ARMS = ("diffusion seed", "cold start", "hot start")
ROOT = Path("out/u2_2d/coverage_scan_relaxation")
STEMS = ["crossover", "crossover_topo", "crossover_L64", "crossover_L64_topo"]


def series_path(tag: str, stem: str, beta: float) -> Path:
    return ROOT / tag / "series" / f"{stem}_beta{beta:g}.npz"


def rescore(tag: str) -> dict:
    stats = {"records": 0, "refit": 0, "t_therm_changed": 0,
             "interval_source_changed": 0, "missing_series": 0}
    for stem in STEMS:
        p = ROOT / tag / f"{stem}.json"
        if not p.exists():
            continue
        records = json.loads(p.read_text(encoding="utf-8"))
        for rec in records:
            stats["records"] += 1
            beta, size = float(rec["beta"]), int(rec["lattice_size"])
            sp = series_path(tag, stem, beta)
            if not sp.exists():
                stats["missing_series"] += 1
                continue
            d = np.load(sp)
            record_every = int(d["record_every"])
            targets = {"plaquette": plaquette_exact(beta, size),
                       "wilson_2x2": wilson_loop_exact(beta, 4),
                       "wilson_4x4": wilson_loop_exact(beta, 16)}
            before = dict(rec["t_therm"])
            for arm in ARMS:
                key = f"{arm}__{NAMES[0]}"
                if key not in d:
                    continue
                series = {n: d[f"{arm}__{n}"] for n in NAMES}
                fit = scan.fit_joint_relaxation_time(
                    series, targets, record_every, names=NAMES)
                tau = fit["tau"]
                rec["t_therm"][arm] = tau
                rec.setdefault("t_therm_err", {})[arm] = fit["tau_err"]
                rec.setdefault("t_therm_chi2_per_dof", {})[arm] = fit["chi2_per_dof"]
                rec.setdefault("t_therm_fit_quality_ok", {})[arm] = fit["fit_quality_ok"]
            stats["refit"] += 1
            if any(_differs(before.get(a), rec["t_therm"].get(a)) for a in ARMS):
                stats["t_therm_changed"] += 1

            # Rerun the interval selection exactly as 28_crossover_scan does.
            n_traj = int(rec.get("n_traj", 0))
            cold = rec["t_therm"]["cold start"]
            taus = rec.get("tau_int_plaquette", {})
            cold_ok = (isinstance(cold, (int, float)) and math.isfinite(cold)
                       and cold < 0.5 * n_traj and taus.get("cold start"))
            source = "cold start" if cold_ok else "diffusion seed"
            old_source = rec.get("interval_source")
            tau_int = taus.get(source)
            rec["interval_source"] = source
            rec["interval"] = 2.0 * tau_int if tau_int else None
            if old_source != source:
                stats["interval_source_changed"] += 1
        p.write_text(json.dumps(records, indent=1), encoding="utf-8")
    return stats


def _differs(a, b) -> bool:
    fa = isinstance(a, float) and math.isnan(a)
    fb = isinstance(b, float) and math.isnan(b)
    if fa or fb:
        return fa != fb
    if a is None or b is None:
        return a is not b
    if math.isinf(a) or math.isinf(b):
        return a != b
    return abs(a - b) > 1e-6 * max(1.0, abs(a))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tags", nargs="+", default=["default", "cov60", "wide"])
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    for tag in args.tags:
        src = ROOT / tag
        if not src.exists():
            print(f"{tag}: no such directory, skipped")
            continue
        if not args.no_backup:
            bak = ROOT / f"{tag}_preveto"
            if not bak.exists():
                bak.mkdir(parents=True)
                for f in src.glob("*.json"):
                    shutil.copy2(f, bak / f.name)
                (bak / "README.md").write_text(
                    f"# {tag} scored under the PRE-VETO estimator\n\n"
                    "Kept verbatim as the record of what was scored before the\n"
                    "absolute chi2/dof goodness-of-fit veto (2026-09-06) was\n"
                    "applied. Superseded by the files one directory up; do not\n"
                    "quote these.\n", encoding="utf-8")
                print(f"{tag}: originals backed up to {bak}")
        s = rescore(tag)
        print(f"{tag}: {s['refit']}/{s['records']} records refit, "
              f"t_therm changed on {s['t_therm_changed']}, "
              f"interval source changed on {s['interval_source_changed']}, "
              f"missing series {s['missing_series']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
