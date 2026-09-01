"""Standalone pipeline schematic PNG for the paper Method section.

Charge transport fires *inside* the reverse-diffusion trajectory once sigma
drops below a threshold, so the network still has steps left afterward to
relax the strain the correction introduces into the local (UV) structure --
drawn as an interleaving, not a bypass. beta_f is NOT the tree-level 4*beta_c
(the project uses the exact matched coupling); that is stated explicitly
rather than shown as a formula.

    python pipeline_figure.py
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.family"] = "STIXGeneral"
plt.rcParams["mathtext.fontset"] = "stix"

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#c9c9c9"
BLUE, ORANGE, GREEN, PURPLE = "#0072B2", "#B5540A", "#1f7a4d", "#5a3a8a"


def box(ax, x, y, w, h, text, face, edge, fontsize=9.0, weight="normal",
        text_colour=INK, ls="-", lw=1.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.018",
                                 linewidth=lw, facecolor=face, edgecolor=edge,
                                 linestyle=ls, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=text_colour, zorder=4, weight=weight,
            linespacing=1.4)


def arrow(ax, p0, p1, colour=INK, ls="-", lw=1.5, rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12,
                                  linewidth=lw, color=colour, linestyle=ls,
                                  zorder=5, connectionstyle=f"arc3,rad={rad}"))


def main() -> int:
    fig, ax = plt.subplots(figsize=(12.6, 5.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 33)
    ax.axis("off")

    ROW = 14.5
    H = 7.0

    # ---- main spine --------------------------------------------------
    box(ax, 1.0, ROW, 13.5, H, "COARSE\nENSEMBLE\n" + r"HMC, $\beta_c,\ L_c$",
        "#eaf3fa", BLUE, weight="bold")

    box(ax, 17.0, ROW, 12.0, H, "BLOCKING\nexact telescope\n"
        + r"$\Theta=\mathrm{wrap}(\Sigma\,\theta_{\rm fine})$",
        "#eaf7ec", GREEN, weight="bold")

    # reverse diffusion, split into two phases to show the mid-trajectory
    # charge injection rather than a single opaque box
    box(ax, 31.5, ROW, 15.5, H, "REVERSE DIFFUSION\n"
        + r"$\sigma:\ \sigma_{\max}\to\sigma_{\rm thr}$" + "\ngenerates UV structure",
        "#fdf0e6", ORANGE, weight="bold")

    box(ax, 49.5, ROW, 17.5, H, "CHARGE CORRECTION\n+ CONTINUED DIFFUSION\n"
        + r"$\sigma:\ \sigma_{\rm thr}\to 0$",
        "#fdf0e6", ORANGE, weight="bold")

    box(ax, 69.5, ROW, 11.5, H, "RETHERM.\nexact local sweeps\nno topological moves",
        "#f4f4f4", MUTED, fontsize=8.6)

    box(ax, 83.5, ROW, 15.5, H, "FINE SEED\nHMC tail delivers\nexactness",
        "#eaf3fa", "#111111", weight="bold")

    for x0, x1 in ((14.5, 17.0), (29.0, 31.5), (47.0, 49.5), (67.0, 69.5),
                   (81.0, 83.5)):
        arrow(ax, (x0, ROW + H / 2), (x1, ROW + H / 2))

    # ---- charge injection detail, drawn INSIDE the trajectory, ABOVE
    # the row so it never competes with anything below --------------
    inj_x = 49.5
    top_text_y = 31.6
    ax.plot([inj_x, inj_x], [ROW + H, top_text_y + 0.4], color=GREEN, lw=1.5,
            ls=(0, (4, 2)), zorder=2)

    ax.text(inj_x + 1.0, top_text_y,
            r"$+\ \Delta Q\cdot(\mathrm{fixed\ instanton\ field})$"
            + "\n" + r"$\Delta Q = Q_{\rm coarse}-Q(\mathrm{sample})$"
            + "\nadded directly to the links, every 10 steps while "
            + r"$\sigma<\sigma_{\rm thr}$,"
            + "\nplus one final exact pass",
            ha="left", va="top", fontsize=8.0, color=GREEN, linespacing=1.45)

    ax.text(inj_x - 1.0, top_text_y,
            "remaining reverse steps then\nrelax the local structure\n"
            "around the now-fixed sector",
            ha="right", va="top", fontsize=8.0, color=MUTED, style="italic",
            linespacing=1.45)

    # ---- coarse Q source, feeding the injection, BELOW the row -------
    src_x = 7.75
    feed_y = 12.4
    arrow(ax, (src_x, ROW), (src_x, feed_y), colour=GREEN, lw=1.5)
    ax.plot([src_x, inj_x], [feed_y, feed_y], color=GREEN, lw=1.5, zorder=2)
    arrow(ax, (inj_x, feed_y), (inj_x, ROW), colour=GREEN, lw=1.5)
    ax.text((src_x + inj_x) / 2, feed_y + 0.7,
            r"$Q_{\rm coarse}$ known exactly from the coarse ensemble"
            " (blocking is an exact telescope)",
            ha="center", va="bottom", fontsize=7.9, color=GREEN)

    # ---- U(2)-only branch, dashed, near the bottom --------------------
    ubox_y = 0.9
    ubox_h = 5.6
    ubox_top = 11.2
    ax.add_patch(FancyBboxPatch((31.5, 0.0), 35.5, ubox_top,
                                 boxstyle="round,pad=0.02", linewidth=1.1,
                                 facecolor="none", edgecolor=MUTED,
                                 linestyle=(0, (5, 3)), zorder=2))
    ax.text(32.3, ubox_top - 0.85, "U(2) ONLY — NO LEARNING IN THIS BRANCH",
            fontsize=7.8, color=MUTED, weight="bold", va="top")

    box(ax, 32.5, ubox_y, 16.0, 5.6,
        "NAIVE SU(2) SEED\nsplit each coarse SU(2) link\ninto two square-root halves",
        "#f5f0fa", PURPLE, fontsize=7.9, ls=(0, (4, 2)))
    box(ax, 50.5, ubox_y, 16.0, 5.6,
        "EXACT CONDITIONAL\nHEATBATH, 20–30 sweeps\n"
        + r"$p(q\mid\psi)$ at frozen $\psi_{\rm fine}$",
        "#eaf7ec", GREEN, fontsize=7.9, ls=(0, (4, 2)))
    arrow(ax, (48.5, ubox_y + 2.8), (50.5, ubox_y + 2.8), colour=MUTED)

    # psi_fine feeds the conditional (from the diffusion output)
    arrow(ax, (57.0, ROW), (58.5, ubox_y + 5.6), colour=MUTED, lw=1.1,
          ls=(0, (2, 2)), rad=0.1)
    ax.text(59.3, 8.6,
            r"$\psi_{\rm fine}$ freezes"
            "\nthe conditional",
            ha="left", va="center", fontsize=7.3, color=MUTED, style="italic",
            linespacing=1.3)

    # merges back up before rethermalization
    arrow(ax, (66.5, ubox_y + 4.0), (72.5, ROW), colour=GREEN, lw=1.3, rad=-0.25)

    ax.text(69.5, 11.4,
            "U(1) runs the top row only.\nU(2) adds this branch, applied to "
            + r"$\psi=\arg\det U$" + "\non the top row, and merges back "
            "before rethermalization.",
            ha="left", va="top", fontsize=7.9, color=MUTED, linespacing=1.45)

    # ---- title / caption -------------------------------------------
    fig.suptitle("One inverse-RG step: what the network generates, what is "
                 "transported, and where exactness comes from",
                 fontsize=13.0, color=INK, x=0.012, ha="left", y=0.99,
                 weight="bold")
    fig.text(0.012, 0.905,
             r"$L_f = 2L_c$; $\beta_f$ set by the exact matched-coupling "
             r"condition, not the tree-level $\beta_f = 4\beta_c$"
             "  —  the network never sees $Q$ as an input; the sector is "
             "imposed structurally mid-trajectory, not inferred.",
             fontsize=9.3, color=MUTED, ha="left")

    fig.tight_layout(rect=(0, 0, 1, 0.865))
    fig.savefig("transport_pipeline.png", dpi=300, bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("wrote transport_pipeline.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
