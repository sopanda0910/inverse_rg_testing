"""How many INDEPENDENT observables a u2 scorecard contains, and back-fill it.

WHY THIS EXISTS. Every `mean |z|` in this project gets compared against zero, or
against another `mean |z|`, and neither reading is meaningful on its own. |z| is
half-normal when the model is exactly right and the error bars are correct, so
the null value is `sqrt(2/pi) = 0.798` -- a scorecard of 0.187 is four times
"better than perfect" and is evidence about the ERROR BARS, not about the model.
And the standard error of that mean is `sqrt(1 - 2/pi) / sqrt(N)`, which needs
the number of INDEPENDENT observables, not the row count.

In 2D those differ by an order of magnitude. Wilson loops of different sizes are
near-deterministic functions of one another: at L = 32 the correlation matrix of
the 41 scored observables has top eigenvalue 18.6 -- one mode carries 45% of the
variance -- and a mean within-family |correlation| of 0.62. The participation
ratio `(sum lambda)^2 / sum lambda^2` is **3.77**, so SE(mean |z|) is 0.31 rather
than 0.09 and three claims made from these scorecards were overstated by 3.3x.

`validate.report.compare` now records `n_effective` on every summary it writes,
so this script exists for the ARTEFACTS THAT PREDATE THAT -- the deployed
validation of record and the challenger comparisons. It measures the generated
ensembles directly (no reference HMC is involved: N_eff is a property of the
observable set on one ensemble) and writes the counts back into the summary.

Two counts are produced, because two different scorecards are read off these
files: `n_effective` over every scored observable, and `n_effective_extended`
over the area >= 16 full-U(2) Wilson loops, which is the subset guard (c) of
`25_challenger_report.py` averages.

    python u2_2d/scripts/47_effective_observables.py --ladder out/u2_2d/ladder \
        --summary out/u2_2d/validation/summary.json --inject
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.utils import load_ensemble
from u2_2d.validate.observables import measure_ensemble
from u2_2d.validate.report import _extended_wilson
from u2_2d.validate.stats import (effective_observable_count, mean_abs_z_sigma,
                                  null_mean_abs_z)


def counts_for(path: Path) -> dict:
    configs, meta = load_ensemble(path)
    gen = measure_ensemble(configs)
    return {
        "ensemble": str(path),
        "lattice_size": int(configs.shape[-2]),
        "beta": float(meta.get("beta", 0.0)) if isinstance(meta, dict) else 0.0,
        "n_configs": int(configs.shape[0]),
        "n_effective": effective_observable_count(gen),
        "n_effective_extended": effective_observable_count(
            {k: v for k, v in gen.items() if _extended_wilson(k)}),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ladder", default="out/u2_2d/ladder",
                    help="directory of ladder_L*_beta*.pt ensembles")
    ap.add_argument("--summary", default="out/u2_2d/validation/summary.json",
                    help="validation summary to annotate")
    ap.add_argument("--inject", action="store_true",
                    help="write the counts back into --summary")
    ap.add_argument("--out", default="out/u2_2d/n_effective.json")
    args = ap.parse_args()

    ladder = Path(args.ladder)
    found = sorted(ladder.glob("ladder_L*_beta*.pt"))
    if not found:
        print(f"no ladder ensembles under {ladder}")
        return 1

    rows = []
    for path in found:
        row = counts_for(path)
        rows.append(row)
        print(f"L={row['lattice_size']:3d} beta={row['beta']:9.3f}  "
              f"N={row['n_configs']:5d}  N_eff(all) {row['n_effective']:6.2f}  "
              f"N_eff(extended) {row['n_effective_extended']:6.2f}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nwrote {args.out}")

    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"(no summary at {summary_path} -- nothing to annotate)")
        return 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    by_size = {r["lattice_size"]: r for r in rows}
    print(f"\n{'L':>4} {'mean |z|':>9} {'rows':>5} {'N_eff':>7} {'sigma vs null':>14}")
    for entry in summary:
        row = by_size.get(entry.get("lattice_size"))
        if not row:
            continue
        if args.inject:
            entry["n_effective"] = row["n_effective"]
            entry["n_effective_extended"] = row["n_effective_extended"]
        mz = entry.get("mean_wilson_z")
        if mz is not None:
            sig = mean_abs_z_sigma(mz, row["n_effective"])
            print(f"{entry['lattice_size']:4d} {mz:9.3f} "
                  f"{len(entry.get('rows', [])):5d} {row['n_effective']:7.2f} "
                  f"{sig:+14.2f}")
    if args.inject:
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nannotated {summary_path}")
    print(f"null for an exact model: mean |z| = {null_mean_abs_z():.4f}; "
          "positive sigma means BELOW the null, i.e. errors likely too large.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
