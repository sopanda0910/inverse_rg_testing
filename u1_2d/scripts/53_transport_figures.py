"""Figures 33-36 -- why the seed lands in the right topological sector.

The prolongator claim has two halves. Script 50 draws the half about
thermalization cost; these four panels draw the half about topology, which is
the one a referee attacks first, because a local score network with a finite
receptive field plainly cannot control a global integer.

The answer the study gives is that it never has to:

  33_ladder_fixed_point  the exact <Q^2> is a FIXED POINT of the ladder, so the
                         coarse ensemble's P(Q) *is* the fine theory's P(Q).
                         Transport is an identity, not an approximation.
  34_match_rate_volume   what the model contributes on its own, and it degrades
                         with volume -- 0.484 / 0.234 / 0.094 at L = 16/32/64.
                         Drawn because the paper's protocol item 9 requires the
                         raw pre-enforcement number to be reported.
  35_sector_freeze_sigma reverse-diffusion sector changes die at sigma ~ 0.31,
                         flat across a 16x volume range. This is the mechanism
                         behind 34: below sigma_freeze the sector is already
                         decided, so the remaining sampling cannot fix it.
  36_sector_tail         the instanton-HMC tail repairing P(Q), the route that
                         needs no analytic P(Q) and so transfers to theories
                         where none exists.

    python u1_2d/scripts/53_transport_figures.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))

from _figstyle import ARM, INK, MUTED, dress, panel_tag, title  # noqa: E402

from u1_2d.lgt import exact  # noqa: E402

OUT = REPO / "out" / "u1_2d"
FIG = OUT / "paper_appendix" / "figures"


BASE_BETA = 1.3471894926775612          # matched coarse partner of beta_f = 4
# the campaign's own Wilson rungs, from the character-convolution MLE matching
WILSON_LADDER = [(8, BASE_BETA), (16, 4.0), (32, 14.1464), (64, 55.0237),
                 (128, 218.58)]
# Villain, where beta_c = beta_f / 4 is exact rather than a tree-level relation
VILLAIN_LADDER = [(8, BASE_BETA), (16, 4 * BASE_BETA), (32, 16 * BASE_BETA),
                  (64, 64 * BASE_BETA), (128, 256 * BASE_BETA)]


def fig_ladder_fixed_point() -> None:
    """Exact <Q^2> under (V, beta) -> (4V, 4beta), five rungs, both actions."""
    fig, ax = plt.subplots(figsize=(6.9, 4.25))

    for action, ladder, color, marker, dy in (
            ("villain", VILLAIN_LADDER, ARM["seed"][0], "o", -18),
            ("wilson", WILSON_LADDER, ARM["hmc+inst"][0], "D", 12)):
        q2 = [exact.topological_susceptibility_exact(b, action, L) * L * L
              for L, b in ladder]
        ax.plot(range(len(ladder)), q2, color=color, marker=marker, ms=7, lw=2.0,
                markeredgecolor="white", markeredgewidth=0.7,
                label=("Villain, " r"$\beta_c=\beta_f/4$ exact"
                       if action == "villain"
                       else "Wilson, campaign matched rungs"), zorder=4)
        for i, v in enumerate(q2):
            ax.annotate(f"{v:.5f}", (i, v), textcoords="offset points",
                        xytext=(0, dy), ha="center", fontsize=8, color=color)
        print(f"  {action:8s} " + "  ".join(f"{v:.5f}" for v in q2))

    ax.set_xticks(range(len(WILSON_LADDER)))
    ax.set_xticklabels([rf"$L={L}$" for L, _ in WILSON_LADDER],
                       fontsize=9, color=INK)
    ax.set_xlim(-0.35, len(WILSON_LADDER) - 0.65)
    ax.set_ylim(1.05, 2.15)
    ax.set_xlabel(r"ladder rung  ($L \to 2L$, $\beta \to 4\beta$)", fontsize=10, color=INK)
    ax.set_ylabel(r"exact finite-volume $\langle Q^2 \rangle$", fontsize=10, color=INK)
    title(ax, r"Sector transport is an identity: $\langle Q^2\rangle$ is a fixed point"
              " of the ladder")
    dress(ax)
    ax.legend(fontsize=9, frameon=False, labelcolor=INK, loc="center right")
    fig.text(0.5, 0.012,
             r"Both ladders start from $\beta = 1.3472$ at $L = 8$. Villain is invariant to "
             "five decimals; the Wilson ladder inherits it to 4%, the drift sitting entirely\n"
             "in the first, strongest-coupling step where tree-level matching is worst. "
             r"The coarse ensemble's $P(Q)$ is therefore the fine theory's $P(Q)$.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(FIG / "33_ladder_fixed_point.png", dpi=226)
    plt.close(fig)
    print("wrote 33_ladder_fixed_point.png")


def _freezing_rows():
    rows = json.loads((OUT / "charge_freezing_L64" / "charge_freezing.json").read_text())
    return sorted(rows, key=lambda r: r["fine_L"])


def fig_match_rate_volume() -> None:
    rows = _freezing_rows()
    Ls = [r["fine_L"] for r in rows]
    V = [2 * L * L for L in Ls]
    rate = [r["match_rate_without_projection"] for r in rows]

    fig, ax = plt.subplots(figsize=(6.9, 4.53))
    color = ARM["cold"][0]
    ax.plot(V, rate, color=color, marker="o", ms=8, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.7, zorder=4)
    for v, r, L in zip(V, rate, Ls):
        ax.annotate(f"{r:.3f}", (v, r), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=9, color=color, fontweight="bold")
        ax.annotate(rf"$L={L}$", (v, r), textcoords="offset points", xytext=(0, -18),
                    ha="center", fontsize=8, color=MUTED)

    ref = np.array(V, dtype=float)
    ax.plot(ref, rate[0] * (ref / ref[0]) ** -0.5, color=MUTED, lw=1.0,
            ls=(0, (4, 3)), zorder=2,
            label=r"halving per $4\times$ volume  ($\propto V^{-1/2}$)")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"volume  $V = 2L^2$", fontsize=10, color=INK)
    ax.set_ylabel("raw $Q$-match rate (no charge projection)", fontsize=10, color=INK)
    title(ax, "What the model supplies on its own: topology, and it degrades with volume")
    dress(ax)
    ax.set_ylim(0.05, 1.0)
    ax.legend(fontsize=8.5, frameon=False, labelcolor=INK, loc="lower left")
    fig.text(0.5, 0.012,
             "Fraction of generated configurations landing in the coarse partner's "
             "sector before charge projection, at matched couplings\n"
             r"$\beta_f = 14.15 / 55.02 / 218.58$. Reported because the protocol requires "
             "the pre-enforcement number; the deployed pipeline imposes the sector.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(FIG / "34_match_rate_volume.png", dpi=203)
    plt.close(fig)
    print("wrote 34_match_rate_volume.png  rates=" + ", ".join(f"{r:.3f}" for r in rate))


def fig_sector_freeze_sigma() -> None:
    rows = _freezing_rows()
    fig, ax = plt.subplots(figsize=(6.9, 4.29))
    styles = [(ARM["seed"][0], "o"), (ARM["cold"][0], "s"), (ARM["hmc+inst"][0], "D")]

    for r, (color, marker) in zip(rows, styles):
        tr = r["trace"]
        sig = np.array([t["sigma"] for t in tr])
        frac = np.array([t["frac_changed"] for t in tr])
        ax.plot(sig, frac, color=color, lw=1.8, zorder=4,
                label=rf"$L={r['fine_L']},\ \beta_f={r['fine_beta']:g}$")
        ax.axvline(r["sigma_freeze"], color=color, lw=0.9, ls=(0, (3, 3)), zorder=2)
        ax.plot([r["sigma_freeze"]], [0.5], color=color, marker=marker, ms=7,
                markeredgecolor="white", markeredgewidth=0.7, zorder=5, clip_on=False)

    sf = [r["sigma_freeze"] for r in rows]
    ax.annotate(r"$\sigma_{\mathrm{freeze}} \approx %.2f$" % float(np.mean(sf)),
                xy=(float(np.mean(sf)), 0.63), xytext=(0.9, 0.75), fontsize=9.5,
                color=INK,
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9,
                                connectionstyle="arc3,rad=-0.2"))

    ax.set_xscale("log")
    ax.set_xlabel(r"noise level  $\sigma$  (reverse process runs right to left)",
                  fontsize=10, color=INK)
    ax.set_ylabel("fraction of configurations changing sector", fontsize=10, color=INK)
    title(ax, r"The sector is decided at $\sigma \approx 0.31$, and that is flat in volume")
    dress(ax)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=8.5, frameon=False, labelcolor=INK, loc="upper left")
    fig.text(0.5, 0.012,
             r"$\sigma_{\mathrm{freeze}}$ = " + ", ".join(f"{s:.3f}" for s in sf) +
             " over a 16x range in volume. Below it the reverse process can no longer "
             "move Q,\nso the remaining sampling cannot repair a wrong sector.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.075, 1, 1))
    fig.savefig(FIG / "35_sector_freeze_sigma.png", dpi=214)
    plt.close(fig)
    print("wrote 35_sector_freeze_sigma.png")


def fig_sector_tail() -> None:
    rows = json.loads((OUT / "pq_hmc_tail" / "summary.json").read_text())
    rows = sorted(rows, key=lambda r: (r["L"], r["beta"]))
    labels = [rf"$L={r['L']}$" + "\n" + rf"$\beta={r['beta']:.4g}$" for r in rows]
    x = np.arange(len(rows))

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.06))

    ax = axes[0]
    for r, xi in zip(rows, x):
        ax.plot([xi - 0.16, xi + 0.16],
                [r["q2_before"] / r["exact_q2"], r["q2_after"] / r["exact_q2"]],
                color=MUTED, lw=0.9, zorder=2)
    ax.scatter(x - 0.16, [r["q2_before"] / r["exact_q2"] for r in rows],
               s=62, color=ARM["cold"][0], marker="s", edgecolor="white",
               linewidth=0.7, zorder=4, label="transported batch")
    ax.scatter(x + 0.16, [r["q2_after"] / r["exact_q2"] for r in rows],
               s=70, color=ARM["seed"][0], marker="o", edgecolor="white",
               linewidth=0.7, zorder=4, label="after the tail")
    ax.axhline(1.0, color=INK, lw=1.0, ls=(0, (4, 3)), zorder=3)
    ax.set_ylabel(r"$\langle Q^2\rangle$ / exact", fontsize=10, color=INK)
    ax.set_ylim(0, 2.05)
    panel_tag(ax, "(a)")
    title(ax, "Sector statistics")
    ax.legend(fontsize=8.5, frameon=False, labelcolor=INK, loc="upper left",
              ncol=2, handletextpad=0.4, columnspacing=1.2)
    for r, xi in zip(rows, x):
        ax.annotate(f"{r['tail_seconds']:.0f} s", (xi, 0.09), ha="center",
                    fontsize=7.5, color=MUTED)
    ax.annotate("tail wall-clock", (-0.42, 0.20), ha="left", fontsize=7.5,
                color=MUTED, style="italic")

    ax = axes[1]
    floor = 1e-5

    def clip(p):
        # beta_f = 218.58 populates a single bin, so chi^2 is not defined there.
        # An untestable case is drawn as absent, never as a pass.
        return None if p is None else max(p, floor)

    for r, xi in zip(rows, x):
        b, a = clip(r["chi2_p_before"]), clip(r["chi2_p_after"])
        if b is None or a is None:
            ax.text(xi, 0.25, "no\ntestable\nbins", fontsize=7.5, color=MUTED,
                    ha="center", va="center", style="italic")
            continue
        ax.plot([xi - 0.16, xi + 0.16], [b, a], color=MUTED, lw=0.9, zorder=2)
        ax.scatter([xi - 0.16], [b], s=62, color=ARM["cold"][0], marker="s",
                   edgecolor="white", linewidth=0.7, zorder=4)
        ax.scatter([xi + 0.16], [a], s=70, color=ARM["seed"][0], marker="o",
                   edgecolor="white", linewidth=0.7, zorder=4)
    ax.axhline(0.05, color=INK, lw=1.0, ls=(0, (4, 3)), zorder=3)
    ax.text(len(rows) - 0.5, 0.065, r"$p = 0.05$", fontsize=8, color=INK, ha="right")
    ax.set_yscale("log")
    ax.set_ylabel(r"$\chi^2$ $p$-value against exact $P(Q)$", fontsize=10, color=INK)
    panel_tag(ax, "(b)")
    title(ax, "Distributional test")

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, color=INK)
        ax.set_xlim(-0.55, len(rows) - 0.45)
        dress(ax)

    fig.suptitle("A 200-trajectory instanton-HMC tail repairs P(Q) without knowing P(Q)",
                 fontsize=12, color=INK, x=0.012, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             "The tail's Metropolis test uses only the computable action difference of the "
             "winding proposal, so this route transfers to theories with no analytic P(Q). "
             r"$\beta_f = 218.58$ has one populated" "\n"
             r"bin and no testable $\chi^2$; its $\langle Q^2\rangle$ is shown regardless. "
             "Wall-clock annotated in (a).",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.075, 1, 0.935))
    fig.savefig(FIG / "36_sector_tail.png", dpi=307)
    plt.close(fig)
    print("wrote 36_sector_tail.png")


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_ladder_fixed_point()
    fig_match_rate_volume()
    fig_sector_freeze_sigma()
    fig_sector_tail()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
