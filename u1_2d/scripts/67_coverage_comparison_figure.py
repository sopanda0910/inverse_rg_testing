"""Overlay `65_cost_efficiency_figure.py`'s steady-state cost-efficiency curve
for several checkpoints that differ in training coverage. The u1 twin of
`u2_2d/scripts/59_coverage_comparison_figure.py`.

Reads `out/u1_2d/coverage_scan/<tag>/crossover_window.json` (written by
`66_training_coverage_scan.py`) for each additional checkpoint, plus the
existing `out/u1_2d/thermalization/crossover_window.json` for the deployed
one. As of this writing only the deployed checkpoint has data -- see
`66_training_coverage_scan.py`'s docstring for why a genuine coverage
ablation needs a new u1 training run before this figure has more than one
curve on it.

    python u1_2d/scripts/67_coverage_comparison_figure.py
"""
from __future__ import annotations

import argparse
import math
import sys
from importlib import import_module
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

sys.path.insert(0, str(Path(__file__).resolve().parent))
fig65 = import_module("65_cost_efficiency_figure")

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"

CHECKPOINTS = [
    # tag, paths, colour, train_beta_max, label
    #
    # wide2000's new coverage (fine beta 300-2000) is L=16 ONLY --
    # random_rungs, the sole fine=32 source, stayed capped at beta<=250 (see
    # wide2000.yaml's header) -- so this figure's wide2000/deployed panel is
    # the matched L=8->16 scan in
    # coverage_scan/wide2000_L16target/{deployed,wide2000}/, which reruns
    # BOTH checkpoints identically except for the checkpoint (--L 16, run
    # with `python 67_coverage_comparison_figure.py --L 16`). wide250 has no
    # L=16 data (its own coverage extension was L=32) and is intentionally
    # left off this panel; its qualitative result (thermalizes at
    # beta_f=218.58, L=32, where deployed has no coverage at all) is quoted
    # in the text from its own L=32 figure/run, not from this one.
    ("deployed", ["out/u1_2d/coverage_scan/wide2000_L16target/deployed/crossover_window.json"],
     "#0072B2", 60.0, "deployed (score_net.pt, beta_max=60)"),
    ("wide2000", ["out/u1_2d/coverage_scan/wide2000_L16target/wide2000/crossover_window.json"],
     "#009E73", 2000.0, "wide2000 (beta_max=2000, same capacity)"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--L", type=int, default=32)
    parser.add_argument("--out", default="out/u1_2d/figures/fig67_coverage_comparison.png")
    args = parser.parse_args()

    fig, ax = plt.subplots(figsize=(6.9, 4.6))
    log_floor, log_ceil = 0.03, 30.0
    present = []

    for tag, paths, colour, train_max, label in CHECKPOINTS:
        rows = [r for r in fig65.load_rows(paths) if r.get("L") == args.L]
        if not rows:
            print(f"[{tag}] no data for L={args.L} under {paths}")
            continue
        present.append((tag, colour, train_max, label))
        rows = sorted(rows, key=lambda r: r["beta"])
        xs, ys, lo_xs = [], [], []
        for r in rows:
            v = fig65.cost_efficiency(r)
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

        betas = [r["beta"] for r in rows]
        inside = [b for b in betas if b <= train_max]
        outside = [b for b in betas if b > train_max]
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
    ax.set_xlabel(r"fine coupling  $\beta$  ($L = %d$)" % args.L, fontsize=10, color=INK)
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
    ax.legend(handles=handles, loc="upper left", fontsize=7.5, frameon=False,
             labelcolor=INK)

    fig.suptitle("u1: cost-efficiency vs training coverage", fontsize=11.5,
                 color=INK, x=0.02, ha="left")
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote " + str(dest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
