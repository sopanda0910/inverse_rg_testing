"""Method schematic: the reverse-diffusion chain, drawn as a chain.

Replaces the box-flow `transport_pipeline_figure.py`. The box version could say
WHAT the stages are but not WHEN the charge projection acts, and "acts inside
the reverse trajectory rather than after it" is the one structural claim of the
method that a box diagram cannot carry.

Drawn in the node-and-arrow language standard for diffusion samplers: the
sigma ladder is the spine, running right to left from the prior to the delivered
configuration; the Langevin corrector is a sub-chain hanging below the spine
inside a dashed box; the two conditioning mechanisms enter from above.

Three drawing rules, all of them there for a reason:

  * Labels carry names and update rules only. Everything explanatory lives in
    the caption, so the type can be set at 9-11 pt and still survive the
    downscale to a two-column figure* (authored 6.9 in, displayed ~6.5 in).
  * No two arrows cross, and no arrow crosses a box outline. The corrector's
    descending and returning arrows run parallel in separate columns rather
    than curving through each other, and the dashed corrector box has gaps cut
    in its top edge where those columns pass.
  * The projection arrows enter on the LATE half of the chain because that is
    when the projection fires. Its position is the mechanism, not decoration.

Three things the diagram has to get right, all read off `u1_2d/model/sampler.py`
and `u1_2d/pipeline/ladder.py` rather than from prose:

  * The prior is UNIFORM on the circle, not a standard normal. The forward
    kernel is a wrapped Gaussian, whose sigma -> infinity limit is the uniform
    measure on the torus, and `sample_ancestral` starts from
    `rand * 2pi - pi` accordingly. Drawing N(0, I) here would be wrong.
  * The corrector runs at the noise level the predictor just ARRIVED at
    (`sigma_next`), not the one it left, so it hangs below the node it returns
    to. It is one step, not a sub-chain of many.
  * The projection is a step_callback applied AFTER the predictor+corrector
    block, gated on `sigma_next < charge_projection_sigma` and firing every
    `charge_projection_interval`-th such step -- plus once unconditionally after
    the loop. Both firings are drawn.

    python docs/reverse_diffusion_figure.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

# The paper's typeface, shared with every other paper figure.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "u1_2d" / "scripts"))
from _figstyle import PAPER_BOLD, apply_paper_font  # noqa: E402

apply_paper_font()

INK, MUTED = "#1a1a1a", "#5c5c5c"
SPINE_E, SPINE_F = "#B5540A", "#F3D3B3"
CORR_E, CORR_F = "#0072B2", "#CBE0F0"
GREEN, GREEN_F = "#1f7a4d", "#eaf7ec"
GREY_F = "#f0f0f0"

W = 6.9
YLO, YHI = 8.0, 63.0
H = W * (YHI - YLO) / 100.0

ROW = 40.0          # the sigma ladder
R = 4.2             # spine node radius
RC = 3.6            # corrector node radius
CORR_Y = 21.5
DX = 2.3            # half-separation of the corrector's two arrow columns


def node(ax, x, y, label, face, edge, r=R, fontsize=10.5):
    ax.add_patch(Circle((x, y), r, facecolor=face, edgecolor=edge, lw=1.7,
                        zorder=4))
    ax.text(x, y, label, ha="center", va="center", fontsize=fontsize,
            color=INK, zorder=5)


def arrow(ax, p0, p1, colour=INK, lw=1.7, ls="-", ms=14):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms,
                                 lw=lw, color=colour, linestyle=ls, zorder=3))


def dots(ax, x0, x1, y, colour=SPINE_E):
    """A dashed span standing for the omitted intermediate noise levels."""
    ax.plot([x0, x1], [y, y], color=colour, lw=1.7, ls=(0, (4, 3)), zorder=3)
    arrow(ax, ((x0 + x1) / 2 + 0.6, y), (x1 - 0.1, y), colour=colour)


def gapped_box(ax, x0, y0, x1, y1, gaps, colour, lw=1.4):
    """A dashed rectangle whose top edge is broken wherever an arrow passes, so
    no arrow ever crosses an outline."""
    dash = (0, (5, 3))
    for xs, ys in (([x0, x1], [y0, y0]), ([x0, x0], [y0, y1]),
                   ([x1, x1], [y0, y1])):
        ax.plot(xs, ys, color=colour, lw=lw, ls=dash, zorder=1)
    cuts = sorted(gaps)
    x = x0
    for a, b in cuts:
        if a > x:
            ax.plot([x, a], [y1, y1], color=colour, lw=lw, ls=dash, zorder=1)
        x = b
    if x < x1:
        ax.plot([x, x1], [y1, y1], color=colour, lw=lw, ls=dash, zorder=1)


def main() -> int:
    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, 100)
    ax.set_ylim(YLO, YHI)
    ax.set_aspect("equal")
    ax.axis("off")

    x_T, x_t, x_tm1, x_0 = 94.0, 74.0, 52.0, 28.0

    # ---------------- the sigma ladder, right to left ----------------
    for x, lab in ((x_T, r"$\phi_T$"), (x_t, r"$\phi_t$"),
                   (x_tm1, r"$\phi_{t-1}$"), (x_0, r"$\phi_0$")):
        node(ax, x, ROW, lab, SPINE_F, SPINE_E)

    dots(ax, x_T - R - 0.6, x_t + R + 0.6, ROW)
    arrow(ax, (x_t - R - 0.6, ROW), (x_tm1 + R + 0.6, ROW), colour=SPINE_E)
    dots(ax, x_tm1 - R - 0.6, x_0 + R + 0.6, ROW)

    ax.text(x_T, ROW - R - 2.2, r"$\phi_T \sim \mathrm{Unif}(-\pi,\pi]$",
            ha="center", va="top", fontsize=9.0, color=MUTED)

    # The predictor, in the gap kept clear for it between the two feed columns.
    # Written as an assignment on one line with the noise-step abbreviation
    # defined under it: the earlier two-line form began with a bare "+" and
    # buried sigma_{t-1}^2/sigma_t^2 inside the radical, where it set cramped.
    ax.text((x_t + x_tm1) / 2 - 5.0, ROW + R + 3.4,
            r"$\phi_{t-1} = \phi_t + \Delta_t\, s_\theta"
            r" + \dfrac{\sigma_{t-1}}{\sigma_t}\sqrt{\Delta_t}\; z$",
            ha="center", va="bottom", fontsize=8.0, color=SPINE_E)
    ax.text((x_t + x_tm1) / 2 - 5.0, ROW + R + 1.0,
            r"$\Delta_t = \sigma_t^2 - \sigma_{t-1}^2$",
            ha="center", va="bottom", fontsize=7.5, color=MUTED)

    # ---------------- what enters from above ----------------
    ax.add_patch(FancyBboxPatch((12.0, 53.0), 28.0, 7.5,
                                boxstyle="round,pad=0.4,rounding_size=1.2",
                                facecolor=GREEN_F, edgecolor=GREEN, lw=1.5,
                                zorder=2))
    ax.text(26.0, 56.75, r"$Q_{\rm coarse}$ (exact)", ha="center", va="center",
            fontsize=9.5, color=INK)

    ax.add_patch(FancyBboxPatch((64.0, 53.0), 29.0, 7.5,
                                boxstyle="round,pad=0.4,rounding_size=1.2",
                                facecolor="#eaf3fa", edgecolor=CORR_E, lw=1.5,
                                zorder=2))
    ax.text(78.5, 56.75, r"coarse field, $\sigma$, $\beta_1$", ha="center",
            va="center", fontsize=9.5, color=INK)

    arrow(ax, (x_t, 53.0), (x_t, ROW + R + 0.5), colour=CORR_E, lw=1.5,
          ls=(0, (3, 2)))
    arrow(ax, (x_0, 53.0), (x_0, ROW + R + 0.5), colour=GREEN, lw=1.8)
    # into phi_{t-1} on the diagonal, staying clear of the predictor label and
    # of the dashed spine span below it
    arrow(ax, (40.0, 53.3), (x_tm1 - 2.8, ROW + 3.2), colour=GREEN, lw=1.8)

    # ---------------- the Langevin corrector ---------------------------
    gapped_box(ax, 44.0, 10.0, 82.0, 30.0,
               [(x_tm1 - DX - 1.2, x_tm1 + DX + 1.2),
                (x_t - DX - 1.2, x_t + DX + 1.2)], CORR_E)
    for x in (x_t, x_tm1):
        node(ax, x, CORR_Y, r"$\tilde\phi$", CORR_F, CORR_E, r=RC, fontsize=10)
        arrow(ax, (x - DX, ROW - R - 0.4), (x - DX, CORR_Y + RC + 0.4),
              colour=CORR_E, lw=1.5, ls=(0, (3, 2)))
        arrow(ax, (x + DX, CORR_Y + RC + 0.4), (x + DX, ROW - R - 0.4),
              colour=SPINE_E, lw=1.6)

    ax.text(63.0, 15.6, "Langevin corrector", ha="center", va="center",
            fontsize=9.0, color=CORR_E, fontproperties=PAPER_BOLD)
    ax.text(63.0, 11.9,
            r"$\phi \leftarrow \phi + \epsilon\,s_\theta + \sqrt{2\epsilon}\,z$",
            ha="center", va="center", fontsize=9.0, color=MUTED)

    # ---------------- the projection, spelled out ----------------------
    ax.add_patch(FancyBboxPatch((2.0, 10.0), 37.0, 20.0,
                                boxstyle="round,pad=0.4,rounding_size=1.2",
                                facecolor="none", edgecolor=GREEN, lw=1.4,
                                linestyle=(0, (1, 2)), zorder=1))
    ax.text(20.5, 24.5, r"impose $Q_{\rm coarse}$", ha="center", va="center",
            fontsize=9.0, color=GREEN, fontproperties=PAPER_BOLD)
    ax.text(20.5, 19.0, r"$\Delta Q = Q_{\rm coarse} - Q(\phi)$",
            ha="center", va="center", fontsize=9.0, color=MUTED)
    ax.text(20.5, 14.0, r"$\phi \leftarrow \phi + \Delta Q\, I$",
            ha="center", va="center", fontsize=9.0, color=MUTED)

    # ---------------- what the chain delivers ---------------------------
    # The box is the PRODUCT, not the operation that makes it: labelling it
    # "exact tail" named the rethermalization sweeps, which read as a step
    # rather than as the configuration handed to HMC.
    ax.add_patch(FancyBboxPatch((2.0, 34.5), 16.5, 11.0,
                                boxstyle="round,pad=0.4,rounding_size=1.2",
                                facecolor=GREY_F, edgecolor=MUTED, lw=1.5,
                                zorder=2))
    ax.text(10.25, 40.0, "preconditioned\nconfiguration", ha="center",
            va="center", fontsize=9.0, color=INK, linespacing=1.4)
    arrow(ax, (x_0 - R - 0.6, ROW), (18.9, ROW), colour=MUTED)
    ax.text(10.25, 46.6, "ready for HMC", ha="center", va="bottom",
            fontsize=8.5, color=INK, fontproperties=PAPER_BOLD)
    ax.text(10.25, 33.3, "after exact local rethermalization", ha="center",
            va="top", fontsize=7.5, color=MUTED)

    fig.tight_layout(pad=0.2)
    # Beside this script, not in the working directory: run from the repo root
    # it used to drop the figure there instead of in docs/.
    out = Path(__file__).resolve().parent / "reverse_diffusion_schematic.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
