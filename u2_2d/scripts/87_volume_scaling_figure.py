"""Volume scaling, resolved by training coverage.

The companion to `86_coverage_money_figure.py` (which holds volume fixed and
scans coupling). Here coupling is aggregated and VOLUME is the axis: how much
does the seed degrade one volume up, and does wider coupling coverage protect
against it?

Scored on the endpoint of record (raw seed Z at record 0). Points are the
median over that volume's couplings; bars span the interquartile range, so the
spread behind each median is visible rather than implied -- seed quality is
rugged from one coupling to its neighbour, and a bare median would hide that.

No checkpoint trains above L=32, and `wide`'s entire coverage extension sits
at L=8, so any difference in SLOPE here is coupling coverage transferring
across volume rather than exposure to the volume itself.

    python u2_2d/scripts/87_volume_scaling_figure.py
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
VOLS = (32, 64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out/u2_2d/figures/fig61_volume_scaling.png"))
    args = ap.parse_args()

    series = {}
    for L in VOLS:
        for label, colour, ceil, xs, zs in fig85.load("u2", L):
            series.setdefault(label, {"colour": colour})[L] = np.asarray(zs)

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    x = np.arange(len(VOLS))
    off = np.linspace(-0.055, 0.055, len(series))

    for k, (label, d) in enumerate(series.items()):
        med, lo, hi = [], [], []
        for L in VOLS:
            z = d[L]
            q1, q2, q3 = np.percentile(z, [25, 50, 75])
            med.append(q2); lo.append(q2 - q1); hi.append(q3 - q2)
        ax.errorbar(x + off[k], med, yerr=[lo, hi], color=d["colour"], lw=2.0,
                    marker="o", ms=7, capsize=4, markeredgecolor="white",
                    markeredgewidth=0.8, label=label, zorder=3)
        factor = med[1] / med[0]
        ax.annotate(f"×{factor:.1f}", (x[1] + off[k], med[1]), fontsize=9,
                    color=d["colour"], xytext=(11, 0), textcoords="offset points",
                    va="center", fontweight="bold")

    ax.axhspan(0, 2, color="#2ca02c", alpha=0.08, zorder=0)
    ax.axhline(2, color="#2ca02c", ls="--", lw=1.0, alpha=0.7, zorder=1)
    ax.text(0.01, 2, " indistinguishable from exact", color="#2ca02c",
            fontsize=8.5, va="bottom", transform=ax.get_yaxis_transform())

    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"$L={L}$\n$V={2*L*L}$" for L in VOLS], fontsize=10)
    ax.set_xlim(-0.35, len(VOLS) - 0.55)
    ax.set_ylabel(r"raw seed $Z=\max|z|$, median over couplings"
                  "\n(lower is better)", fontsize=10.5, color=INK)
    ax.set_title("One volume up, narrow coverage degrades an order of magnitude "
                 "and wide coverage barely moves\n"
                 r"annotations: median $Z$ at $L{=}64$ relative to $L{=}32$; "
                 "bars are the interquartile range over couplings",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    ax.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    print(f"wrote {out}")
    for label, d in series.items():
        m32, m64 = np.median(d[32]), np.median(d[64])
        print(f"  {label:<44} L=32 {m32:7.2f}  L=64 {m64:7.2f}  x{m64/m32:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
