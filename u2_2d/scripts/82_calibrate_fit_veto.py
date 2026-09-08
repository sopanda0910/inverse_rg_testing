"""Calibrate the absolute goodness-of-fit veto against a SYNTHETIC NULL, so
its threshold is a measured false-rejection rate rather than a round number.

WHY. `fit_joint_relaxation_time` rejects a resolved fit whose
chi2/dof exceeds a threshold. The threshold was chosen by inspection --
healthy fits sat at ~1-3, misspecified ones at 40-9000, so anything in the
gap worked. That is a defensible gap argument and an arbitrary number, and
the number is load-bearing: it decides whether a classical arm reports a
finite relaxation time or none at all.

WHY NOT A p-VALUE. The obvious fix, `chi2.sf(chi2, dof) < alpha`, was tried
first and is wrong here. Successive records of a Monte Carlo chain are
correlated in simulation time, so while the per-record errors (taken ACROSS
independent chains) are correct and E[chi2/dof] = 1 still holds for a
correctly specified model, the VARIANCE of chi2/dof is larger than the
nominal 2/dof. A nominal chi2 tail probability is therefore anticonservative
in its assumptions and, with dof of several hundred, arbitrarily strict in
practice -- it flagged healthy fits at chi2/dof = 1.20-1.28.

WHAT THIS DOES INSTEAD, following the calibration precedent already set for
the sector goodness-of-fit test in `48_verdict_calibration.py`: generate
series for which the exponential model is TRUE BY CONSTRUCTION, with
AR(1) autocorrelation in simulation time matched to what the real chains
show, push them through the identical fitting path, and read the null
distribution of chi2/dof off the result. The threshold is then quotable as a
false-rejection rate.

    python u2_2d/scripts/82_calibrate_fit_veto.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from importlib import import_module
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
scan = import_module("28_crossover_scan")

NAMES = ("plaquette", "wilson_2x2", "wilson_4x4")


def synth(rng, n_rec, n_chains, tau, rho, amp, sigma, target):
    """One arm's series: a true exponential decay toward `target`, plus AR(1)
    noise in simulation time (lag-1 correlation `rho`) that is independent
    across chains -- the real chains' structure, since chains are independent
    replicas but successive records within a chain are not."""
    t = np.arange(n_rec)[:, None]
    signal = target + amp * np.exp(-t / tau)
    noise = np.empty((n_rec, n_chains))
    noise[0] = rng.normal(0.0, sigma, n_chains)
    s = sigma * math.sqrt(max(1.0 - rho * rho, 1e-12))
    for i in range(1, n_rec):
        noise[i] = rho * noise[i - 1] + rng.normal(0.0, s, n_chains)
    return signal + noise


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--replicas", type=int, default=300)
    ap.add_argument("--n-records", type=int, default=75)
    ap.add_argument("--n-chains", type=int, default=64)
    ap.add_argument("--out", default="out/u2_2d/fit_veto_calibration.json")
    args = ap.parse_args()

    targets = {"plaquette": 0.9988, "wilson_2x2": 0.9952, "wilson_4x4": 0.9810}
    sigmas = {"plaquette": 1.2e-5, "wilson_2x2": 4.0e-5, "wilson_4x4": 1.6e-4}
    results = {}
    # rho spans no autocorrelation to strongly correlated records; tau spans
    # fast to slow decays relative to the window.
    for rho in (0.0, 0.5, 0.8, 0.9):
        for tau in (5.0, 20.0):
            chi2s = []
            rng = np.random.default_rng(12345)
            for _ in range(args.replicas):
                series = {}
                for n in NAMES:
                    series[n] = synth(rng, args.n_records, args.n_chains, tau, rho,
                                      amp=12.0 * sigmas[n], sigma=sigmas[n],
                                      target=targets[n])
                t = np.arange(args.n_records, dtype=float)
                m = {n: series[n].mean(axis=1) for n in NAMES}
                s = {n: np.maximum(series[n].std(axis=1, ddof=1)
                                   / math.sqrt(args.n_chains), 1e-12) for n in NAMES}
                tau_hat, c_flat, c_fit, ndof, npar = scan._fit_joint_once(
                    t, m, s, targets, NAMES)
                if tau_hat in (0.0,) or math.isinf(tau_hat) or tau_hat != tau_hat:
                    continue
                chi2s.append(c_fit / max(ndof - npar, 1))
            a = np.array(chi2s)
            if len(a) < 10:
                continue
            key = f"rho={rho}, tau={tau:g}"
            results[key] = {
                "n": len(a), "median": float(np.median(a)),
                "p95": float(np.percentile(a, 95)),
                "p99": float(np.percentile(a, 99)),
                "max": float(a.max()),
                "reject_at_3": float((a > 3).mean()),
                "reject_at_5": float((a > 5).mean()),
            }
            r = results[key]
            print(f"{key:<22} n={r['n']:3d} median={r['median']:5.2f} "
                  f"p95={r['p95']:5.2f} p99={r['p99']:5.2f} max={r['max']:6.2f}  "
                  f"false-reject @3 {100*r['reject_at_3']:5.2f}%  "
                  f"@5 {100*r['reject_at_5']:5.2f}%")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
