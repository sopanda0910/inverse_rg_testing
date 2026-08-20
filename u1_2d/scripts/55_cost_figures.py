"""Figures 40-41 -- what the seed costs, honestly accounted.

The study's cost claim is *not* "cheaper per configuration". It is "flat in beta
against a baseline whose entry cost diverges and then stops converging". Two
panels, and the first one is the concession:

  40_cost_per_config   seconds per INDEPENDENT configuration vs beta, for the
                       four classical arms plus the prolongator. The classical
                       baseline of record is HMC + winding update, which is
                       exact and nearly free, so it is a hard baseline and the
                       figure must show that it wins on marginal cost.
  41_breakeven         cumulative seconds vs number of configurations, with the
                       generative arm charged its full one-time entry cost. The
                       crossing points are annotated, and where a classical arm
                       does not converge at all there is no crossing to find --
                       which is the actual claim.

Cost of an independent configuration is 2 * tau_int(Q^2) * (s/traj), the same
definition script 43 uses, so the arms are comparable. A frozen chain has no
finite cost: a constant series reports a SMALL tau_int, so quoting one would
credit a chain that never moved.

    python u1_2d/scripts/55_cost_figures.py
"""

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _figstyle import ARM, INK, MUTED, dress, panel_tag, title  # noqa: E402

OUT = REPO / "out" / "u1_2d"
FIG = OUT / "paper_appendix" / "figures"

# Script 17's accounting, unchanged: the head-to-head charges the classical arm
# its burn-in, so the generative arm must be charged its own entry cost.
CAMPAIGN_DATA_SECONDS = 3.2 * 60.0
CAMPAIGN_TRAIN_SECONDS = 100 * 45.0
CAMPAIGN_ONE_TIME_SECONDS = CAMPAIGN_DATA_SECONDS + CAMPAIGN_TRAIN_SECONDS

ARM_ORDER = ["hmc", "hmc+inst", "ptbc", "open"]


def load_arms():
    rows = json.loads((OUT / "classical_arms" / "ptbc_benchmark.json").read_text())
    rows += json.loads((OUT / "ptbc_benchmark_tuned" / "ptbc_benchmark.json").read_text())
    by_arm: dict[str, list[tuple[float, float, bool]]] = {}
    for r in rows:
        cost = r["sec_per_independent_config"]
        by_arm.setdefault(r["arm"], []).append(
            (r["beta"], cost, bool(r["frozen"]) or not math.isfinite(cost)))
    for v in by_arm.values():
        v.sort()
    return by_arm


def diffusion_cost():
    base = json.loads((OUT / "diffusion_vs_instanton" / "summary.json").read_text())
    return sorted((r["beta"], r["diffusion"]["seconds_per_independent_config"])
                  for r in base)


def fig_cost_per_config() -> None:
    by_arm = load_arms()
    diff = diffusion_cost()

    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    ax.set_xscale("log")
    ax.set_yscale("log")

    for arm in ARM_ORDER:
        pts = by_arm.get(arm, [])
        if not pts:
            continue
        color, marker, label = ARM[arm]
        good = [(b, c) for b, c, frozen in pts if not frozen]
        bad = [b for b, _, frozen in pts if frozen]
        if good:
            xs, ys = zip(*good)
            ax.plot(xs, ys, color=color, marker=marker, ms=7, lw=1.8,
                    markeredgecolor="white", markeredgewidth=0.6, zorder=4)
        for b in bad:
            ax.plot([b], [40.0], color=color, marker=marker, ms=8,
                    markerfacecolor="none", markeredgecolor=color,
                    markeredgewidth=1.4, zorder=5, clip_on=False)
            ax.annotate("", xy=(b, 95.0), xytext=(b, 52.0),
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.1,
                                        shrinkA=0, shrinkB=0), zorder=5)

    xs, ys = zip(*diff)
    ax.plot(xs, ys, color=ARM["seed"][0], marker="o", ms=7.5, lw=2.2,
            markeredgecolor="white", markeredgewidth=0.6, zorder=6)

    ax.text(4.6, 60, "frozen: no finite cost\n(0 sector changes in 3000 traj)",
            fontsize=8, color=MUTED, ha="left", style="italic")

    ax.set_xlabel(r"fine coupling  $\beta_f$", fontsize=10, color=INK)
    ax.set_ylabel("seconds per independent configuration", fontsize=10, color=INK)
    title(ax, "The marginal cost claim, conceded: the winding update is the arm to beat")
    dress(ax)
    ax.set_ylim(1e-2, 2e2)

    handles = [Line2D([], [], color=ARM[a][0], marker=ARM[a][1], ms=6.5, lw=1.8,
                      markeredgecolor="white", markeredgewidth=0.6, label=ARM[a][2])
               for a in ARM_ORDER]
    handles.append(Line2D([], [], color=ARM["seed"][0], marker="o", ms=7, lw=2.2,
                          markeredgecolor="white", markeredgewidth=0.6,
                          label="diffusion prolongator (marginal)"))
    ax.legend(handles=handles, fontsize=8.5, frameon=False, labelcolor=INK,
              loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3,
              handletextpad=0.5, columnspacing=1.6)

    fig.text(0.5, 0.008,
             r"$L = 32$, 3000 trajectories, cost $= 2\,\tau_{\mathrm{int}}(Q^2) \times$ "
             "s/traj, PTBC charged for every replica it must evolve. Open boundaries "
             "measure a different observable\n"
             r"($Q$ is not an integer, $\langle Q^2\rangle = 2.8$-$4.4$ against a periodic "
             "exact 0.03-1.90) and are drawn for reference only. Marginal cost excludes "
             "entry cost; figure 41 charges it.",
             fontsize=6.8, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.115, 1, 1))
    fig.savefig(FIG / "40_cost_per_config.png", dpi=200)
    plt.close(fig)
    print("wrote 40_cost_per_config.png")
    for arm in ARM_ORDER:
        print(f"  {arm:9s} " + "  ".join(
            ("frozen" if f else f"{c:.3f}") for _, c, f in by_arm.get(arm, [])))


