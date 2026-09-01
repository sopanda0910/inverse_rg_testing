"""Figures 13-14 -- what the U(2) ladder costs, and the dial that buys it back.

NARRATIVE.md section 23 lists "what does it cost?" as the question a referee asks
after the physics, and the answer is unflattering enough that it has to be drawn
rather than buried: for LOCAL observables the ladder is 3.68x slower than
HMC + winding. Two panels, and the second is the reason the first is not fatal:

  fig13_cost           seconds per independent configuration by arm, with each
                       bar labelled by the fraction of the exact P(Q) that arm
                       actually covers and how many ODD sectors it visited. The
                       classical arms are cheaper and cover half the
                       distribution with zero odd sectors; the hot arm "covers"
                       1.000 while carrying <Q^2> = 109 against an exact 1.001.
                       A seconds-ratio against an arm sampling the wrong
                       distribution is meaningless, so the two axes are shown
                       together and never collapsed into one number.

  fig14_sampler_steps  cost and accuracy against the number of reverse-diffusion
                       steps. The cost is dominated by the sampler, which is
                       tunable: at 25 steps the top rung is 1.4x FASTER than
                       HMC + winding at ~2.7x the extended-loop error, and below
                       18 steps the lift collapses. The pre-rethermalization
                       error is the honest y-axis -- the post column is repaired
                       by local sweeps and looks healthy past the point where
                       the model stopped working, and <Q^2> is imposed by
                       `apply_coarse_charge` and cannot degrade at all.

    python u2_2d/scripts/16_cost_figures.py
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
SEED_C, COLD_C, HOT_C, WIND_C = "#D55E00", "#0072B2", "#56B4E9", "#009E73"

ARM_STYLE = {
    "A_diffusion_seed": (SEED_C, "diffusion seed"),
    "B_cold_start": (COLD_C, "cold start"),
    "C_hot_start": (HOT_C, "hot start"),
    "D_cold_plus_winding": (WIND_C, "HMC + winding"),
    "E_diffusion_plus_winding": (SEED_C, "diffusion + winding"),
    "F_hot_plus_winding": (HOT_C, "hot + winding"),
    "G_cold_plus_odd_winding": (WIND_C, "HMC + odd winding"),
    "H_diffusion_plus_odd_winding": (SEED_C, "diffusion + odd winding"),
}
# Fallback rather than KeyError: stage 08 gained four arms on 2026-08-20 and this
# figure should degrade to a grey unnamed bar rather than take the queue down.
ARM_FALLBACK = ("#777777", None)


def dress(ax):
    ax.grid(True, which="major", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8.5)


def figure_cost(cost: dict, path: Path) -> None:
    arms = cost["arms"]
    ladder = cost["ladder"]

    labels, secs, cover, odd, colors = [], [], [], [], []
    for a in arms:
        color, name = ARM_STYLE.get(a["arm"], ARM_FALLBACK)
        name = name or a["arm"].replace("_", " ")
        labels.append(name)
        secs.append(a["seconds_per_independent_config_local"])
        cover.append(a["exact_probability_covered"])
        odd.append(a["odd_sectors_visited"])
        colors.append(color)
    labels.append("ladder\n(incl. base)")
    secs.append(ladder["seconds_per_config_including_base"])
    cover.append(arms[0]["exact_probability_covered"])
    odd.append(arms[0]["odd_sectors_visited"])
    colors.append(SEED_C)

    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.13))

    ax = axes[0]
    finite = [s if (s is not None and math.isfinite(s)) else 0.0 for s in secs]
    ax.bar(x, finite, width=0.6, color=colors, alpha=0.9, zorder=3)
    for xi, s in zip(x, secs):
        if s is None or not math.isfinite(s):
            ax.text(xi, 0.02, "never\nthermalizes", ha="center", va="bottom",
                    fontsize=8, color=MUTED, style="italic", rotation=0)
        else:
            ax.annotate(f"{s:.3f} s", (xi, s), textcoords="offset points",
                        xytext=(0, 5), ha="center", fontsize=8.5, color=INK,
                        fontweight="bold")
    ax.set_ylabel("seconds per independent configuration\n(local observables)",
                  fontsize=9.5, color=INK)
    ax.set_ylim(0, max(finite) * 1.28)
    ax.set_title("(a)  Cost — and the ladder loses",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    dress(ax)

    ax = axes[1]
    ax.bar(x, cover, width=0.6, color=colors, alpha=0.9, zorder=3)
    ax.axhline(1.0, color=INK, lw=1.1, ls=(0, (4, 3)), zorder=4)
    for xi, c, o in zip(x, cover, odd):
        ax.annotate(f"{c:.3f}", (xi, c), textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=8.5, color=INK, fontweight="bold")
        ax.annotate(f"{o} odd\nsectors", (xi, 0.03), ha="center", va="bottom",
                    fontsize=7.5, color="white" if c > 0.25 else MUTED)
    ax.set_ylabel(r"fraction of exact $P(Q)$ covered", fontsize=9.5, color=INK)
    ax.set_ylim(0, 1.22)
    ax.set_title("(b)  Reachability — and the classical arms cannot improve",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    dress(ax)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.5, color=INK)

    hot = next(a for a in arms if a["arm"] == "C_hot_start")
    fig.suptitle(rf"$L = {cost['lattice_size']}$, $\beta = {cost['beta']:g}$: "
                 "the ladder is slower, and it reaches sectors the fast arms cannot",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             "Odd charge has probability ZERO in the classical arms' stationary "
             "distribution, not merely a long autocorrelation, so no amount of "
             "additional time fixes column (b) for them.\n"
             "Read coverage together with "
             r"$\langle Q^2\rangle$: the hot arm covers "
             f"{hot['exact_probability_covered']:.3f} while carrying "
             r"$\langle Q^2\rangle = 109$ against an exact 1.001 — it visits many sectors, "
             "and the wrong ones.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.075, 1, 0.935))
    fig.savefig(path, dpi=235)
    plt.close(fig)
    print(f"wrote {path}")


def figure_sampler_steps(records: list, path: Path) -> None:
    records = sorted(records, key=lambda r: r["n_sampler_steps"])
    steps = np.array([r["n_sampler_steps"] for r in records], dtype=float)
    ratio = np.array([r["ratio_vs_hmc_winding_top_rung"] for r in records])
    pre = np.array([abs(r["rungs"][-1]["rel_err_pre_retherm"]) for r in records])
    post = np.array([abs(r["rungs"][-1]["rel_err"]) for r in records])
    w8 = np.array([abs(r["rungs"][-1]["wilson"]["wilson_8x8"]["rel_err"])
                   for r in records])

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.07))

    ax = axes[0]
    ax.plot(steps, ratio, color=SEED_C, marker="o", ms=7, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.7, zorder=4)
    ax.axhline(1.0, color=WIND_C, lw=1.4, ls=(0, (4, 3)), zorder=3)
    ax.text(steps[-1], 1.08, "HMC + winding", fontsize=8, color=WIND_C, ha="right")
    for s, r in zip(steps, ratio):
        if s in (25, 200):
            ax.annotate(f"{r:.2f}×", (s, r), textcoords="offset points",
                        xytext=(-4, 8), ha="right", fontsize=9, color=INK,
                        fontweight="bold")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("reverse-diffusion steps", fontsize=9.5, color=INK)
    ax.set_ylabel("top-rung cost / HMC + winding", fontsize=9.5, color=INK)
    ax.set_yticks([0.4, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
    ax.set_yticklabels(["0.4", "0.5", "0.75", "1", "1.5", "2", "3", "4"])
    ax.minorticks_off()
    ax.set_title("(a)  The cost is the sampler, and the sampler is a dial",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    dress(ax)

    ax = axes[1]
    ax.plot(steps, pre, color=COLD_C, marker="s", ms=6.5, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.7, zorder=4,
            label="plaquette, pre-rethermalization")
    ax.plot(steps, w8, color=SEED_C, marker="o", ms=6.5, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.7, zorder=4,
            label=r"$W(8\times 8)$, after rethermalization")
    ax.plot(steps, post, color=MUTED, marker="^", ms=5.5, lw=1.3, ls=(0, (3, 2)),
            zorder=3, label="plaquette, after rethermalization")
    ax.axvline(18, color=INK, lw=1.0, ls=(0, (1, 2)), zorder=3)
    ax.text(17, 3e-2, "below 18 steps\nthe lift collapses", fontsize=8, color=INK,
            ha="right", va="top")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("reverse-diffusion steps", fontsize=9.5, color=INK)
    ax.set_ylabel("relative error against the closed form", fontsize=9.5, color=INK)
    ax.set_title("(b)  What fewer steps costs in accuracy",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    ax.legend(fontsize=8, frameon=False, labelcolor=INK, loc="lower left")
    dress(ax)

    fig.suptitle(r"Tuning the lift: $L = 16$, $\beta = 28$ base, up the full schedule "
                 r"to $L = 64$, $\beta = 416.5$",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             "The pre-rethermalization plaquette is the measurement of what the MODEL "
             "did; the post-rethermalization curve is repaired by local sweeps and stays "
             "flat past the point where\nthe model stopped working, which is why it is "
             r"drawn dashed and demoted. $\langle Q^2\rangle$ is imposed by "
             "`apply_coarse_charge` at every setting and so cannot degrade — it is not an "
             "accuracy axis and is not plotted.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.075, 1, 0.935))
    fig.savefig(path, dpi=235)
    plt.close(fig)
    print(f"wrote {path}  ({len(records)} settings, {steps[0]:.0f}-{steps[-1]:.0f} steps)")


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="out/u2_2d/figures")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cost = _load(Path("out/u2_2d/seed_benchmark/cost.json"))
    if cost:
        figure_cost(cost, out_dir / "fig13_cost.png")

    records = []
    for name in ("sampler_steps_low", "sampler_steps"):
        rows = _load(Path("out/u2_2d") / name / "sampler_steps.json")
        if rows:
            records.extend(rows)
    # the two runs overlap at 25-400; keep one record per step count
    seen, unique = set(), []
    for r in records:
        if r["n_sampler_steps"] in seen:
            continue
        seen.add(r["n_sampler_steps"])
        unique.append(r)
    if unique:
        figure_sampler_steps(unique, out_dir / "fig14_sampler_steps.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
