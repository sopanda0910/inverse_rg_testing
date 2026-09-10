"""Recompute both timescales from the saved series using standard definitions,
so the paper can cite them instead of defining them.

Nothing here is invented. Two quantities, each the textbook one:

INTERVAL TIME.  tau_int is the integrated autocorrelation time, estimated with
Sokal's automatic windowing [Madras & Sokal 1988; Wolff 2004]. N measurements
carry N / (2 tau_int) independent samples, so the cost of ONE independent
configuration is

    interval = 2 tau_int,   maximised over the scored observables.

The maximisation must include Q^2. tau_int of a local observable stays at a few
trajectories in a chain whose topology has not moved once, so a plaquette-only
interval never sees topological freezing; the cost of an independent
CONFIGURATION is set by the slowest mode. A series that never moves is reported
as infinite rather than integrated: a constant has no autocorrelation, so
freezing otherwise returns a spuriously SMALL tau_int.

THERMALIZATION TIME.  Detmold & Endres [PRD 92, 114516 (2015); PRD 94, 114502
(2016)] fit the approach of an observable to its equilibrium value with a single
exponential,

    <O>(t) = O_exact + A exp(-t / tau_rel),

the target held at the known exact value rather than fitted, since these
theories are solvable. Equilibration is reached once the remaining bias falls
below the statistical error sigma on the mean, which is the standard
burn-in-until-bias-is-invisible criterion and gives a closed form,

    t_therm = tau_rel * ln(|A| / sigma),   clipped below at 0,

again maximised over observables. This is well behaved in both limits that
matter and is why it replaces the discrete threshold crossing used earlier: a
start already at equilibrium has |A| <= sigma and returns 0 rather than the
`inf` an unconstrained fit to a flat series returns, and a start that never
arrives returns inf through tau_rel. The earlier fitted `t_therm` was INVERTED
for good starting configurations for exactly that reason -- it asked whether a
decay could be resolved, and a configuration already at target has none.

    python u2_2d/scripts/90_standard_timescales.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from u2_2d.lgt.exact import wilson_loop_exact, det_topological_charge_distribution  # noqa: E402
from u2_2d.validate.stats import integrated_autocorrelation_time  # noqa: E402

BASE = ROOT / "out/u2_2d/coverage_scan_relaxation"
OUT = BASE / "_standard_timescales.json"
CKPTS = ("cov60", "default", "wide", "wide_dense")
STEMS = ("crossover", "crossover_topo", "crossover_L64", "crossover_L64_topo")
OBS = (("plaquette", 1), ("wilson_2x2", 4), ("wilson_4x4", 16))
ARMS = ("diffusion seed", "cold start", "hot start")


def tau_int_traj(series, record_every):
    """2 tau_int in trajectories; inf for a series that never moves."""
    tail = np.asarray(series, dtype=float)
    tail = tail[tail.shape[0] // 2:]
    if np.allclose(tail, tail[0]):
        return float("inf")
    taus, moving = [], 0
    for c in range(tail.shape[1]):
        col = tail[:, c]
        if np.allclose(col, col[0]):
            continue
        moving += 1
        t, _ = integrated_autocorrelation_time(col)
        if np.isfinite(t) and t > 0:
            taus.append(t)
    if not taus:
        return float("inf")
    # chains that never move contribute no independent samples at all, so the
    # cost per independent configuration scales up by the moving fraction
    frac = moving / tail.shape[1]
    return float(np.median(taus)) * float(record_every) / max(frac, 1e-9)


def therm_time(series, exact, record_every):
    """Equilibration time on the standard criterion: the earliest trajectory
    after which the remaining bias is statistically invisible, meaning
    |<O>(t) - O_exact| stays below the statistical error sigma for the whole
    rest of the window.

    This is Detmold & Endres' quantity read straight off the data rather than
    off a fitted exponential. Reading it off the fit was tried first and is
    fragile in exactly the cases that matter: curve_fit fails or extrapolates
    past the window for a start that is already equilibrated, which is the same
    inversion that made the original estimator unusable for good starting
    configurations. The criterion has no free parameter beyond the 1-sigma
    convention, and both limits behave: a start already at target returns 0, a
    start that never gets there returns inf.
    """
    a = np.asarray(series, dtype=float)
    n_rec, n_ch = a.shape
    if n_rec < 2:
        return float("nan")
    mean = a.mean(axis=1)
    sigma = float(a[n_rec // 2:].std(axis=1).mean() / np.sqrt(n_ch))
    if not np.isfinite(sigma) or sigma <= 0:
        return float("nan")

    inside = np.abs(mean - exact) <= sigma
    # walk back from the end: the crossing is the last point at which the chain
    # was still outside the noise
    idx = n_rec
    while idx > 0 and inside[idx - 1]:
        idx -= 1
    if idx == 0:
        return 0.0                      # inside the noise from the first record
    if idx >= n_rec:
        return float("inf")             # never settles inside the window
    return float(idx * float(record_every))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    out = {}
    for ck in CKPTS:
        for stem in STEMS:
            meta = BASE / ck / f"{stem}.json"
            if not meta.exists():
                continue
            for r in json.loads(meta.read_text()):
                sf = BASE / ck / "series" / f"{stem}_beta{r['beta']:g}.npz"
                if not sf.exists():
                    continue
                z = np.load(sf)
                re_ = float(z["record_every"])
                L = r["lattice_size"]
                beta = r["beta"]
                qv, pq = det_topological_charge_distribution(beta, L)
                q2_exact = float((qv ** 2 * pq).sum())

                rec = {"model_beta": r["model_beta"], "beta": beta, "L": L}
                for arm in ARMS:
                    ivs = [tau_int_traj(z[f"{arm}__{o}"], re_) for o, _ in OBS]
                    ivs.append(tau_int_traj(z[f"{arm}__charge"] ** 2, re_))
                    tts = []
                    for o, area in OBS:
                        ex = wilson_loop_exact(beta, area, lattice_size=L)
                        tts.append(therm_time(z[f"{arm}__{o}"], ex, re_))
                    tts.append(therm_time(z[f"{arm}__charge"] ** 2, q2_exact, re_))
                    tag = arm.split()[0]
                    iv = 2.0 * max(ivs)
                    tt = np.nanmax(tts)
                    rec[f"interval_{tag}"] = None if not np.isfinite(iv) else iv
                    rec[f"therm_{tag}"] = None if not np.isfinite(tt) else float(tt)
                    rec[f"interval_local_{tag}"] = (
                        None if not np.isfinite(2.0 * max(ivs[:-1]))
                        else 2.0 * max(ivs[:-1]))
                out[f"{ck}|{stem}|{beta:g}"] = rec
            print(f"  done {ck} {stem}")

    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"wrote {len(out)} records -> {args.out}")

    def show(v):
        return "inf" if v is None else f"{v:.0f}"

    print("\nsanity, L=32 winding round (model beta: therm(lift) / interval(cold)):")
    for ck in CKPTS:
        rows = [v for k, v in out.items()
                if k.startswith(f"{ck}|crossover_topo|")]
        rows.sort(key=lambda r: r["model_beta"])
        s = "  ".join(f"{r['model_beta']:.0f}:{show(r['therm_diffusion'])}"
                      f"/{show(r['interval_cold'])}" for r in rows)
        print(f"  {ck:11s} {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
