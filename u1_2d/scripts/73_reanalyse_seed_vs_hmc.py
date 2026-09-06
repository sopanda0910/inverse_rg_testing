"""u1 twin of `u2_2d/scripts/72_reanalyse_seed_vs_hmc.py`: reanalyse every
saved thermalization series with the chi2/dof-vetoed `fit_relaxation_time`
(ported to u1 2026-09-06, same day as u2's fix -- see
`u1_2d/validate/stats.py`'s `_fit_exp_once` docstring). CPU-only, no HMC
re-run: reads `out/u1_2d/coverage_scan/*/thermalization/*/*_series.npz`.

    python u1_2d/scripts/73_reanalyse_seed_vs_hmc.py
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u1_2d.validate.stats import fit_relaxation_time

NAMES = ("plaquette", "wilson_2x2", "wilson_4x4", "wilson_6x6")
ARMS = ("diffusion seed", "cold start", "hot start")


def targets_for(beta: float, size: int) -> dict:
    return {"plaquette": plaquette_exact(beta, lattice_size=size),
           "wilson_2x2": wilson_loop_exact(beta, 4, lattice_size=size),
           "wilson_4x4": wilson_loop_exact(beta, 16, lattice_size=size),
           "wilson_6x6": wilson_loop_exact(beta, 36, lattice_size=size)}


def status(tau) -> str:
    if tau is None or (isinstance(tau, float) and math.isnan(tau)):
        return "BAD-FIT"
    if math.isinf(tau):
        return "inf"
    return "finite"


def main() -> int:
    files = sorted(glob.glob("out/u1_2d/coverage_scan/*/thermalization/*/*_series.npz"))
    print(f"found {len(files)} series files")
    rows = []
    for f in files:
        m = re.search(r"L(\d+)_beta([\d.]+)_series\.npz$", f)
        if not m:
            continue
        size, beta = int(m.group(1)), float(m.group(2))
        d = np.load(f)
        targets = targets_for(beta, size)
        arm_status = {}
        for arm in ARMS:
            per_obs = {}
            for name in NAMES:
                key = f"{arm}|{name}"
                if key not in d:
                    continue
                tau, err = fit_relaxation_time(d[key], targets[name])
                per_obs[name] = {"tau": None if (isinstance(tau, float) and math.isnan(tau)) else tau,
                                 "err": err, "status": status(tau)}
            if per_obs:
                arm_status[arm] = per_obs
        rows.append({"file": f, "size": size, "beta": beta, "arms": arm_status})

    out_path = Path("out/u1_2d/seed_vs_hmc_reanalysis.json")
    json.dump(rows, open(out_path, "w"))
    print(f"wrote {out_path}")

    counts = {arm: {"finite": 0, "inf": 0, "BAD-FIT": 0} for arm in ARMS}
    for r in rows:
        for arm, per_obs in r["arms"].items():
            for name, info in per_obs.items():
                counts[arm][info["status"]] += 1
    print(f"\n{'arm':<16s} {'finite':>7s} {'inf':>6s} {'BAD-FIT':>8s} {'total':>6s}")
    for arm, c in counts.items():
        tot = sum(c.values())
        print(f"{arm:<16s} {c['finite']:7d} {c['inf']:6d} {c['BAD-FIT']:8d} {tot:6d}  "
             f"({100*c['BAD-FIT']/max(tot,1):.0f}% bad)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
