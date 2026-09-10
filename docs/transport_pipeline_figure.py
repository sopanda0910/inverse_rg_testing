"""Standalone pipeline schematic PNG for the paper Method section.

Stripped to the flow chart itself -- box labels only, no paragraph-length
annotations -- because at print size in the paper the small explanatory text
became illegible; the mechanism is explained in the surrounding prose
instead. The diagram alone must still make the two facts legible on its own:
(1) charge correction is injected mid-trajectory, inside the reverse
diffusion, not appended after it; (2) the U(2) SU(2) branch is exact and
never learned.

    python pipeline_figure.py
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.family"] = "STIXGeneral"
plt.rcParams["mathtext.fontset"] = "stix"

INK, MUTED = "#1a1a1a", "#5c5c5c"
BLUE, ORANGE, GREEN, PURPLE = "#0072B2", "#B5540A", "#1f7a4d", "#5a3a8a"


def box(ax, x, y, w, h, text, face, edge, fontsize=11.0, weight="normal",
        text_colour=INK, ls="-", lw=1.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.018",
                                 linewidth=lw, facecolor=face, edgecolor=edge,
                                 linestyle=ls, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_colour, zorder=4, weight=weight,
            linespacing=1.4)


def arrow(ax, p0, p1, colour=INK, ls="-", lw=1.7, rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14,
                                  linewidth=lw, color=colour, linestyle=ls,
                                  zorder=5, connectionstyle=f"arc3,rad={rad}"))


def main() -> int:
    # Authored near the width it is displayed at in the paper (\linewidth of a
    # two-column figure*, 6.5 in). Drawn much wider than that, every label is
    # downscaled and the subscripts, at 0.7x again, become unreadable.
    fig, ax = plt.subplots(figsize=(9.0, 3.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 24.5)
    ax.axis("off")

    ROW = 15.5
    H = 8.0

    # ---- main spine --------------------------------------------------
    box(ax, 1.0, ROW, 13.5, H, "COARSE\nENSEMBLE\n" + r"HMC, $\beta_c,\ L_c$",
        "#eaf3fa", BLUE, weight="bold")

    box(ax, 17.0, ROW, 12.0, H, "BLOCKING\n(exact)",
        "#eaf7ec", GREEN, weight="bold")

    box(ax, 31.5, ROW, 15.5, H, "REVERSE\nDIFFUSION\n(learned)",
        "#fdf0e6", ORANGE, weight="bold")

    box(ax, 49.5, ROW, 17.5, H, "CHARGE\nCORRECTION\n+ CONTINUED\nDIFFUSION",
        "#fdf0e6", ORANGE, weight="bold")

    box(ax, 69.5, ROW, 11.5, H, "RETHERM.\n(exact)",
        "#f4f4f4", MUTED)

    box(ax, 83.5, ROW, 15.5, H, "FINE SEED\nfor HMC",
        "#eaf3fa", "#111111", weight="bold")

    for x0, x1 in ((14.5, 17.0), (29.0, 31.5), (47.0, 49.5), (67.0, 69.5),
                   (81.0, 83.5)):
        arrow(ax, (x0, ROW + H / 2), (x1, ROW + H / 2))

    # ---- the coarse charge, from its source into the correction step ----
    # One labelled path, not two. An extra arrow leaving the top of the box
    # duplicated this and pointed out of the step rather than into it.
    # "coarse" is a word rather than a subscript: a subscript sets at 0.7x and
    # was the smallest text in the figure.
    src_x = 7.75
    inj_x = 53.0
    feed_y = 13.0
    arrow(ax, (src_x, ROW), (src_x, feed_y), colour=GREEN, lw=1.6)
    ax.plot([src_x, inj_x], [feed_y, feed_y], color=GREEN, lw=1.6, zorder=2)
    arrow(ax, (inj_x, feed_y), (inj_x, ROW), colour=GREEN, lw=1.6)
    ax.text((src_x + inj_x) / 2, feed_y - 0.6, r"impose coarse $Q$ (exact)",
            ha="center", va="top", fontsize=13.0, color=GREEN, weight="bold")

    # ---- U(2)-only branch, dashed, below --------------------------
    # Sized so the widest label ("EXACT CONDITIONAL") clears its box, the two
    # boxes do not touch, and the "U(2) ONLY" tag sits clear of both the
    # container edge and the boxes below it.
    ubox_y, ubox_h = 0.8, 6.0
    ubox_top = 9.6
    ax.add_patch(FancyBboxPatch((29.5, 0.0), 41.0, ubox_top,
                                 boxstyle="round,pad=0.02", linewidth=1.2,
                                 facecolor="none", edgecolor=MUTED,
                                 linestyle=(0, (5, 3)), zorder=2))
    ax.text(30.4, ubox_top - 0.6, "U(2) ONLY", fontsize=10.5, color=MUTED,
            weight="bold", va="top")

    box(ax, 31.0, ubox_y, 17.0, ubox_h,
        "NAIVE SU(2) SEED\n(inverse block)",
        "#f5f0fa", PURPLE, fontsize=9.0, ls=(0, (4, 2)))
    box(ax, 52.0, ubox_y, 17.0, ubox_h,
        "EXACT CONDITIONAL\nHEATBATH\n" + r"$p(q\mid\psi)$",
        "#eaf7ec", GREEN, fontsize=9.0, ls=(0, (4, 2)))
    arrow(ax, (48.0, ubox_y + ubox_h / 2), (52.0, ubox_y + ubox_h / 2),
          colour=MUTED)

    # psi_fine feeds the conditional (from the diffusion output). Kept clear of
    # the charge feed, which now enters the same box from below at x = 53.
    arrow(ax, (62.0, ROW), (60.5, ubox_y + ubox_h), colour=MUTED, lw=1.2,
          ls=(0, (2, 2)), rad=0.1)

    # Merges back up before rethermalization. Leaves from the right EDGE of the
    # green box, not its top corner, so it does not cut across the border.
    arrow(ax, (69.8, ubox_y + ubox_h / 2), (73.5, ROW), colour=GREEN,
          lw=1.5, rad=-0.18)

    fig.tight_layout()
    fig.savefig("transport_pipeline.png", dpi=300, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("wrote transport_pipeline.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
