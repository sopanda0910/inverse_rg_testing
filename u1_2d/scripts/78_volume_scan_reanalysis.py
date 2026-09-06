"""Reanalyse u1's fixed-beta VOLUME scan (L = 32/64/128 at beta = 14.1464)
under the CORRECTED joint exponential relaxation-time estimator, from the
per-trajectory series already on disk. No HMC, no GPU -- minutes on CPU.

WHY THIS EXISTS. `out/u1_2d/thermalization_volume/report.md` quotes
`t_therm` from the ORIGINAL discrete threshold-crossing rule (first record
where |z| <= 2 for 5 consecutive records). That definition was replaced
project-wide on 2026-09-03 by an exponential relaxation-time FIT (Detmold &
Endres' multiscale-equilibration methodology), and the fit itself gained an
absolute chi2/dof goodness-of-fit veto on 2026-09-06. u2's whole coverage /
volume matrix has been re-run under the corrected estimator; u1's volume
scan has not, so the two studies currently quote volume results computed by
DIFFERENT rules -- exactly the drift CLAUDE.md's standing parity rule
forbids.

This is affordable only because the scan saved its raw per-trajectory
series (`*_series.npz`, [n_records, n_chains] per arm per observable) --
the same foresight that made u2's own estimator changes cheap. Reanalysis
costs seconds; regenerating the HMC would cost hours at L = 128.

The estimator used is `fit_joint_relaxation_time` (one tau shared across
plaquette / W(2x2) / W(4x4)), ported verbatim into u1_2d/validate/stats.py
from u2's `28_crossover_scan.py`, so the number this script prints is
directly comparable to every u2 t_therm in the paper.

    .venv/Scripts/python.exe u1_2d/scripts/78_volume_scan_reanalysis.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from u1_2d.lgt.exact import wilson_loop_exact
from u1_2d.validate.stats import LOCAL, fit_joint_relaxation_time

# Wilson-loop area for each name the joint fit uses.
AREA = {"plaquette": 1, "wilson_2x2": 4, "wilson_4x4": 16, "wilson_6x6": 36}
ARMS = ("diffusion seed", "hot start", "cold start")


def threshold_t_therm(series: np.ndarray, target: float,
                      z_threshold: float = 2.0, n_consecutive: int = 5) -> float:
    """The SUPERSEDED discrete rule, inlined from
    `u1_2d/scripts/05_hmc_thermalization.py` (it lives in a script, not an
    importable module). Reported only as the `t_therm_threshold_old`
    cross-check column, matching u2's own precedent -- never as the value of
    record.

    NOTE it is computed here on the FULL generated batch, whereas the original
    `report.md` applied it to a subsample matched to the baseline chain count.
    More chains means a smaller SEM and hence a stricter |z| <= 2 test, so
    this column reads higher than the report's (e.g. 9 against 1 at L=32).
    That is the stricter reading, and the two are not interchangeable -- do
    not compare this column against the report's numbers directly."""
    mean = series.mean(axis=1)
    sem = np.maximum(series.std(axis=1, ddof=1) / math.sqrt(series.shape[1]), 1e-12)
    ok = np.abs((mean - target) / sem) <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t:t + n_consecutive].all():
            return float(t)
    return float("inf")


