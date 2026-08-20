"""Figures 44-45 -- the two schematics the paper needs and no run produces.

  44_pipeline      what the method is, with the EXACT steps and the LEARNED step
                   drawn differently. The paper's correctness claim attaches to
                   the HMC tail, not to the model, so the reader has to be able
                   to see at a glance which arrows carry exactness. Solid arrows
                   are exact (detailed balance or an identity); the single
                   dashed arrow is the learned prolongation, which has no
                   accept/reject and makes no exactness claim of its own.

  45_architecture  the gauge-covariant score network. Two things earn the panel:
                   the invariant input / curl output sandwich, which makes the
                   whole map gauge-covariant by construction rather than by
                   training, and the (sigma, beta) FiLM path, which is what lets
                   one checkpoint serve every rung of the ladder and extrapolate
                   15x in coupling.

Both are drawn from the deployed checkpoint's own configuration, read at run
time, so a retrained model with different widths cannot silently leave a stale
diagram behind.

    python u1_2d/scripts/57_schematics.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _figstyle import ARM, INK, MUTED  # noqa: E402

OUT = REPO / "out" / "u1_2d"
FIG = OUT / "paper_appendix" / "figures"

EXACT_C = ARM["hmc+inst"][0]
LEARNED_C = ARM["seed"][0]
IMPOSED_C = ARM["cold"][0]


def box(ax, x, y, w, h, text, color, *, fill=0.10, fontsize=9, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                                facecolor=color, alpha=fill, edgecolor=color,
                                linewidth=1.6, zorder=3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize,
            color=INK, zorder=5, linespacing=1.45, fontweight=weight)


def arrow(ax, xy_from, xy_to, color, *, dashed=False, label=None, rad=0.0,
          label_offset=(0, 0.028), fontsize=7.5):
    ax.add_patch(FancyArrowPatch(xy_from, xy_to, arrowstyle="-|>",
                                 mutation_scale=15, color=color, lw=1.7,
                                 linestyle=((0, (4, 2.5)) if dashed else "-"),
                                 shrinkA=3, shrinkB=3, zorder=4,
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        mx = (xy_from[0] + xy_to[0]) / 2 + label_offset[0]
        my = (xy_from[1] + xy_to[1]) / 2 + label_offset[1]
        ax.text(mx, my, label, ha="center", va="bottom", fontsize=fontsize,
                color=color, zorder=5, linespacing=1.35)


def fig_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(11.0, 4.9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    y, h, w = 0.44, 0.24, 0.175
    xs = [0.025, 0.265, 0.505, 0.745]

    box(ax, xs[0], y, w, h,
        "coarse ensemble\n" r"$L_c,\ \beta_c$" "\nHMC + winding update", EXACT_C)
    box(ax, xs[1], y, w, h,
        "learned prolongation\n" r"$L_c \to 2L_c,\ \beta_c \to \beta_f$" "\n"
        "reverse diffusion", LEARNED_C, fill=0.14)
    box(ax, xs[2], y, w, h,
        "sector transport\n" r"impose $Q_c$ on the fine field" "\n"
        r"($\langle Q^2\rangle$ is a ladder fixed point)", IMPOSED_C)
    box(ax, xs[3], y, w, h,
        "HMC tail\n" r"$0$-$8$ trajectories" "\n" "exact by detailed balance",
        EXACT_C, weight="bold")

    mid = y + h / 2
    arrow(ax, (xs[0] + w, mid), (xs[1], mid), LEARNED_C, dashed=True,
          label="no accept/reject\nno exactness claim", label_offset=(0, 0.035))
    arrow(ax, (xs[1] + w, mid), (xs[2], mid), IMPOSED_C, label="imposed,\nnot learned")
    arrow(ax, (xs[2] + w, mid), (xs[3], mid), EXACT_C, label="exact")

    box(ax, xs[3], 0.145, w, 0.15, "measurement\n" r"$\langle W(R\times T)\rangle$, "
                                  r"$\langle Q^2\rangle$, $\ldots$", EXACT_C, fill=0.05)
    arrow(ax, (xs[3] + w / 2, y), (xs[3] + w / 2, 0.295), EXACT_C)

    # the ladder as the outer loop: the fine ensemble becomes the next coarse one
    ax.add_patch(FancyArrowPatch((xs[3] + w / 2, y + h), (xs[0] + w / 2, y + h),
                                 arrowstyle="-|>", mutation_scale=15, color=MUTED,
                                 lw=1.5, shrinkA=4, shrinkB=4, zorder=2,
                                 connectionstyle="arc3,rad=0.32"))
    ax.text(0.5, 0.955, r"ladder: the fine ensemble is the next rung's coarse ensemble  "
                        r"($L \to 2L$, $\beta \to 4\beta$)",
            ha="center", va="center", fontsize=9, color=MUTED, style="italic")

    ax.text(0.012, 0.055, "solid = exact (detailed balance, or an identity)   ·   "
                          "dashed = learned, no exactness claim of its own",
            fontsize=8.5, color=MUTED, ha="left")
    ax.text(0.012, 0.005,
            "Correctness attaches to the HMC chain started from the seed, not to the "
            "model's output. The model is an initializer; the sector is supplied by the "
            "ladder identity.",
            fontsize=7.5, color=MUTED, ha="left")

    fig.suptitle("Learned prolongation: what is exact, and what is not",
                 fontsize=12.5, color=INK, x=0.008, ha="left", y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG / "44_pipeline.png", dpi=200)
    plt.close(fig)
    print("wrote 44_pipeline.png")


def fig_architecture() -> None:
    ckpt = torch.load(OUT / "checkpoints" / "score_net.pt", map_location="cpu",
                      weights_only=False)
    kw = ckpt["model_kwargs"]
    n_params = sum(v.numel() for v in ckpt["model_state"].values())
    hidden, depth = kw["hidden"], kw["depth"]
    cond_ch, k = kw["cond_channels"], kw["kernel_size"]

    fig, ax = plt.subplots(figsize=(11.0, 5.1))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    y, h, w = 0.47, 0.25, 0.155
    xs = [0.020, 0.215, 0.410, 0.605, 0.812]

    box(ax, xs[0], y, w, h,
        r"noisy links $\theta$" "\n" r"$[B, 2, L, L]$" "\n"
        r"coarse field $c$", MUTED, fill=0.07)
    box(ax, xs[1], y, w, h,
        "gauge-invariant\nfeatures\n"
        rf"$\cos/\sin$ of plaquette" "\n" rf"and $1\!\times\!2$, $2\!\times\!1$ rectangles"
        "\n" rf"$[B, {6 + cond_ch}, L, L]$", EXACT_C, fontsize=8)
    box(ax, xs[2], y, w, h,
        f"{depth} FiLM residual\nblocks\n"
        rf"${k}\times{k}$ circular conv" "\n" rf"width {hidden}", LEARNED_C, fontsize=8.5)
    box(ax, xs[3], y, w, h,
        "scalar head\n" r"$h(x)$, one per plaquette" "\n"
        r"$+$ gated analytic" "\n" r"Wilson force", LEARNED_C, fontsize=8)
    box(ax, xs[4], y, w, h,
        "plaquette curl\n" r"$s_\mu(x) = h(x) - h(x - \hat\nu)$" "\n"
        r"$[B, 2, L, L]$", EXACT_C, fontsize=8.5)

    mid = y + h / 2
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, (a + w, mid), (b, mid), MUTED)

    box(ax, xs[2] - 0.10, 0.185, 0.30, 0.145,
        r"FiLM embedding from $(\log\sigma,\ \log\beta)$" "\n"
        rf"plus the coarse winding density $2\pi Q_c / V$",
        IMPOSED_C, fontsize=8.5)
    for x in (xs[2], xs[3]):
        arrow(ax, (x + w / 2, 0.33), (x + w / 2, y), IMPOSED_C)

    ax.text(xs[1] + w / 2, y + h + 0.035, "gauge invariance in",
            ha="center", fontsize=8.5, color=EXACT_C, fontweight="bold")
    ax.text(xs[4] + w / 2, y + h + 0.035, "gauge covariance out",
            ha="center", fontsize=8.5, color=EXACT_C, fontweight="bold")
    ax.annotate("", xy=(xs[4] + w, y + h + 0.075),
                xytext=(xs[1], y + h + 0.075),
                arrowprops=dict(arrowstyle="-", color=EXACT_C, lw=1.2,
                                connectionstyle="arc3,rad=-0.09"))

    ax.text(0.012, 0.02,
            "The curl head is COMPLETE, not merely contained in the covariant class: every "
            "gauge-covariant field with vanishing holonomy is a plaquette curl,\n"
            "so the parameterization costs no expressiveness. No layer sees $L$ -- the "
            "convolutions are circular and the normalization is per-site -- which is why one "
            "checkpoint serves\nevery rung and extrapolates in coupling.",
            fontsize=7.5, color=MUTED, ha="left", linespacing=1.5)

    fig.suptitle(f"The gauge-covariant score network   ({n_params:,} parameters, "
                 f"depth {depth}, width {hidden})",
                 fontsize=12.5, color=INK, x=0.008, ha="left", y=0.985)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(FIG / "45_architecture.png", dpi=200)
    plt.close(fig)
    print(f"wrote 45_architecture.png  ({n_params:,} parameters)")


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_pipeline()
    fig_architecture()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
