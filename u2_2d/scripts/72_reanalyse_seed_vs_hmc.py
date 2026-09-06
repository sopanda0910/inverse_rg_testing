"""Reanalyse every saved crossover-scan series with the corrected
`fit_joint_relaxation_time` (chi2 absolute-goodness-of-fit veto added
2026-09-06) and build the three-way comparison the paper actually needs:
diffusion seed vs. STANDARD HMC (plain round, cold/hot start) vs.
WINDING HMC (topo round, cold/hot start).

No HMC is re-run -- this reads the `series/*.npz` files
`28_crossover_scan.py` already saved for every checkpoint, exactly the
reanalysis path those files exist for.

    python u2_2d/scripts/72_reanalyse_seed_vs_hmc.py
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys
from importlib import import_module
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
scan = import_module("28_crossover_scan")

from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.model.det_lift import model_beta

NAMES = ("plaquette", "wilson_2x2", "wilson_4x4")
ROOT = Path("out/u2_2d/coverage_scan_relaxation")
CHECKPOINTS = ["default", "cov60", "wide", "wide_dense"]


def refit(npz_path: Path, beta: float, size: int) -> dict:
    d = np.load(npz_path)
    record_every = int(d["record_every"])
    targets = {"plaquette": plaquette_exact(beta, size),
              "wilson_2x2": wilson_loop_exact(beta, 4),
              "wilson_4x4": wilson_loop_exact(beta, 16)}
    out = {}
    for arm in ("diffusion seed", "cold start", "hot start"):
        series = {name: d[f"{arm}__{name}"] for name in NAMES}
        fit = scan.fit_joint_relaxation_time(series, targets, record_every, names=NAMES)
        out[arm] = fit
    return out


def main() -> int:
    rows = []
    for tag in CHECKPOINTS:
        series_dir = ROOT / tag / "series"
        for f in sorted(series_dir.glob("*.npz")):
            m = re.match(r"(crossover(?:_L(\d+))?(_topo)?)_beta([\d.]+)\.npz", f.name)
            if not m:
                continue
            size = int(m.group(2)) if m.group(2) else 32
            topo = bool(m.group(3))
            beta = float(m.group(4))
            fits = refit(f, beta, size)
            rows.append({"tag": tag, "L": size, "topo": topo, "beta": beta,
                        "model_beta": model_beta(beta), "fits": fits})

    out_path = Path("out/u2_2d/seed_vs_hmc_reanalysis.json")
    json.dump(rows, open(out_path, "w"), default=lambda x: None if isinstance(x, float) and math.isnan(x) else x)
    print(f"wrote {out_path}  ({len(rows)} rows)")

    def fmt(fit):
        t = fit["tau"]
        if not fit.get("fit_quality_ok", True):
            return "BAD-FIT"
        if t is None or (isinstance(t, float) and math.isnan(t)):
            return "BAD-FIT"
        if math.isinf(t):
            return "inf"
        return f"{t:.1f}"

    print(f"\n{'tag':<11s} {'L':>3s} {'round':>6s} {'model_b':>8s}  "
         f"{'seed':>8s} {'plain-cold':>10s} {'plain-hot':>10s} "
         f"{'wind-cold':>10s} {'wind-hot':>10s}")
    # pair plain/topo rows at the matching (tag, L, beta)
    by_key = {}
    for r in rows:
        by_key.setdefault((r["tag"], r["L"], round(r["beta"], 3)), {})[r["topo"]] = r
    for (tag, L, beta), pair in sorted(by_key.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        plain = pair.get(False)
        topo = pair.get(True)
        mb = (plain or topo)["model_beta"]
        seed = fmt((topo or plain)["fits"]["diffusion seed"])
        pc = fmt(plain["fits"]["cold start"]) if plain else "--"
        ph = fmt(plain["fits"]["hot start"]) if plain else "--"
        wc = fmt(topo["fits"]["cold start"]) if topo else "--"
        wh = fmt(topo["fits"]["hot start"]) if topo else "--"
        print(f"{tag:<11s} {L:3d} {'':6s} {mb:8.2f}  {seed:>8s} {pc:>10s} {ph:>10s} {wc:>10s} {wh:>10s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
