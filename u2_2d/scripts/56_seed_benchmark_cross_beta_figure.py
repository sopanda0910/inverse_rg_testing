"""Stage 56: fig31, the seed-vs-classical-start significance grid, at two couplings.

Reads `topology_stats.json` (Q^2, from `54_`) and `observable_stats.json`
(plaquette/loops, from `55_`) at both benchmarked rungs and draws |z| against
the exact closed form, one row per sampler and one column per coupling. This
is the direct, quantitative version of "does the diffusion seed outperform a
cold/hot start" -- every bar is a calibrated significance, not a raw mean.

Three things changed when this figure was promoted from the appendix to the
body as the single U(2) benchmark figure (it replaced fig07's topological-reach
grid and fig20's Wilson-loop histogram overlays, neither of which could show a
sigma):

  * All EIGHT arms are drawn, not six. The marginal (odd-capable) winding move
    is the only classical move that can reach an odd sector at all, so a
    benchmark that omits it compares the seed against a baseline nobody would
    deploy. It gets its own row; there is no hot+odd arm, so that row has two
    bars rather than three.
  * The frozen cold-start arm is LABELLED rather than silently clipped. Its
    Q^2 z-score is genuinely infinite -- every chain sits at Q=0 forever, so
    the across-chain SEM is exactly zero -- and a bar capped at 1e4 reads as
    "large" when the honest statement is "this arm has sampled nothing".
  * One shared legend outside the axes, so no bar is occluded.

    python u2_2d/scripts/56_seed_benchmark_cross_beta_figure.py
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
SEED_C, COLD_C, HOT_C = "#0072B2", "#D55E00", "#7a1fa2"

RUNGS = [
    ("out/u2_2d/seed_benchmark_rung0", r"$L=32$,  $\beta=105.651$"),
    ("out/u2_2d/seed_benchmark", r"$L=64$,  $\beta=416.524$"),
]
# (row label, [(arm key, series label, colour)])
ROWS = [
    ("plain HMC",
     [("A_diffusion_seed", "diffusion seed", SEED_C),
      ("B_cold_start", "cold start", COLD_C),
      ("C_hot_start", "hot start", HOT_C)]),
    (r"+ even winding ($\Delta Q=2$)",
     [("E_diffusion_plus_winding", "diffusion seed", SEED_C),
      ("D_cold_plus_winding", "cold start", COLD_C),
      ("F_hot_plus_winding", "hot start", HOT_C)]),
    (r"+ marginal winding ($\Delta Q=1$)",
     [("H_diffusion_plus_odd_winding", "diffusion seed", SEED_C),
      ("G_cold_plus_odd_winding", "cold start", COLD_C)]),
]
OBS = ["plaquette", "wilson_2x2", "wilson_4x4", "wilson_8x8", "Q2"]
OBS_LABEL = {"plaquette": r"$W(1{\times}1)$", "wilson_2x2": r"$W(2{\times}2)$",
             "wilson_4x4": r"$W(4{\times}4)$", "wilson_8x8": r"$W(8{\times}8)$",
             "Q2": r"$\langle Q^2\rangle$"}

Y_FLOOR, Y_CEIL = 0.05, 1.2e3


def load_z(rung_dir: str) -> dict:
    """{arm: {obs: |z|}} from the two stats files this rung wrote."""
    topo = json.loads((Path(rung_dir) / "topology_stats.json").read_text(encoding="utf-8"))
    obs = json.loads((Path(rung_dir) / "observable_stats.json").read_text(encoding="utf-8"))
    z = {}
    for a in topo["arms"]:
        z.setdefault(a["arm"], {})["Q2"] = abs(a["q_squared_z"])
    for a in obs["arms"]:
        for name, v in a.items():
            if name == "arm" or "error" in v:
                continue
            z.setdefault(a["arm"], {})[name] = abs(v["z"])
    return z


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="out/u2_2d/figures/fig31_seed_vs_classical_significance.png")
    args = ap.parse_args()

    fig, axes = plt.subplots(len(ROWS), len(RUNGS), figsize=(10.5, 8.2),
                             sharey=True)
    for col, (rung_dir, rung_label) in enumerate(RUNGS):
        z = load_z(rung_dir)
        for row, (row_label, arms) in enumerate(ROWS):
            ax = axes[row, col]
            x = np.arange(len(OBS))
            n = len(arms)
            width = 0.8 / n
            for i, (arm, _label, color) in enumerate(arms):
                offset = (i - (n - 1) / 2.0) * width
                raw = [z.get(arm, {}).get(o, np.nan) for o in OBS]
                # bottom=0 is -inf in log space and AGG rasterizes that as a
                # degenerate (invisible) rectangle for an arbitrary bar in the
                # set. An explicit, log-representable bottom avoids it; a value
                # already under the floor is clipped up so "too small to plot"
                # shows as a floor-height bar rather than as no bar.
                vals = [Y_FLOOR if not np.isfinite(v) else max(min(v, Y_CEIL), Y_FLOOR)
                        for v in raw]
                ax.bar(x + offset, vals, width * 0.92, bottom=Y_FLOOR,
                       color=color, zorder=3)
                for xi, (v, r) in enumerate(zip(vals, raw)):
                    if not np.isfinite(r):
                        # Frozen: SEM is exactly zero because every chain sat
                        # in one sector for the whole run. Say so.
                        # Anchored just above the floor-height bar and grown
                        # upward: `rotation_mode="anchor"` is what keeps the
                        # rotated string inside the axes instead of running
                        # off the bottom spine.
                        ax.annotate("frozen", (xi + offset, Y_FLOOR * 2.6),
                                    ha="left", va="center", fontsize=7,
                                    color=COLD_C, zorder=5, rotation=90,
                                    rotation_mode="anchor")
                    elif r > Y_CEIL:
                        ax.annotate(f"{r:.0f}", (xi + offset, Y_CEIL),
                                    ha="center", va="bottom", fontsize=6.5,
                                    color=color, zorder=5)
            ax.axhline(2.5, color="#2ca02c", lw=1.1, ls="--", zorder=2)
            ax.axhspan(Y_FLOOR, 2.5, color="#2ca02c", alpha=0.07, zorder=0)
            ax.set_yscale("log")
            ax.set_ylim(Y_FLOOR, Y_CEIL * 3)
            ax.set_xticks(x)
            ax.set_xticklabels([OBS_LABEL[o] for o in OBS], fontsize=8.5)
            ax.grid(True, axis="y", which="major", color=GRID, lw=0.5, zorder=0)
            ax.set_axisbelow(True)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            ax.tick_params(colors=MUTED, labelsize=8.5)
            if col == 0:
                ax.set_ylabel(row_label + "\n" + r"$|z|$ vs exact", fontsize=9,
                              color=INK)
            if row == 0:
                ax.set_title(rung_label, fontsize=11, color=INK)
            # Placed on the sparsest panel: the marginal-winding row has no
            # hot arm, so its right-hand half is empty at every coupling.
            if col == 0 and row == len(ROWS) - 1:
                ax.annotate(r"  agreement band, $|z|\leq2.5$", (0.995, 2.5),
                            xycoords=ax.get_yaxis_transform(), ha="right",
                            va="bottom", fontsize=8.5, color="#2ca02c")

    handles = [Patch(color=SEED_C, label="diffusion seed"),
               Patch(color=COLD_C, label="cold start"),
               Patch(color=HOT_C, label="hot start")]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
               fontsize=10, bbox_to_anchor=(0.5, -0.005))
    fig.suptitle(
        "The diffusion seed is the only start that agrees with the exact closed "
        "form on local observables and topology at once\n"
        r"(400 trajectories, 64 chains, identical for every arm; bars are clipped "
        r"below $|z|=0.05$ and annotated above $|z|=10^{3}$)",
        fontsize=10.5, color=INK, y=0.995)
    fig.tight_layout(rect=(0, 0.035, 1, 0.955))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
