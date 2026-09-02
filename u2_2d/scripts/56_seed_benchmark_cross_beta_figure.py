"""Stage 56: fig31, the seed-vs-classical-start significance grid, at two couplings.

Reads `topology_stats.json` (Q^2, from `54_`) and `observable_stats.json`
(plaquette/loops, from `55_`) at both benchmarked rungs and draws |z| against
the exact closed form for the plain-HMC row (A/B/C: diffusion seed, cold, hot)
and the even-winding row (E/D/F), one column per coupling. This is the direct,
quantitative version of "does the diffusion seed outperform a cold/hot start
under wHMC" -- every bar is a calibrated significance, not a raw mean.

    python u2_2d/scripts/56_seed_benchmark_cross_beta_figure.py
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

RUNGS = [
    ("out/u2_2d/seed_benchmark_rung0", "L=32, beta=105.651"),
    ("out/u2_2d/seed_benchmark", "L=64, beta=416.524"),
]
ROWS = [
    ("plain HMC", [("A_diffusion_seed", "diffusion seed", "#1b6ca8"),
                   ("B_cold_start", "cold start", "#c2571a"),
                   ("C_hot_start", "hot start", "#7a1fa2")]),
    ("+ even winding", [("E_diffusion_plus_winding", "diffusion seed", "#1b6ca8"),
                        ("D_cold_plus_winding", "cold start", "#c2571a"),
                        ("F_hot_plus_winding", "hot start", "#7a1fa2")]),
]
OBS = ["plaquette", "wilson_2x2", "wilson_4x4", "wilson_8x8", "Q2"]
OBS_LABEL = {"plaquette": "P", "wilson_2x2": "W(2x2)", "wilson_4x4": "W(4x4)",
             "wilson_8x8": "W(8x8)", "Q2": "Q$^2$"}


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
    fig, axes = plt.subplots(len(ROWS), len(RUNGS), figsize=(11, 7))
    for col, (rung_dir, rung_label) in enumerate(RUNGS):
        z = load_z(rung_dir)
        for row, (row_label, arms) in enumerate(ROWS):
            ax = axes[row, col]
            x = np.arange(len(OBS))
            width = 0.25
            y_floor = 0.05
            for i, (arm, label, color) in enumerate(arms):
                vals = [min(z.get(arm, {}).get(o, np.nan), 1e4) for o in OBS]
                # `bottom=0` is -inf in log space; AGG occasionally rasterizes
                # that as a degenerate (invisible) rectangle for an arbitrary
                # bar in the set even though every other bar with a similar
                # bottom=0 baseline renders fine. An explicit, log-representable
                # bottom avoids the degenerate path entirely. Values already
                # below y_floor (e.g. z ~ 0.006) are clipped to the floor rather
                # than silently vanishing, so "too small to plot" stays visible
                # as a floor-height bar instead of no bar.
                vals = [max(v, y_floor) if np.isfinite(v) else y_floor for v in vals]
                ax.bar(x + (i - 1) * width, vals, width, bottom=y_floor,
                      label=label, color=color)
            ax.axhline(2.0, color="black", linewidth=0.8, linestyle=":", zorder=0)
            ax.set_yscale("log")
            ax.set_xticks(x)
            ax.set_xticklabels([OBS_LABEL[o] for o in OBS])
            ax.set_ylim(y_floor, 2e3)
            if col == 0:
                ax.set_ylabel(f"{row_label}\n|z| vs exact")
            if row == 0:
                ax.set_title(rung_label)
            if row == len(ROWS) - 1 and col == 0:
                ax.legend(fontsize=8, loc="upper left")
    fig.suptitle("Diffusion seed vs. cold/hot start under wHMC: |z| against the "
                 "exact closed form\n(dotted line = 2 sigma; capped at 1e4 for "
                 "display, frozen chains go far higher)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))

    out_dir = Path("out/u2_2d/figures")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fig31_seed_vs_classical_significance.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
