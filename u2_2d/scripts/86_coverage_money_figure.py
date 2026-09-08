"""The summary figure: coupling reach, volume, and training coverage at once.

Three things the paper argues separately, in one panel set:

  (a) how far in coupling a checkpoint's seed stays usable, and that the edge
      sits at its own TRAINING CEILING rather than at some universal beta;
  (b) what happens one volume up, at L=64, where no checkpoint has ever
      trained;
  (c) that the difference between checkpoints is coverage and nothing else --
      identical architecture, epochs and random-rung block.

Scored on the endpoint of record (raw seed Z at record 0, before any
trajectory) so it is directly comparable to every number in the text.

    python u2_2d/scripts/86_coverage_money_figure.py
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "fig85", ROOT / "u2_2d" / "scripts" / "85_coverage_seed_quality_figure.py")
fig85 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fig85)

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out/u2_2d/figures/fig60_coverage_money.png"))
    args = ap.parse_args()

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.6), sharey=True)

    for ax, L in zip(axes, (32, 64)):
        arms = fig85.load("u2", L)
        if not arms:
            print(f"no data for L={L}")
            return 1
        for label, colour, ceil, xs, zs in arms:
            ax.plot(xs, zs, "-o", color=colour, ms=4.5, lw=1.7, label=label,
                    markeredgecolor="white", markeredgewidth=0.6, zorder=3)
            if np.isfinite(ceil) and xs.min() <= ceil <= xs.max() * 1.05:
                ax.axvline(ceil, color=colour, ls=":", lw=1.3, alpha=0.8, zorder=1)
        ax.axhspan(0, 2, color="#2ca02c", alpha=0.08, zorder=0)
        ax.axhline(2, color="#2ca02c", ls="--", lw=1.0, alpha=0.7, zorder=2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel(r"model coupling $\beta$", fontsize=10.5, color=INK)
        ax.set_title(f"$L={L}$" + ("   (no checkpoint trains above $L=32$)"
                                   if L == 64 else ""),
                     fontsize=10.5, color=INK, loc="left")
        ax.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=9)

    axes[0].set_ylabel(r"raw seed $Z=\max|z|$   (lower is better)",
                       fontsize=10.5, color=INK)
    axes[0].text(0.02, 2, " indistinguishable from exact", color="#2ca02c",
                 fontsize=8.5, va="bottom", transform=axes[0].get_yaxis_transform())

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False,
               fontsize=9.5, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Seed quality is set by distance to the checkpoint's own training "
                 "coverage, not by the coupling itself\n"
                 "(dotted vertical lines: each checkpoint's training ceiling; "
                 "checkpoints differ only in coverage)",
                 fontsize=11, color=INK, y=1.06)
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