def fig_breakeven() -> None:
    by_arm = load_arms()
    diff = dict(diffusion_cost())

    # beta = 218.58 is the headline coupling: the deepest one both a classical
    # arm and the pipeline were run at.
    beta = 218.58
    inst = next(c for b, c, f in by_arm["hmc+inst"] if abs(b - beta) < 1e-6 and not f)
    ptbc = next(c for b, c, f in by_arm["ptbc"] if abs(b - beta) < 1e-6 and not f)
    gen_marginal = diff[min(diff, key=lambda b: abs(b - beta))]

    n = np.logspace(0, 5, 400)
    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    lines = [
        ("diffusion prolongator", ARM["seed"][0], "-",
         CAMPAIGN_ONE_TIME_SECONDS + gen_marginal * n),
        ("HMC + winding update", ARM["hmc+inst"][0], "-", inst * n),
        ("PTBC (tuned)", ARM["ptbc"][0], "-", ptbc * n),
    ]
    for label, color, ls, y in lines:
        ax.plot(n, y, color=color, ls=ls, lw=2.2, zorder=4, label=label)

    for label, color, other in (("HMC + winding update", ARM["hmc+inst"][0], inst),
                                ("PTBC (tuned)", ARM["ptbc"][0], ptbc)):
        if other <= gen_marginal:
            ax.annotate(f"never breaks even against\n{label}\n"
                        f"({other:.2f} s vs {gen_marginal:.2f} s marginal)",
                        xy=(3.0e4, other * 3.0e4), xytext=(9.0e2, other * 3.0e4 * 2.4),
                        fontsize=8, color=color, ha="left",
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=0.9,
                                        connectionstyle="arc3,rad=-0.15"))
            continue
        n_star = CAMPAIGN_ONE_TIME_SECONDS / (other - gen_marginal)
        ax.plot([n_star], [other * n_star], marker="o", ms=9, color=color,
                markerfacecolor="white", markeredgewidth=2.0, zorder=6)
        ax.annotate(f"break-even vs {label}\n{n_star:,.0f} configurations",
                    xy=(n_star, other * n_star), xytext=(n_star * 0.09, other * n_star * 4.5),
                    fontsize=8.5, color=color,
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0))
        print(f"  break-even vs {label}: {n_star:,.0f} configurations")

    ax.axhline(CAMPAIGN_ONE_TIME_SECONDS, color=ARM["seed"][0], lw=1.1,
               ls=(0, (4, 3)), zorder=3)
    ax.text(1.15, CAMPAIGN_ONE_TIME_SECONDS * 0.30,
            f"one-time entry cost {CAMPAIGN_ONE_TIME_SECONDS / 60:.0f} min\n"
            "(data generation + training)",
            fontsize=8, color=ARM["seed"][0], va="top")
    ax.axvline(38 * 128, color=MUTED, lw=1.0, ls=(0, (1, 2)), zorder=3)
    ax.text(38 * 128 * 0.88, 7.0e5, "configurations this\ncheckpoint actually served",
            fontsize=7.5, color=MUTED, ha="right", va="top")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("configurations produced", fontsize=10, color=INK)
    ax.set_ylabel("cumulative seconds", fontsize=10, color=INK)
    title(ax, rf"Total cost with the entry charge included   ($L = 32$, $\beta_f = {beta:g}$)")
    dress(ax)
    ax.set_ylim(1, 1e6)
    ax.legend(fontsize=9, frameon=False, labelcolor=INK, loc="lower left")
    fig.text(0.5, 0.012,
             "The generative arm is charged its full one-time cost, which is the accounting "
             "a referee is entitled to. At this coupling the winding update is cheaper per\n"
             "configuration and stays cheaper, so the defensible claim is about reachability "
             "and about scaling in beta -- not about being cheaper outright.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 1))
    fig.savefig(FIG / "41_breakeven.png", dpi=200)
    plt.close(fig)
    print(f"wrote 41_breakeven.png  (hmc+inst {inst:.3f} s, ptbc {ptbc:.3f} s, "
          f"diffusion {gen_marginal:.3f} s marginal)")


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_cost_per_config()
    fig_breakeven()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
