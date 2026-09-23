"""Chain-bootstrap band on t_therm, and on the improvement factor built from it.

`t_therm` is a first-crossing index, so the point estimate hides two things: it
is quantized by the record spacing, and it is set by the last chain to settle,
which is why the improvement-factor curves are ragged in coupling. A fitted
relaxation time would be smooth but is inverted for a good starting
configuration -- a chain that begins at the target has no transient to fit -- so
the crossing is kept and its uncertainty is measured instead.

Both sides of the factor get a band, each resampling its own arm's chains:

    F = interval (classical, cold arm) / t_therm (preconditioned arm)

The two arms are independent runs, so their draws are paired independently. For
a coupling where no classical arm equilibrates the numerator is that coupling's
trajectory budget, a fixed number, and only the denominator contributes.

Reads the saved per-chain series; runs no HMC.

    python u2_2d/scripts/93_therm_bootstrap.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact  # noqa: E402
from u2_2d.validate.stats import (  # noqa: E402
    bootstrap_thermalization,
    integrated_autocorrelation_time,
)

BASE = ROOT / "out/u2_2d/coverage_scan_relaxation"
CKPTS = ("cov60", "default", "wide", "wide_dense")
STEMS = ("crossover_topo", "crossover_L64_topo")
OBS = ("plaquette", "wilson_2x2", "wilson_4x4")
AREA = {"plaquette": 1, "wilson_2x2": 4, "wilson_4x4": 16}


def targets(beta: float, size: int) -> dict[str, float]:
    return {"plaquette": plaquette_exact(beta, size),
            "wilson_2x2": wilson_loop_exact(beta, 4),
            "wilson_4x4": wilson_loop_exact(beta, 16)}


def per_chain_tau(series: np.ndarray) -> np.ndarray:
    """tau_int of each chain's own tail, as 90_standard_timescales computes it.

    A chain that never moves contributes no autocorrelation and is dropped here;
    the moving fraction is applied by the caller, since a frozen chain supplies
    no independent samples and must inflate the cost rather than vanish from it.
    """
    tail = series[series.shape[0] // 2:]
    taus = []
    for c in range(tail.shape[1]):
        col = tail[:, c]
        if np.allclose(col, col[0]):
            continue
        t, _ = integrated_autocorrelation_time(col)
        if np.isfinite(t) and t > 0:
            taus.append(float(t))
    return np.asarray(taus, dtype=np.float64)


def interval_band(series_by_obs: dict, charge: np.ndarray | None,
                  record_every: float, n_boot: int, seed: int) -> dict:
    """2 tau_int in trajectories, maximised over observables, with a band.

    Resamples chains rather than recomputing tau on resampled series: for a
    statistic that is the median over chains the two are equivalent, and the
    first is affordable.
    """
    rng = np.random.default_rng(seed)
    per_obs, fractions = [], []
    for name, s in series_by_obs.items():
        arr = np.asarray(s, dtype=np.float64)
        taus = per_chain_tau(arr)
        if taus.size == 0:
            return {"interval": math.inf, "lo": math.inf, "hi": math.inf}
        per_obs.append(taus)
        fractions.append(taus.size / arr.shape[1])
    if charge is not None:
        taus = per_chain_tau(np.asarray(charge, dtype=np.float64) ** 2)
        if taus.size == 0:
            return {"interval": math.inf, "lo": math.inf, "hi": math.inf}
        per_obs.append(taus)
        fractions.append(taus.size / np.asarray(charge).shape[1])

    def value(sample_idx=None) -> float:
        best = 0.0
        for taus, frac in zip(per_obs, fractions):
            t = taus if sample_idx is None else taus[sample_idx % taus.size]
            v = 2.0 * float(np.median(t)) * record_every / max(frac, 1e-9)
            best = max(best, v)
        return best

    point = value()
    draws = np.empty(n_boot)
    n = max(t.size for t in per_obs)
    for b in range(n_boot):
        draws[b] = value(rng.integers(0, n, size=n))
    lo, hi = np.percentile(draws, (16.0, 84.0))
    return {"interval": point, "lo": float(lo), "hi": float(hi)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(BASE / "_therm_bootstrap.json"))
    args = ap.parse_args()

    out = {}
    for ckpt in CKPTS:
        for stem in STEMS:
            meta = BASE / ckpt / f"{stem}.json"
            if not meta.exists():
                continue
            for rec in json.loads(meta.read_text()):
                beta, size = rec["beta"], rec["lattice_size"]
                f = BASE / ckpt / "series" / f"{stem}_beta{beta:g}.npz"
                if not f.exists():
                    continue
                z = np.load(f)
                re_ = float(z["record_every"])
                tg = targets(beta, size)
                entry = {"beta": beta, "L": size,
                         "n_traj": float(rec.get("n_traj", 400))}
                for arm, tag in (("diffusion seed", "lift"), ("cold start", "cold")):
                    ser = {k: z[f"{arm}__{k}"] for k in OBS
                           if f"{arm}__{k}" in z.files}
                    if len(ser) != len(OBS):
                        continue
                    entry[tag] = bootstrap_thermalization(
                        ser, tg, record_every=re_, n_boot=args.n_boot,
                        seed=args.seed)
                cold = {k: z[f"cold start__{k}"] for k in OBS
                        if f"cold start__{k}" in z.files}
                if len(cold) == len(OBS):
                    q = z["cold start__charge"] if "cold start__charge" in z.files else None
                    entry["interval_cold"] = interval_band(
                        cold, q, re_, args.n_boot, args.seed + 1)
                out[f"{ckpt}|{stem}|{beta:g}"] = entry
                print(f"  {ckpt:11s} {stem:20s} beta={beta:9.3f}  "
                      f"lift {entry.get('lift', {}).get('t_therm', float('nan')):7.1f}"
                      f" [{entry.get('lift', {}).get('lo', float('nan')):.0f},"
                      f"{entry.get('lift', {}).get('hi', float('nan')):.0f}]")
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"\nwrote {len(out)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
