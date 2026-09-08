"""Recompute EVERY crossover-derived number the paper quotes, from whatever
is currently on disk, so the paper and the data cannot drift apart.

Emits: the volume table (resolved counts by checkpoint and volume, overall and
in-coverage), the paired McNemar tests between checkpoints at each volume, the
coverage sign tests of sec:coverage-u2, and the gap-vs-t_therm correlation.

Run it after any rescore. Every number it prints is one the paper states.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, spearmanr

ROOT = Path("out/u2_2d/coverage_scan_relaxation")
CEIL = {"cov60": 56.83, "default": 104.132, "wide": 2000.0,
        "wide_dense": 2000.0, "wide_dense_frozen": 2000.0}
L32 = ["crossover", "crossover_topo"]
L64 = ["crossover_L64", "crossover_L64_topo"]


def resolved(t) -> bool:
    """A finite fitted relaxation time. NaN is the veto's BAD-FIT marker and
    inf is 'never converged'; neither counts as resolved."""
    return isinstance(t, (int, float)) and t == t and not math.isinf(t)


def load(tag: str, stem: str):
    p = ROOT / tag / f"{stem}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def cost_efficiency(rec):
    iv = rec.get("interval")
    if not iv or not math.isfinite(iv):
        return None
    t = rec["t_therm"]["diffusion seed"]
    if not isinstance(t, (int, float)) or t != t:
        return None          # BAD-FIT: no value, not a zero
    if math.isinf(t):
        return 0.0           # seed never converges: pipeline delivers nothing
    if t <= 0:
        return float("inf")  # already at target
    return iv / t


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tags", nargs="+",
                    default=["cov60", "default", "wide", "wide_dense"])
    args = ap.parse_args()
    tags = [t for t in args.tags if (ROOT / t).exists()]

    print("=" * 74)
    print("VOLUME TABLE  (seed resolves a finite relaxation time)")
    print(f"{'checkpoint':<20} {'L=32 all':>10} {'L=32 incov':>11} "
          f"{'L=64 all':>10} {'L=64 incov':>11}")
    table = {}
    for tag in tags:
        row = []
        for stems in (L32, L64):
            r = t = ri = ti = 0
            for stem in stems:
                for rec in load(tag, stem):
                    ok = resolved(rec["t_therm"]["diffusion seed"])
                    t += 1; r += ok
                    if rec["model_beta"] <= CEIL.get(tag, 1e9):
                        ti += 1; ri += ok
            row += [f"{r}/{t}", f"{ri}/{ti}"]
        table[tag] = row
        print(f"{tag:<20} {row[0]:>10} {row[1]:>11} {row[2]:>10} {row[3]:>11}")

    print("\n" + "=" * 74)
    print("PAIRED McNEMAR, checkpoint vs checkpoint, identical couplings")
    for L, stems in (("L=32", L32), ("L=64", L64)):
        for a in tags:
            for b in tags:
                if a >= b:
                    continue
                w = l = 0
                for stem in stems:
                    A = {round(x["model_beta"], 3): resolved(x["t_therm"]["diffusion seed"])
                         for x in load(a, stem)}
                    B = {round(x["model_beta"], 3): resolved(x["t_therm"]["diffusion seed"])
                         for x in load(b, stem)}
                    for k in A:
                        if k not in B:
                            continue
                        if A[k] and not B[k]:
                            w += 1
                        elif B[k] and not A[k]:
                            l += 1
                n = w + l
                if n == 0:
                    continue
                p = binomtest(w, n, 0.5).pvalue
                print(f"  {L}  {a:<12} vs {b:<12}: {a[:4]}-only {w:2d}, "
                      f"{b[:4]}-only {l:2d}, discordant {n:2d}, p={p:.4f}")

    print("\n" + "=" * 74)
    print("COVERAGE SIGN TESTS (cost-efficiency, wide vs default)")
    for label, restrict in (("all couplings", None),
                            ("past default's ceiling", 104.132)):
        wins = losses = ties = 0
        for stems in (L32, L64):
            for stem in stems:
                W = {round(x["model_beta"], 3): cost_efficiency(x) for x in load("wide", stem)}
                D = {round(x["model_beta"], 3): cost_efficiency(x) for x in load("default", stem)}
                for k in W:
                    if k not in D or W[k] is None or D[k] is None:
                        continue
                    if restrict is not None and k <= restrict:
                        continue
                    if W[k] > D[k]:
                        wins += 1
                    elif W[k] < D[k]:
                        losses += 1
                    else:
                        ties += 1
        n = wins + losses
        p = binomtest(wins, n, 0.5).pvalue if n else float("nan")
        print(f"  {label:<26}: wide wins {wins}, loses {losses}, ties {ties}, "
              f"n={n}, p={p:.4f}")

    print("\n" + "=" * 74)
    print("GAP TO NEAREST TRAINING RUNG vs seed t_therm (pooled Spearman)")
    gaps, taus = [], []
    for tag in tags:
        rungs = RUNGS.get(tag)
        if not rungs:
            continue
        for stems in (L32, L64):
            for stem in stems:
                for rec in load(tag, stem):
                    t = rec["t_therm"]["diffusion seed"]
                    if not resolved(t) or t <= 0:
                        continue
                    mb = rec["model_beta"]
                    gaps.append(min(abs(mb - r) for r in rungs))
                    taus.append(t)
    if len(gaps) > 3:
        rho, p = spearmanr(gaps, taus)
        print(f"  n={len(gaps)}  Spearman rho={rho:+.3f}  p={p:.2e}")
    else:
        print("  too few resolved points")
    return 0


# Model-beta training rungs per checkpoint (from the configs).
RUNGS = {
    "default": [0.62, 1.71, 3.56, 7.02, 12.95, 14.01, 26.42, 50.79, 104.13],
    "cov60": [0.62, 1.71, 3.56, 7.02, 12.95, 14.01, 26.42, 50.79, 56.83],
    "wide": [0.62, 1.71, 3.56, 7.02, 12.95, 14.01, 26.42, 50.79, 104.13,
             150.0, 175.0, 200.0, 225.0, 250.0, 275.0, 300.0, 325.0, 350.0,
             375.0, 437.5, 500.0],
}
RUNGS["wide_dense"] = RUNGS["wide"]
RUNGS["wide_dense_frozen"] = RUNGS["wide"]

if __name__ == "__main__":
    raise SystemExit(main())
