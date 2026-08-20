"""Figures 42-43 -- the two claims the seed framing has to answer.

  42_mala_locality  "wrap the proposal in MALA and it becomes exact." Measured
                    on its own terms: the acceptance ratio against an
                    equilibrium start is ~1 at every step size, and <Q^2> is
                    BIT-IDENTICAL before and after in all eight settings -- zero
                    sector changes across 50 steps x 64 configurations. A high
                    acceptance rate is a local statement and does not bound
                    mixing on the modes the proposal cannot move.

  43_zhu_pq         "a wider Q distribution than a frozen chain is evidence of
                    correctness." It is not, when the correct answer is
                    computable and sits between the two. Four histograms with
                    exact P(Q) overlaid: their HMC arm at 0.06x exact <Q^2>,
                    their diffusion arm at 2.36x, ours at 1.08x with chi^2
                    p = 0.41. Both of their arms reject exact overwhelmingly,
                    in opposite directions.

The Zhu et al. bars are DIGITIZED from the published figure (arXiv:2410.19602,
vector paths calibrated against the axis ticks, recovering integer multiples of
1/1024 to within 0.001 of a configuration). That is a digitization of a figure,
not their data, and is labelled as such in the panel. Our own row is an
out-of-training-range checkpoint use and is labelled too.

    python u1_2d/scripts/56_positioning_figures.py
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

from _figstyle import ARM, INK, MUTED, dress, panel_tag, title  # noqa: E402

OUT = REPO / "out" / "u1_2d"
FIG = OUT / "paper_appendix" / "figures"


def fig_mala_locality() -> None:
    rows = json.loads((OUT / "mala_exactness" / "mala_exactness.json").read_text())
    cases = sorted({r["case"] for r in rows})
    palette = [ARM["seed"][0], ARM["cold"][0]]
    markers = ["o", "s"]

    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.6))

    ax = axes[0]
    for case, color, marker in zip(cases, palette, markers):
        sub = sorted((r for r in rows if r["case"] == case), key=lambda r: r["eps"])
        eps = [r["eps"] for r in sub]
        ax.plot(eps, [r["acceptance_model"] for r in sub], color=color, marker=marker,
                ms=7, lw=2.0, markeredgecolor="white", markeredgewidth=0.7, zorder=4,
                label=rf"{case}  model start")
        ax.plot(eps, [r["acceptance_equilibrium"] for r in sub], color=color,
                marker=marker, ms=6, lw=1.4, ls=(0, (3, 2)), markerfacecolor="none",
                markeredgewidth=1.3, zorder=4,
                label=rf"{case}  equilibrium start")
    ax.set_xscale("log")
    ax.set_xlabel(r"MALA step size  $\epsilon$", fontsize=10, color=INK)
    ax.set_ylabel("acceptance rate", fontsize=10, color=INK)
    ax.set_ylim(-0.03, 1.06)
    panel_tag(ax, "(a)")
    title(ax, "Acceptance says the proposal is fine")
    ax.legend(fontsize=7.8, frameon=False, labelcolor=INK, loc="lower left")
    dress(ax)

    ax = axes[1]
    labels, before, after, exacts = [], [], [], []
    for r in rows:
        labels.append(rf"{r['case'].split(':')[1][:6]}" + "\n" + rf"$\epsilon={r['eps']:g}$")
        before.append(r["obs_before"]["Q^2"])
        after.append(r["obs_after"]["Q^2"])
    x = np.arange(len(rows))
    ax.bar(x - 0.19, before, width=0.36, color=ARM["cold"][0], zorder=3,
           label=r"$\langle Q^2\rangle$ before")
    ax.bar(x + 0.19, after, width=0.36, color=ARM["seed"][0], zorder=3,
           label=r"$\langle Q^2\rangle$ after 50 MALA steps")
    for xi, b, a in zip(x, before, after):
        if b == a:
            ax.annotate("identical", (xi, max(b, a)), textcoords="offset points",
                        xytext=(0, 6), ha="center", fontsize=7, color=MUTED,
                        rotation=90, va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7.5, color=INK)
    ax.set_ylabel(r"$\langle Q^2\rangle$", fontsize=10, color=INK)
    ax.set_ylim(0, max(before) * 1.55)
    panel_tag(ax, "(b)")
    title(ax, "Topology says it is not")
    ax.legend(fontsize=8.5, frameon=False, labelcolor=INK, loc="upper right")
    dress(ax)

    n_moved = sum(1 for r in rows if r["obs_before"]["Q^2"] != r["obs_after"]["Q^2"])
    fig.suptitle("A local corrector is not a substitute for a real tail",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             f"{len(rows)} settings, 50 steps x 64 configurations each. "
             f"{len(rows) - n_moved} of {len(rows)} settings changed sector in NO "
             "configuration; the ratio of model-start to equilibrium-start acceptance "
             "is 1.00 to within 1%.\nThe acceptance rate is a statement about local moves "
             "and does not bound mixing on the modes the proposal cannot move.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 0.935))
    fig.savefig(FIG / "42_mala_locality.png", dpi=200)
    plt.close(fig)
    print(f"wrote 42_mala_locality.png  ({len(rows) - n_moved}/{len(rows)} settings "
          "left Q^2 bit-identical)")


def fig_zhu_pq() -> None:
    ours = json.loads((OUT / "zhu_comparison" / "zhu_comparison.json").read_text())[0]
    theirs = json.loads((OUT / "zhu_comparison" / "zhu_figure_counts.json").read_text())

    exact_hist = {int(k): v for k, v in ours["exact_hist"].items()}
    qs = sorted(exact_hist)
    exact_p = np.array([exact_hist[q] for q in qs])

    panels = []
    for a in theirs["arms"]:
        total = a["total"]
        p = np.array([a["counts"].get(str(q), 0) / total for q in qs])
        panels.append((a["arm"] + "\n(digitized from their figure)", p,
                       a["q2_over_exact"], a["chi2_p"]))
    for a in ours["arms"]:
        h = {int(k): v for k, v in a["hist"].items()}
        p = np.array([h.get(q, 0.0) for q in qs])
        name = ("this work: HMC, no topological moves" if a["arm"].startswith("hmc")
                else "this work: inverse-RG seed\n(out-of-training-range checkpoint)")
        panels.append((name, p, a["q2_over_exact"], a["chi2_p"]))

    order = [1, 3, 0, 2]
    fig, axes = plt.subplots(2, 2, figsize=(10.4, 7.0), sharex=True, sharey=True)
    for ax, idx in zip(axes.ravel(), order):
        name, p, ratio, chi2 = panels[idx]
        good = chi2 > 0.05
        color = ARM["seed"][0] if good else ARM["cold"][0]
        ax.bar(qs, p, width=0.72, color=color, alpha=0.88, zorder=3)
        ax.step(np.array(qs) - 0.5, exact_p, where="post", color=INK, lw=1.8,
                zorder=5, label="exact finite-volume $P(Q)$")
        ax.plot(qs[-1] + 0.5, exact_p[-1], alpha=0)
        ax.set_title(name, fontsize=9.5, color=INK, pad=8, loc="left")
        verdict = (rf"$\langle Q^2\rangle$ / exact = {ratio:.2f}" "\n"
                   rf"$\chi^2$ $p$ = " +
                   (f"{chi2:.2f}" if chi2 > 1e-3 else f"$10^{{{np.log10(chi2):.0f}}}$"))
        ax.text(0.985, 0.95, verdict, transform=ax.transAxes, fontsize=9,
                color=color, ha="right", va="top", fontweight="bold")
        dress(ax)

    for ax in axes[-1]:
        ax.set_xlabel("topological charge $Q$", fontsize=10, color=INK)
    for ax in axes[:, 0]:
        ax.set_ylabel("probability", fontsize=10, color=INK)
    axes[0, 0].legend(fontsize=8.5, frameon=False, labelcolor=INK, loc="upper left")
    axes[0, 0].set_xlim(qs[0] - 0.8, qs[-1] + 0.8)

    fig.suptitle(rf"Width is not correctness   ($L = {ours['L']}$, $\beta = {ours['beta']:g}$, "
                 rf"exact $\langle Q^2\rangle = {ours['exact_q2']:.4f}$)",
                 fontsize=12.5, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             "A wider Q distribution than a frozen chain is not evidence of correctness when "
             "the correct answer is computable and sits between them. The over-production is "
             "a failure\nour own RAW model shows too (2.5-5.4x above exact at strong "
             "coupling), so it looks like a property of score-based samplers on this theory "
             "rather than a defect of one implementation.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.055, 1, 0.955))
    fig.savefig(FIG / "43_zhu_pq.png", dpi=200)
    plt.close(fig)
    print("wrote 43_zhu_pq.png  " +
          ", ".join(f"{n.splitlines()[0]}: {r:.2f}x" for n, _, r, _ in panels))


def main() -> int:
    FIG.mkdir(parents=True, exist_ok=True)
    fig_mala_locality()
    fig_zhu_pq()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
