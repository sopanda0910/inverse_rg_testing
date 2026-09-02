"""Cost accounting in INTERVAL TIME (trajectories), not wall-clock.

Every existing cost figure in this project (17_headtohead_cost.png,
18_entry_cost.png) reports seconds per independent configuration. This script
reads the same already-computed JSONs and re-expresses the three-way
comparison -- plain HMC, HMC + winding, diffusion seed -- on a trajectory
axis instead, at the three Table-S8 couplings (L=32, beta = 14.1464, 55.0237,
218.58). No new sampling is run.

Sources (all already on disk):
  out/u1_2d/diffusion_vs_instanton/summary.json
      instanton_hmc.interval_trajectories = 2 * tau_int(slowest Wilson loop),
      i.e. the HMC + winding marginal cost per independent configuration.
  out/u1_2d/thermalization/crossover_window.json
      diffusion-seed t_therm (script 05/35), plain HMC hot/cold burn-in
      (never within the 640-trajectory budget once beta >~ 8).

Plain HMC has NO finite entry here: Table S8 (docs/u1_2d/NARRATIVE.md S25.6a)
measured 0 sector changes in 3000 trajectories at all three couplings, so its
bar is drawn as "frozen" rather than a number.

    .venv/Scripts/python.exe u1_2d/scripts/68_cost_interval_time.py
"""

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
BLUE, ORANGE, GREEN = "#0072B2", "#D55E00", "#2e7d32"

OUT = Path("out/u1_2d")
FIG_PATH = OUT / "paper_appendix" / "figures" / "cost_interval_time.png"

# Table S8 couplings (docs/u1_2d/NARRATIVE.md S25.6a), matched to the nearest
# case actually present in each source JSON.
CASES = [
    {"label": r"$\beta=14.15$", "instanton_beta": 14.1464, "crossover_beta": 14.146446570889967},
    {"label": r"$\beta=55.02$", "instanton_beta": 55.0237, "crossover_beta": 55.023680066170776},
    {"label": r"$\beta=218.58$", "instanton_beta": 218.58, "crossover_beta": 218.5802136261687},
]


def main():
    plt.rcParams.update({
        "font.size": 10, "font.family": "sans-serif",
        "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK, "ytick.color": INK,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True, "figure.dpi": 300,
    })

    instanton = {r["beta"]: r["instanton_hmc"] for r in
                 json.loads((OUT / "diffusion_vs_instanton" / "summary.json").read_text())}
    crossover = {round(r["beta"], 4): r for r in
                 json.loads((OUT / "thermalization" / "crossover_window.json").read_text())["rows"]
                 if r["L"] == 32}

    winding_interval, seed_therm = [], []
    for case in CASES:
        winding_interval.append(instanton[case["instanton_beta"]]["interval_trajectories"])
        seed_therm.append(crossover[round(case["crossover_beta"], 4)]["seed"])

    labels = [c["label"] for c in CASES]
    x = np.arange(len(CASES))
    width = 0.26

    fig, ax = plt.subplots(figsize=(8.6, 4.6))

    # Plain HMC: frozen at all three (Table S8), drawn as a capped bar with an
    # explicit "frozen" annotation rather than an infinite bar.
    frozen_height = 400.0
    ax.bar(x - width, [frozen_height] * len(CASES), width, color="white",
           edgecolor=MUTED, hatch="////", linewidth=1.2, zorder=2,
           label="plain HMC: frozen (0 changes / 3000 traj, Table S8)")
    for xi in x:
        ax.annotate("frozen", xy=(xi - width, frozen_height), xytext=(0, 4),
                     textcoords="offset points", ha="center", fontsize=8, color=MUTED)

    bars_w = ax.bar(x, winding_interval, width, color=ORANGE, zorder=3,
                     label=r"HMC + winding: $2\,\tau_{int}(Q^2\ \mathrm{etc.})$ interval")
    bars_s = ax.bar(x + width, [max(v, 0.3) for v in seed_therm], width, color=BLUE, zorder=3,
                     label="diffusion seed: $t_{therm}$ (trajectories to converge)")

    for xi, v in zip(x, winding_interval):
        ax.annotate(f"{v:.1f}", xy=(xi, v), xytext=(0, 3), textcoords="offset points",
                     ha="center", fontsize=8.5, color=INK)
    for xi, v in zip(x, seed_therm):
        ax.annotate(f"{v:.0f}", xy=(xi + width, max(v, 0.3)), xytext=(0, 3),
                     textcoords="offset points", ha="center", fontsize=8.5, color=INK)

    ax.set_yscale("log")
    ax.set_ylim(0.2, 3000)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("trajectories per independent / thermalized configuration\n(interval time, not wall-clock)")
    ax.set_title("Cost in interval time: plain HMC vs. HMC+winding vs. diffusion seed\n(L = 32, matched Table S8 couplings)",
                  fontsize=10.5)
    ax.legend(frameon=False, fontsize=8.2, loc="center left", bbox_to_anchor=(1.02, 0.5))
    for spine in ax.spines.values():
        spine.set_color(GRID)
    fig.tight_layout()
    FIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=300)
    plt.close(fig)
    print(f"wrote {FIG_PATH}")


if __name__ == "__main__":
    main()