def fmt(x: float) -> str:
    if x != x:
        return "BAD-FIT"
    if math.isinf(x):
        return "inf"
    return f"{x:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="out/u1_2d/thermalization_volume")
    ap.add_argument("--out", default="out/u1_2d/thermalization_volume/reanalysis.json")
    ap.add_argument("--n-boot", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    root = Path(args.root)
    cases = sorted([d for d in root.iterdir() if d.is_dir() and d.name.startswith("L")],
                   key=lambda d: int(d.name.split("_")[0][1:]))
    if not cases:
        print(f"no L*/ case directories under {root}")
        return 1

    records = []
    print(f"{'L':>4} {'arm':<16} {'tau (new)':>10} {'+-':>8} {'chi2/dof':>9} "
          f"{'t_therm (old)':>14} {'2 tau_int':>10}")
    for case in cases:
        npz_files = sorted(case.glob("*_series.npz"))
        if not npz_files:
            print(f"{case.name}: no series, skipped")
            continue
        z = np.load(npz_files[0])
        summary_files = sorted(case.glob("*_summary.json"))
        summary = json.loads(summary_files[0].read_text(encoding="utf-8")) if summary_files else {}
        size = int(summary.get("lattice_size") or case.name.split("_")[0][1:])
        beta = float(summary.get("beta") or case.name.split("beta")[1])

        targets = {name: float(wilson_loop_exact(beta, AREA[name], "wilson", size))
                   for name in LOCAL}

        # The HMC decorrelation interval, the yardstick every t_therm is read
        # against, is taken UNCHANGED from the original run's summary. This
        # script corrects the t_therm ESTIMATOR and nothing else: recomputing
        # the interval here as well would change two quantities at once and
        # make the before/after comparison uninterpretable.
        #
        # It was tried, and the attempt is worth recording as the reason for
        # the rule. Recomputing tau_int from the cold arm's settled tail gave
        # intervals of 8.5 / 10.0 / 11.0 against the stored 8.7 / 35.0 / 64.1
        # -- agreeing at L=32 and disagreeing by 3-6x at L=64/128. The cause
        # is visible in this script's own output: at those volumes the cold
        # arm is BAD-FIT, i.e. never equilibrates within the window, so its
        # "settled tail" is not settled and a Madras-Sokal window on a short
        # drifting series truncates early and UNDERSTATES tau_int. Using it
        # would have flattered the seed by shrinking the yardstick it is
        # measured against.
        interval = summary.get("hmc_interval_trajectories")
        interval = float(interval) if interval is not None else float("nan")
        tau_int_stored = (summary.get("tau_int", {}).get("plaquette", {}) or {}).get("value")

        for arm in ARMS:
            series = {name: np.asarray(z[f"{arm}|{name}"], dtype=float) for name in LOCAL}
            fit = fit_joint_relaxation_time(series, targets, record_every=1,
                                            n_boot=args.n_boot, seed=args.seed)
            old = threshold_t_therm(series["plaquette"], targets["plaquette"])
            rec = {"lattice_size": size, "beta": beta, "arm": arm,
                   "n_records": int(series["plaquette"].shape[0]),
                   "n_chains": int(series["plaquette"].shape[1]),
                   "tau": fit["tau"], "tau_err": fit["tau_err"],
                   "chi2_per_dof": fit["chi2_per_dof"],
                   "fit_quality_ok": fit["fit_quality_ok"],
                   "t_therm_threshold_old": old,
                   "tau_int_plaquette_stored": tau_int_stored,
                   "hmc_interval_trajectories": interval,
                   "targets": targets}
            records.append(rec)
            print(f"{size:4d} {arm:<16} {fmt(fit['tau']):>10} "
                  f"{fit['tau_err']:8.1f} {fit['chi2_per_dof']:9.2f} "
                  f"{fmt(old):>14} {interval:10.1f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(records, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")

    # The comparison the paper makes: does the seed's advantage over a fresh
    # chain survive as the volume grows, scored by the CURRENT estimator.
    print("\nseed relaxation against the classical arms, corrected estimator:")
    by_size: dict[int, dict] = {}
    for r in records:
        by_size.setdefault(r["lattice_size"], {})[r["arm"]] = r
    for size in sorted(by_size):
        row = by_size[size]
        seed = row.get("diffusion seed", {})
        print(f"  L={size:4d}  seed {fmt(seed.get('tau', float('nan'))):>8}   "
              f"cold {fmt(row.get('cold start', {}).get('tau', float('nan'))):>8}   "
              f"hot {fmt(row.get('hot start', {}).get('tau', float('nan'))):>8}   "
              f"(HMC interval {seed.get('hmc_interval_trajectories', float('nan')):.1f} traj)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
