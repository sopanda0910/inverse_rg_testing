"""Overlay `57_cost_efficiency_figure.py`'s steady-state cost-efficiency curve
for several checkpoints that differ in TRAINING COVERAGE, so the falloff past
the training range can be compared directly instead of asserted.

Reads `out/u2_2d/coverage_scan/<tag>/*.json` (written by
`58_training_coverage_scan.py`) for the wide-coverage checkpoints, plus the
already-existing `out/u2_2d/crossover/*.json` for the deployed
(narrow-coverage) checkpoint. One panel: cost-efficiency vs beta_f, one
colour per checkpoint, each checkpoint's own training-coverage edge marked in
its own colour (they differ: default's edge sits at model beta 104.132,
v2/cap's at ~107.5) rather than one shared hatch, since a shared edge would
misstate an experiment where the whole point is that the edges differ.

Uses the WINDING round only (HMC + marginal winding in every arm) -- the
honest ergodic classical baseline -- for legibility with several checkpoints
on one axis; `57_cost_efficiency_figure.py` remains the place both rounds are
shown for a single checkpoint.

    python u2_2d/scripts/59_coverage_comparison_figure.py
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module

fig57 = import_module("57_cost_efficiency_figure")

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"

CHECKPOINTS = [
    # tag, dirs to read, colour, train_model_beta_max, label
    #
    # default/cov60/wide re-pointed 2026-09-05 at
    # out/u2_2d/coverage_scan_relaxation/<tag>/, the corrected
    # exponential-relaxation-time (fit_relaxation_time) data from the
    # overnight matrix -- NOT the old out/u2_2d/crossover or
    # coverage_scan/{cov60,...} directories, which used the retired discrete
    # threshold-crossing t_therm. v2/cap/cov30/cov15 were not re-run under
    # the corrected estimator (out of scope for that matrix, see
    # 60_run_full_relaxation_matrix.py's PRIORITY comment) and still read
    # the old dirs -- mixing methodologies on one axis, so treat any
    # v2/cap/cov30/cov15 curve here as qualitative only until re-run.
    ("default", ["out/u2_2d/coverage_scan_relaxation/default"], "#0072B2", 104.132,
     "default (12 fixed rungs)"),
    ("wide", ["out/u2_2d/coverage_scan_relaxation/wide"], "#009E73", 2000.0,
     "wide (trained to model beta ~2000)"),
    ("cov60", ["out/u2_2d/coverage_scan_relaxation/cov60"], "#CC79A7", 56.83,
     "cov60 (capped at model beta ~60, matching u1_2d)"),
    ("v2", ["out/u2_2d/coverage_scan/v2"], "#D55E00", 107.5,
     "v2 (+102 random rungs, same capacity) [old estimator]"),
    ("cap", ["out/u2_2d/coverage_scan/cap"], "#8B4513", 107.5,
     "cap (+102 random rungs, capacity raised) [old estimator]"),
    ("cov30", ["out/u2_2d/coverage_scan/cov30"], "#E69F00", 29.60,
     "cov30 (capped at model beta ~30) [old estimator]"),
    ("cov15", ["out/u2_2d/coverage_scan/cov15"], "#56B4E9", 14.55,
     "cov15 (capped at model beta ~15) [old estimator]"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fine-size", type=int, default=32)
    parser.add_argument("--out", default="out/u2_2d/figures/fig59_coverage_comparison.png")
    args = parser.parse_args()

    fig, ax = plt.subplots(figsize=(6.9, 4.6))
    log_floor, log_ceil = 0.03, 10.0
    present = []

    for tag, dirs, colour, train_max, label in CHECKPOINTS:
        by_volume = fig57.load_rounds(dirs)
        rows = by_volume.get(args.fine_size, {}).get(True, {})
        if not rows:
            print(f"[{tag}] no winding-round data under {dirs} for L={args.fine_size} "
                  "-- run 58_training_coverage_scan.py first" if tag != "default"
                  else f"[{tag}] no data under {dirs}")
            continue
        present.append((tag, colour, train_max, label))
        rows = sorted(rows.values(), key=lambda r: r["beta"])
        xs, ys, lo_xs, hi_xs = [], [], [], []
        for r in rows:
            try:
                v = fig57.cost_efficiency(r)
            except TypeError:
                # Old per-observable-dict t_therm schema (pre-2026-09-03),
                # still present in the [old estimator] checkpoints
                # (v2/cap/cov30/cov15) that were never re-run under the
                # corrected exponential relaxation-time fit -- skip rather
                # than crash the whole figure over one incompatible arm.
                continue
            if v is None:
                continue
            if v <= 0.0:
                lo_xs.append(r["beta"])
            else:
                xs.append(r["beta"])
                ys.append(min(max(v, log_floor), log_ceil))
        if xs:
            ax.plot(xs, ys, color=colour, lw=2.0, marker="o", ms=5,
                    markeredgecolor="white", markeredgewidth=0.5, zorder=4,
                    label=label)
        for b in lo_xs:
            ax.plot([b], [log_floor], marker="v", ms=8, color=colour,
                    markerfacecolor="none", markeredgewidth=1.5, zorder=5)

        # This checkpoint's OWN coverage edge, in its own colour, found the
        # same way 57's shade_training_range does: the midpoint (in log beta)
        # between the last in-coverage and first out-of-coverage coupling.
        mbetas = {r["beta"]: r.get("model_beta") for r in rows}
        inside = [b for b, m in mbetas.items() if m and m <= train_max]
        outside = [b for b, m in mbetas.items() if m and m > train_max]
        if inside and outside:
            edge = math.sqrt(max(inside) * min(outside))
            ax.axvline(edge, color=colour, lw=1.3, ls=(0, (3, 2)), alpha=0.85,
                      zorder=3)

    if not present:
        print("no checkpoint data found at all -- nothing to plot")
        return 1

    ax.axhline(1.0, color=INK, lw=1.1, ls=(0, (1, 1)), zorder=2)
    ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_ylim(log_floor * 0.8, log_ceil * 1.25)
    ax.set_ylabel("steady-state cost-efficiency\n" r"$\mathrm{interval}\,/\,t_{seed}$",
                 fontsize=9.5, color=INK)
    ax.set_xlabel(r"fine coupling  $\beta_f$  ($L_f = %d$)" % args.fine_size,
                 fontsize=10, color=INK)
    ax.grid(True, which="major", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))

    handles = [Line2D([], [], color=c, lw=2.0, marker="o", ms=5, label=lab)
               for _, c, _, lab in present]
    handles.append(Line2D([], [], color=MUTED, lw=1.3, ls=(0, (3, 2)),
                          label="that checkpoint's own training-coverage edge"))
    handles.append(Line2D([], [], color=MUTED, marker="v", ms=8, lw=0,
                          markerfacecolor="none", markeredgewidth=1.5,
                          label="seed itself fails to thermalize"))
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, frameon=False,
             labelcolor=INK)

    fig.suptitle("Wider training coverage moves the cost-efficiency falloff out "
                 "in beta", fontsize=11.5, color=INK, x=0.02, ha="left")
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote " + str(dest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
