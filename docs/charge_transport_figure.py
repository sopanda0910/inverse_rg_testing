"""Standalone schematic PNG for the paper's Reverse Diffusion Model section:
how Q_fine is set equal to Q_coarse during sampling.

Companion to transport_pipeline_figure.py (the whole-pipeline overview); this
one zooms into the single box that overview labels "CHARGE CORRECTION +
CONTINUED DIFFUSION" and makes two facts legible on their own: (1) the three
"soft" mechanisms (conditioning, FiLM mean, reconstruction guidance) bias the
score but cannot change Q by themselves, since Q only moves when a plaquette
angle crosses +-pi; (2) exactness instead comes from a separate, deterministic
instanton-shift step, applied periodically once sigma is small and once more,
unconditionally, at the end.

    python charge_transport_figure.py
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


def box(ax, x, y, w, h, text, face, edge, fontsize=10.5, weight="normal",
        text_colour=INK, ls="-", lw=1.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.018",
                                 linewidth=lw, facecolor=face, edgecolor=edge,
                                 linestyle=ls, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_colour, zorder=4, weight=weight,
            linespacing=1.35)


def arrow(ax, p0, p1, colour=INK, ls="-", lw=1.6, rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13,
                                  linewidth=lw, color=colour, linestyle=ls,
                                  zorder=5, connectionstyle=f"arc3,rad={rad}"))


def main() -> int:
    fig, ax = plt.subplots(figsize=(12.6, 6.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 42)
    ax.axis("off")

    # ================= TOP: the reverse-SDE timeline =====================
    ROW = 31.5
    H = 7.0

    ax.text(0.5, 40.5, r"noise level $\sigma$ during the reverse SDE, "
                        r"$\sigma_{\max}\rightarrow0$",
            ha="left", va="top", fontsize=10.5, color=MUTED, style="italic")

    box(ax, 1.0, ROW, 17.5, H, "PURE NOISE\n" + r"$\sigma=\sigma_{\max}$",
        "#f4f4f4", MUTED, weight="bold")

    box(ax, 21.5, ROW, 30.0, H,
        "REVERSE SDE STEPS\nscore $s_\\theta$ + 3 soft mechanisms:\n"
        "conditioning, FiLM mean, guidance",
        "#fdf0e6", ORANGE, weight="bold", fontsize=9.6)

    box(ax, 54.5, ROW, 26.0, H,
        "SAME STEPS, PLUS A\nDISCRETE PROJECTION EVERY\n"
        "10 STEPS ($\\sigma<0.5$)",
        "#fdf0e6", ORANGE, weight="bold", fontsize=9.6)

    box(ax, 83.5, ROW, 15.5, H, "FINAL, UNCONDITIONAL\nPROJECTION\n"
        r"$\Rightarrow Q_{\rm fine}=Q_{\rm coarse}$",
        "#eaf7ec", GREEN, weight="bold", fontsize=9.6)

    for x0, x1 in ((18.5, 21.5), (51.5, 54.5), (80.5, 83.5)):
        arrow(ax, (x0, ROW + H / 2), (x1, ROW + H / 2))

    # threshold marker between the two orange boxes
    ax.plot([54.5, 54.5], [ROW - 1.0, ROW + H + 1.0], color=MUTED,
             lw=1.0, ls=(0, (2, 2)), zorder=2)
    ax.text(54.5, ROW - 1.6, r"$\sigma$ drops below $\approx0.5$"
                              "\n(Q becomes well defined)",
            ha="center", va="top", fontsize=8.8, color=MUTED)

    # periodic projection ticks inside the second orange box
    tick_y0 = ROW - 3.4
    for tx in (60.5, 66.0, 71.5, 77.0):
        arrow(ax, (tx, ROW), (tx, tick_y0), colour=GREEN, lw=1.3,
              ls=(0, (3, 2)))
    ax.text(68.5, tick_y0 - 0.6, "periodic projection ticks\n(every 10 steps)",
            ha="center", va="top", fontsize=8.8, color=GREEN)

    # soft mechanisms cannot change Q -- annotation under first orange box
    ax.annotate("", xy=(36.5, ROW - 0.3), xytext=(36.5, ROW - 3.2),
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=1.0,
                                 linestyle=(0, (2, 2))))
    ax.text(36.5, ROW - 3.6,
            "gauge-covariant curl deformation:\n"
            r"leaves $Q$ invariant until a plaquette"
            "\nangle actually crosses " + r"$\pm\pi$",
            ha="center", va="top", fontsize=8.6, color=MUTED, style="italic")

    # ================= BOTTOM: the projection step itself =================
    ibox_top = 20.0
    ibox_y = 0.6
    ibox_h = ibox_top - ibox_y
    ax.add_patch(FancyBboxPatch((1.0, ibox_y), 98.0, ibox_h,
                                 boxstyle="round,pad=0.02", linewidth=1.2,
                                 facecolor="none", edgecolor=MUTED,
                                 linestyle=(0, (5, 3)), zorder=2))
    ax.text(1.8, ibox_top - 0.9, "THE PROJECTION STEP  (apply_coarse_charge, "
                                  "no accept/reject)",
            fontsize=9.8, color=MUTED, weight="bold", va="top")

    IROW = 8.0
    IH = 7.0
    box(ax, 3.5, IROW, 20.0, IH,
        r"$\Delta Q=Q_{\rm coarse}-Q_{\rm fine}(\theta)$",
        "#eaf3fa", BLUE, fontsize=10.0)
    box(ax, 27.0, IROW, 26.0, IH,
        r"add $\Delta Q$ copies of the smooth"
        "\nunit-winding instanton field, rewrap",
        "#fdf0e6", ORANGE, fontsize=9.6)
    box(ax, 56.5, IROW, 16.0, IH,
        r"$\Delta Q=0$?",
        "#f4f4f4", MUTED, fontsize=10.0)
    box(ax, 76.0, IROW, 21.0, IH,
        r"done: $Q_{\rm fine}=Q_{\rm coarse}$"
        "\nexactly",
        "#eaf7ec", GREEN, weight="bold", fontsize=9.6)

    for x0, x1 in ((23.5, 27.0), (53.0, 56.5), (72.5, 76.0)):
        arrow(ax, (x0, IROW + IH / 2), (x1, IROW + IH / 2))

    # loop-back arrow: not converged -> re-add the (updated) instanton shift
    arrow(ax, (64.5, IROW), (40.0, IROW - 3.2), colour=MUTED, lw=1.4,
          rad=-0.25)
    ax.text(52.0, IROW - 4.4, "iterate up to 3x (catches a shift that "
                               "itself\ncrosses another plaquette past "
                               r"$\pm\pi$" + ")",
            ha="center", va="top", fontsize=8.6, color=MUTED)

    fig.tight_layout()
    fig.savefig("charge_transport_schematic.png", dpi=300,
                bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote charge_transport_schematic.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
