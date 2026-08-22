"""The pipeline schematic -- figure 1 of the paper, drawn once for both studies.

The last cosmetic gap in `docs/u2_2d/FIGURE_PARITY.md` (parity item #1). It is a
schematic, so nothing here is measured; what it must do is make three things
visually obvious, because each is a claim a reader would otherwise have to
reconstruct from prose:

  1. **Where the sampling actually happens.** At the BASE, at weak coupling,
     where HMC is ergodic in topology. Everything above it inherits.
  2. **That topology is transported, not generated.** The charge branch runs
     around the model, not through it. `enforce_coarse_charge` imposes the
     coarse charge on the fine configuration and the lift cannot alter it --
     measured exact, configuration by configuration, in
     `36_transport_check.py`.
  3. **Where exactness comes from.** The HMC tail, which is exact by detailed
     balance regardless of where it starts. The model is a proposal; nothing
     rests on its density, which is why a ~1 nat/site gap is a specification
     rather than a defect.

The SU(2) branch is drawn dashed and labelled `u2 only`, so one figure serves
both papers: in U(1) the field IS `psi` and that box is absent.

    python u2_2d/scripts/41_pipeline_schematic.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
BLUE, ORANGE, GREEN, PURPLE = "#0072B2", "#D55E00", "#2e7d32", "#5a3a8a"


def box(ax, x, y, w, h, text, face, edge, fontsize=8.5, weight="normal",
        style="round,pad=0.02", text_colour=INK, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, linewidth=1.4,
                                facecolor=face, edgecolor=edge, linestyle=ls,
                                zorder=3, mutation_scale=1.0))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_colour, zorder=4, weight=weight,
            linespacing=1.35)


def arrow(ax, p0, p1, colour=INK, ls="-", lw=1.5, rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13,
                                 linewidth=lw, color=colour, linestyle=ls,
                                 zorder=5,
                                 connectionstyle=f"arc3,rad={rad}"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="out/u2_2d/figures/fig28_pipeline.png")
    args = ap.parse_args()

    fig, ax = plt.subplots(figsize=(12.6, 4.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(-2, 40)
    ax.axis("off")

    ROW = 16.0
    H = 8.0

    # ---- the base --------------------------------------------------------
    box(ax, 1.5, ROW, 15.5, H,
        "COARSE BASE\n" + r"$L=8$, $\beta=3.5$" + "\nHMC + winding",
        "#eaf3fa", BLUE, weight="bold")
    ax.text(9.25, ROW - 2.4, "ergodic in topology here", ha="center",
            fontsize=7.5, color=BLUE, style="italic")
    ax.text(9.25, ROW - 4.6, "the only place P(Q) is SAMPLED",
            ha="center", fontsize=8, color=BLUE, weight="bold")

    # ---- the ladder ------------------------------------------------------
    box(ax, 21.0, ROW, 15.5, H,
        "DIFFUSION LIFT\n" + r"score net on $\psi$" + "\n"
        + r"cond. on model $\beta$", "#fdf0e6", ORANGE, weight="bold")
    ax.text(28.75, ROW - 2.4, "generates the determinant phase only",
            ha="center", fontsize=7.5, color=ORANGE, style="italic")

    box(ax, 40.5, ROW, 14.0, H,
        "IMPOSE Q\n" + r"$\mathtt{enforce\_coarse\_charge}$", "#eaf7ec", GREEN,
        weight="bold")

    box(ax, 58.5, ROW, 13.0, H,
        "SU(2) RESAMPLE\nexact conditional\n" + r"$p(q \mid \psi)$",
        "#f5f0fa", PURPLE, ls=(0, (4, 2)))
    ax.text(65.0, ROW - 2.4, "u2 only; leaves " + r"$\psi$" + " and Q untouched",
            ha="center", fontsize=7.5, color=PURPLE, style="italic")

    box(ax, 75.5, ROW, 10.0, H, "retherm\nsweeps", "#f4f4f4", MUTED)

    box(ax, 88.5, ROW, 10.0, H, "HMC TAIL\nexact", "#eaf3fa", "#111111",
        weight="bold")
    ax.text(93.5, ROW + H + 1.6, "exactness lives here", ha="center",
            fontsize=8, color="#111111", style="italic", weight="bold")

    for x0, x1 in ((17.0, 21.0), (36.5, 40.5), (54.5, 58.5), (71.5, 75.5),
                   (85.5, 88.5)):
        arrow(ax, (x0, ROW + H / 2), (x1, ROW + H / 2))

    # ---- the transport branch: around the model, not through it ----------
    # Three straight segments at a fixed height, so the label sits ABOVE the
    # line. A single curved arc put the text through its own path.
    TOP = ROW + H + 5.0
    arrow(ax, (9.25, ROW + H), (9.25, TOP), colour=GREEN, lw=1.8)
    ax.plot([9.25, 47.5], [TOP, TOP], color=GREEN, lw=1.8, zorder=5,
            solid_capstyle="butt")
    arrow(ax, (47.5, TOP), (47.5, ROW + H), colour=GREEN, lw=1.8)
    ax.text(28.4, TOP + 1.5, "Q is TRANSPORTED, not generated",
            ha="center", fontsize=9.5, color=GREEN, weight="bold")
    ax.text(28.4, TOP - 2.5, "the coarse charge bypasses the network entirely",
            ha="center", fontsize=7.5, color=GREEN, style="italic")

    # ---- the ladder repeat: a loop UNDER the row, back to the lift -------
    # Descends OUTSIDE the last box and returns OUTSIDE the first, so the loop
    # never crosses a caption.
    BOT = ROW - 8.4
    ax.plot([99.4, 99.4], [ROW + H / 2, BOT], color=MUTED, lw=1.3,
            ls=(0, (5, 3)), zorder=2)
    ax.plot([99.4, 19.4], [BOT, BOT], color=MUTED, lw=1.3, ls=(0, (5, 3)),
            zorder=2)
    arrow(ax, (19.4, BOT), (19.4, ROW + H / 2), colour=MUTED, lw=1.3,
          ls=(0, (5, 3)))
    ax.text(60.0, BOT + 1.3,
            "repeat: each step doubles L and takes " + r"$\beta_c$"
            + " to " + r"$4\beta_c$" + "    ("
            + r"$\langle Q^2\rangle \approx V/4\pi^2\beta$"
            + " is a FIXED POINT of that map, so P(Q) is preserved)",
            ha="center", fontsize=8, color=MUTED)

    # ---- the punchline ---------------------------------------------------
    ax.text(50, BOT - 6.5,
            "The configuration delivered at " + r"$\beta = 416$"
            + " carries a topological charge drawn at " + r"$\beta = 3.5$"
            + ", where sampling works.\n"
            "HMC at the target coupling cannot produce that at any cost: it is "
            "frozen, so it keeps whatever charge it started with.",
            ha="center", fontsize=9, color=INK, linespacing=1.5,
            bbox=dict(boxstyle="round,pad=0.6", facecolor="#fbfbfb",
                      edgecolor=GRID, linewidth=1.0))

    fig.suptitle("Learned prolongation: what is generated, what is transported, "
                 "and where exactness comes from",
                 fontsize=12.5, color=INK, x=0.02, ha="left", y=0.98)
    fig.tight_layout()
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
