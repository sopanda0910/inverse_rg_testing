"""Aggregate repeated wall-clock timings into an honest interval on the
cost RATIOS that this project quotes (e.g. the same-endpoint 2.94x of arm G
against arm E).

WHY THIS EXISTS. Those ratios are wall-clock measurements, and their
uncertainty is machine scheduling jitter, not sampling noise -- no
resampling of the physics data can recover it (see App. "Statistical
methodology", the paragraph on what carries no error bar). The only honest
route is to measure the same work repeatedly and report the spread, which
is what `run_timing_jitter.ps1` collects and this script summarises.

TWO MEASUREMENT CONDITIONS MATTER AND ARE ENFORCED UPSTREAM, NOT HERE:
the repeats must run on an otherwise-idle GPU (timing under contention
measures the contention, not the machine), and each repeat must write to
its own output directory, because `08_hmc_seed_benchmark.py` caches
completed arms and would otherwise reuse the first repeat's numbers instead
of re-timing.

    python u2_2d/scripts/77_timing_jitter.py --dirs out/u2_2d/timing_rep1,...
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dirs", required=True,
                    help="comma-separated per-repeat output directories")
    ap.add_argument("--numerator", default="G_cold_plus_odd_winding")
    ap.add_argument("--denominator", default="E_diffusion_plus_winding")
    ap.add_argument("--out", default="out/u2_2d/timing_jitter.json")
    args = ap.parse_args()

    dirs = [Path(d.strip()) for d in args.dirs.split(",") if d.strip()]
    per_arm: dict[str, list[float]] = {}
    for d in dirs:
        for f in sorted(d.glob("arm_*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            name = rec.get("name") or f.stem.replace("arm_", "")
            secs = rec.get("seconds")
            if secs is None:
                continue
            per_arm.setdefault(name, []).append(float(secs))

    if not per_arm:
        print("no arm_*.json with timings found in the given directories")
        return 1

    print(f"{'arm':<32s} {'n':>2s} {'median s':>10s} {'min':>9s} {'max':>9s} {'rel spread':>11s}")
    summary = {}
    for name, vals in sorted(per_arm.items()):
        v = np.array(vals, dtype=float)
        med = float(np.median(v))
        rel = float((v.max() - v.min()) / med) if med > 0 else float("nan")
        summary[name] = {"n": len(v), "median": med, "min": float(v.min()),
                        "max": float(v.max()), "relative_spread": rel,
                        "all": vals}
        print(f"{name:<32s} {len(v):2d} {med:10.1f} {v.min():9.1f} {v.max():9.1f} {100*rel:10.1f}%")

    num, den = args.numerator, args.denominator
    if num in per_arm and den in per_arm:
        a = np.array(per_arm[num], dtype=float)
        b = np.array(per_arm[den], dtype=float)
        # Ratio over ALL pairings of the independent repeats -- with a handful
        # of repeats this enumerates the achievable spread directly, and does
        # not pretend to a precision the repeat count cannot support.
        ratios = np.array([x / y for x in a for y in b if y > 0])
        print(f"\nratio {num} / {den}")
        print(f"  point (median/median) = {np.median(a)/np.median(b):.2f}")
        print(f"  over all {len(ratios)} repeat pairings: "
              f"min {ratios.min():.2f}, max {ratios.max():.2f}, "
              f"median {np.median(ratios):.2f}")
        print(f"  -> quote as {np.median(ratios):.1f} "
              f"(range {ratios.min():.1f}-{ratios.max():.1f} over "
              f"{len(a)}x{len(b)} timing repeats)")
        summary["_ratio"] = {"numerator": num, "denominator": den,
                            "median": float(np.median(ratios)),
                            "min": float(ratios.min()),
                            "max": float(ratios.max()),
                            "n_pairings": int(len(ratios))}

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(summary, open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
