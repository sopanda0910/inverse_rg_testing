"""A goodness-of-fit test for the relaxation fit with NO invented threshold:
a chain-level residual bootstrap, judged at a conventional significance level.

WHY REPLACE THE chi2/dof CUTOFF. The absolute veto rejects a fit whose
chi2/dof exceeds a fixed number. Calibration showed that number is safe
(0/1600 false rejections at 3 and at 5) and that the real seed and classical
populations do not overlap, so nothing in this project's conclusions turns on
it -- but the number itself is this project's invention, and a fixed cutoff
cannot adapt to a series whose autocorrelation or window length differs.

WHY NOT A NOMINAL chi2 p-VALUE. Records of a Monte Carlo chain are correlated
in simulation time. The per-record errors (taken ACROSS independent chains)
are correct, so E[chi2/dof] = 1 still holds under a correct model, but the
VARIANCE of chi2/dof exceeds the nominal 2/dof -- so a chi2-table tail
probability is miscalibrated, and at several hundred degrees of freedom it
becomes arbitrarily strict (it flagged healthy fits at chi2/dof = 1.20-1.28).

THE TEST. Impose the null by construction and let the data supply the null
distribution:

  1. Fit the model, giving a predicted mean curve.
  2. Form per-chain residuals r_c(t) = x_c(t) - pred(t).
  3. Resample WHOLE CHAINS of residuals with replacement -- which preserves
     each chain's autocorrelation in simulation time exactly, without
     modelling it -- and add them back to the fitted curve. Every replica is
     then a dataset for which the model is true, with this series' own noise
     structure.
  4. Refit each replica and collect chi2/dof.
  5. p = fraction of replicas at least as discrepant as the observed fit.

Reject at a conventional alpha. Chain-level resampling is the same unit used
for every other error bar in this project.

    python u2_2d/scripts/83_bootstrap_gof.py --alpha 0.01
"""
from __future__ import annotations

import argparse
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

NAMES = ("plaquette", "wilson_2x2", "wilson_4x4")
ARMS = ("diffusion seed", "cold start", "hot start")


def fit_chi2(t, series, targets, n_chains):
    m = {n: series[n].mean(axis=1) for n in NAMES}
    s = {n: np.maximum(series[n].std(axis=1, ddof=1) / math.sqrt(n_chains), 1e-12)
         for n in NAMES}
    tau, c_flat, c_fit, ndof, npar = scan._fit_joint_once(t, m, s, targets, NAMES)
    return tau, c_fit / max(ndof - npar, 1), m, s, npar


def bootstrap_p(t, series, targets, tau, npar, n_boot, rng):
    """p-value for the observed chi2/dof under the fitted model."""
    n_chains = series[NAMES[0]].shape[1]
    m = {n: series[n].mean(axis=1) for n in NAMES}
    s = {n: np.maximum(series[n].std(axis=1, ddof=1) / math.sqrt(n_chains), 1e-12)
         for n in NAMES}
    _, _, c_obs, ndof, _ = scan._fit_joint_once(t, m, s, targets, NAMES)
    obs = c_obs / max(ndof - npar, 1)

    # Predicted curve per observable from the observed fit, and per-chain
    # residuals about it.
    pred, resid = {}, {}
    for n in NAMES:
        A = m[n][0] - targets[n]
        pred[n] = targets[n] + A * np.exp(-t / max(tau, 1e-6))
        resid[n] = series[n] - pred[n][:, None]

    null = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, n_chains, n_chains)
        rep = {n: pred[n][:, None] + resid[n][:, pick] for n in NAMES}
        _, c, _, _, _ = fit_chi2(t, rep, targets, n_chains)
        null[b] = c
    return obs, float((np.sum(null >= obs) + 1) / (n_boot + 1)), null


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alpha", type=float, default=0.01)
    ap.add_argument("--n-boot", type=int, default=150)
    ap.add_argument("--tags", nargs="+",
                    default=["default", "cov60", "wide", "wide_dense_frozen"])
    ap.add_argument("--out", default="out/u2_2d/bootstrap_gof.json")
    args = ap.parse_args()

    rng = np.random.default_rng(0)
    rows = []
    for tag in args.tags:
        for f in sorted(glob.glob(
                f"out/u2_2d/coverage_scan_relaxation/{tag}/series/*.npz")):
            beta = float(re.match(r".*_beta([\d.]+)\.npz", f).group(1))
            size = 64 if "_L64" in f else 32
            d = np.load(f)
            re_ = int(d["record_every"])
            targets = {"plaquette": plaquette_exact(beta, size),
                       "wilson_2x2": wilson_loop_exact(beta, 4),
                       "wilson_4x4": wilson_loop_exact(beta, 16)}
            for arm in ARMS:
                if f"{arm}__{NAMES[0]}" not in d:
                    continue
                series = {n: d[f"{arm}__{n}"] for n in NAMES}
                n_rec, n_ch = series[NAMES[0]].shape
                t = np.arange(n_rec, dtype=float) * re_
                tau, chi2dof, _, _, npar = fit_chi2(t, series, targets, n_ch)
                if tau in (0.0,) or math.isinf(tau) or tau != tau:
                    continue
                obs, p, _ = bootstrap_p(t, series, targets, tau, npar,
                                        args.n_boot, rng)
                rows.append({"tag": tag, "arm": arm, "beta": beta, "L": size,
                             "chi2_per_dof": obs, "p": p})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(args.out, "w"), indent=1)

    seed = [r for r in rows if r["arm"] == "diffusion seed"]
    cls = [r for r in rows if r["arm"] != "diffusion seed"]
    print(f"{'arm':<16} {'n':>4} {'reject at alpha':>16} {'chi2/dof>5':>12} {'agree':>7}")
    for lbl, v in (("diffusion seed", seed), ("cold/hot start", cls)):
        rej = sum(1 for r in v if r["p"] < args.alpha)
        old = sum(1 for r in v if r["chi2_per_dof"] > 5.0)
        agree = sum(1 for r in v if (r["p"] < args.alpha) == (r["chi2_per_dof"] > 5.0))
        print(f"{lbl:<16} {len(v):4d} {rej:16d} {old:12d} "
              f"{100*agree/max(len(v),1):6.1f}%")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
