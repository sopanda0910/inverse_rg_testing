"""Paired chain-resampling bootstrap for cost-efficiency and speedup.

cost_efficiency = interval / max(seed_t, 1), with interval = 2 tau_int and
seed_t the fitted relaxation time. BOTH ingredients are statistical
estimates computed from THE SAME chains, so they are correlated, and the
ratio of two noisy quantities whose denominator can approach zero is
heavy-tailed and asymmetric. Independent Gaussian error propagation is
wrong on both counts. This script instead resamples chains ONCE per
replicate and recomputes both ingredients on that same resample before
forming the ratio, which handles the correlation and the tail shape for
free, and reports how often a replicate lands in the degenerate branches
(seed never converges -> efficiency 0; seed already converged -> capped)
rather than hiding them inside a symmetric error bar.

NOTE ON WHAT THIS DOES NOT COVER: wall-clock ratios (e.g. the
same-endpoint 2.94x of arm G against arm E) are single timing measurements
whose uncertainty is machine jitter, not sampling noise. They cannot be
bootstrapped from physics data and are not touched here; quote them to one
significant figure, or re-time them repeatedly to get a spread.

The `interval_source` (cold chain vs seeded chain) is held FIXED at
whatever the full-data analysis selected, so every replicate estimates the
same quantity rather than silently switching estimand mid-bootstrap.

    python u2_2d/scripts/76_cost_efficiency_errorbars.py --tag wide_dense
"""
from __future__ import annotations

import argparse
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

from u1_2d.validate.stats import integrated_autocorrelation_time
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.model.det_lift import model_beta

NAMES = ("plaquette", "wilson_2x2", "wilson_4x4")
ROOT = Path("out/u2_2d/coverage_scan_relaxation")


def per_chain_tau_int(tail: np.ndarray) -> np.ndarray:
    return np.array([integrated_autocorrelation_time(tail[:, c])[0]
                    for c in range(tail.shape[1])])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tag", default="wide_dense")
    ap.add_argument("--n-boot", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    series_dir = ROOT / args.tag / "series"
    rows = []
    for f in sorted(series_dir.glob("*.npz")):
        m = re.match(r"(crossover(?:_L(\d+))?(_topo)?)_beta([\d.]+)\.npz", f.name)
        if not m:
            continue
        size = int(m.group(2)) if m.group(2) else 32
        topo = bool(m.group(3))
        beta = float(m.group(4))
        d = np.load(f)
        record_every = int(d["record_every"])
        targets = {"plaquette": plaquette_exact(beta, size),
                  "wilson_2x2": wilson_loop_exact(beta, 4),
                  "wilson_4x4": wilson_loop_exact(beta, 16)}

        seed_series = {n: d[f"diffusion seed__{n}"] for n in NAMES}
        cold_series = {n: d[f"cold start__{n}"] for n in NAMES}
        n_records, n_chains = seed_series["plaquette"].shape
        t = np.arange(n_records, dtype=float) * record_every

        # full-data point estimates, and the source choice they imply
        def fit(series_dict, pick=None):
            sub = ({k: v[:, pick] for k, v in series_dict.items()} if pick is not None
                   else series_dict)
            means = {k: v.mean(axis=1) for k, v in sub.items()}
            sems = {k: np.maximum(v.std(axis=1, ddof=1) / math.sqrt(v.shape[1]), 1e-12)
                   for k, v in sub.items()}
            return scan._fit_joint_once(t, means, sems, targets, NAMES)[0]

        seed_full = fit(seed_series)
        cold_full = fit(cold_series)
        cold_tail = cold_series["plaquette"][n_records // 2:]
        seed_tail = seed_series["plaquette"][n_records // 2:]
        cold_taus = per_chain_tau_int(cold_tail)
        seed_taus = per_chain_tau_int(seed_tail)
        cold_ok = (math.isfinite(cold_full) and cold_full < 0.5 * n_records * record_every
                   and np.isfinite(cold_taus).any())
        source = "cold start" if cold_ok else "diffusion seed"
        src_taus = cold_taus if cold_ok else seed_taus

        def ce_from(tau_int_med, seed_t):
            if tau_int_med is None or not np.isfinite(tau_int_med):
                return None
            interval = 2.0 * tau_int_med * record_every
            if seed_t is None or (isinstance(seed_t, float) and math.isnan(seed_t)):
                return None
            if math.isinf(seed_t):
                return 0.0
            return interval / max(seed_t, 1.0)

        finite_full = src_taus[np.isfinite(src_taus)]
        ce_full = ce_from(float(np.median(finite_full)) if len(finite_full) else None,
                         seed_full)

        rng = np.random.default_rng(args.seed)
        boots, n_zero, n_bad = [], 0, 0
        for _ in range(args.n_boot):
            pick = rng.integers(0, n_chains, n_chains)
            st = fit(seed_series, pick)
            rt = src_taus[pick]
            rt = rt[np.isfinite(rt)]
            ce = ce_from(float(np.median(rt)) if len(rt) else None, st)
            if ce is None:
                n_bad += 1
            elif ce == 0.0:
                n_zero += 1
                boots.append(0.0)
            else:
                boots.append(ce)
        arr = np.array(boots, dtype=float)
        lo = float(np.percentile(arr, 2.5)) if len(arr) else float("nan")
        hi = float(np.percentile(arr, 97.5)) if len(arr) else float("nan")
        rows.append({"tag": args.tag, "L": size, "topo": topo, "beta": beta,
                    "model_beta": model_beta(beta), "interval_source": source,
                    "cost_efficiency": ce_full, "ci_lo": lo, "ci_hi": hi,
                    "frac_zero_branch": n_zero / max(args.n_boot, 1),
                    "frac_unusable": n_bad / max(args.n_boot, 1),
                    "n_boot": args.n_boot})
        print(f"L={size:3d} {'topo' if topo else 'plain':5s} mb={model_beta(beta):8.2f}  "
             f"CE={ce_full if ce_full is None else round(ce_full,3)!s:>8s}  "
             f"95% CI [{lo:.3f}, {hi:.3f}]  "
             f"zero-branch {100*n_zero/max(args.n_boot,1):3.0f}%  "
             f"unusable {100*n_bad/max(args.n_boot,1):3.0f}%  src={source}")

    out = Path(args.out or f"out/u2_2d/cost_efficiency_errorbars_{args.tag}.json")
    json.dump(rows, open(out, "w"), default=lambda o: None)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
