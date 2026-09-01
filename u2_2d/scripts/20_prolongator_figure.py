"""Figure 15 -- the diffusion seed against the non-learned prolongators.

Two panels because the two columns say opposite things and the paper has to
show both.

  (a) t_therm by arm. This is the referee's question -- how much of the seed's
      advantage is buyable by any coarse-to-fine map -- and at the couplings
      this study runs at the answer is "most of it, for LOCAL observables". Every
      arm gets the ladder's own post-processing, and the exact conditional SU(2)
      sampler is strong enough that a naive 2x2 tile lands within a trajectory or
      two of the learned lift. Drawing that is not a concession; it is the
      measurement, and hiding it would be the concession.

  (b) the PRE-rethermalization relative error. Same configurations, before the
      local sweeps run. This is the column that separates a good model from a
      good repair, and it is where the arms actually differ -- by orders of
      magnitude, on the same data that panel (a) shows as a tie.

Read together they say something sharper than either alone: at these couplings
the local-update repair is doing most of the work on local observables, and what
the learned lift buys has to be argued somewhere other than t_therm.

    python u2_2d/scripts/20_prolongator_figure.py
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
SEED_C, COLD_C, HOT_C, GEO_C, SMEAR_C = ("#D55E00", "#0072B2", "#56B4E9",
                                         "#CC79A7", "#009E73")
STYLE = {
    "diffusion": (SEED_C, "diffusion seed"),
    "smear": (SMEAR_C, "flux + tuned sweeps"),
    "flux": (GEO_C, "flux"),
    "halve": (GEO_C, "halve"),
    "tile": (GEO_C, "tile"),
    "cold": (COLD_C, "cold start"),
    "hot": (HOT_C, "hot start"),
}
ORDER = ["diffusion", "smear", "flux", "halve", "tile", "cold", "hot"]


def dress(ax):
    ax.grid(True, which="major", axis="y", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8.5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="out/u2_2d/prolongator_L64")
    parser.add_argument("--out", default="out/u2_2d/figures/fig15_prolongator.png")
    args = parser.parse_args()

    src = Path(args.source) / "prolongator.json"
    if not src.exists():
        print(f"missing {src} -- run stage 17 first")
        return 1
    rows = json.loads(src.read_text(encoding="utf-8"))
    rows = sorted(rows, key=lambda r: ORDER.index(r["arm"]) if r["arm"] in ORDER else 99)
    budget = rows[0]["n_traj"]
    beta, size = rows[0]["beta"], rows[0]["lattice_size"]

    obs = [k for k in ("plaquette", "wilson_2x2", "wilson_4x4", "wilson_8x8")
           if k in rows[0]["t_therm"]]
    labels = [STYLE.get(r["arm"], (MUTED, r["arm"]))[1] for r in rows]
    x = np.arange(len(rows))

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.03))

    ax = axes[0]
    width = 0.8 / len(obs)
    shades = np.linspace(0.45, 1.0, len(obs))
    for j, o in enumerate(obs):
        vals, hatched = [], []
        for r in rows:
            v = r["t_therm"].get(o)
            hatched.append(v is None)
            vals.append(budget * 1.35 if v is None else max(v, 0.0))
        colors = [STYLE.get(r["arm"], (MUTED, ""))[0] for r in rows]
        ax.bar(x + (j - (len(obs) - 1) / 2) * width, vals, width=width * 0.92,
               color=colors, alpha=float(shades[j]), zorder=3,
               edgecolor=["none" if not h else INK for h in hatched],
               hatch=["" if not h else "///" for h in hatched],
               label=o.replace("wilson_", "W "))
    ax.axhline(budget, color=INK, lw=1.1, ls=(0, (4, 3)), zorder=4)
    ax.text(len(rows) - 0.5, budget * 1.05, f"{budget}-trajectory budget",
            fontsize=7.5, color=INK, ha="right")
    ax.set_yscale("symlog", linthresh=1.0, linscale=0.4)
    ax.set_yticks([0, 1, 10, 100, budget])
    ax.set_yticklabels(["0", "1", "10", "100", str(budget)])
    ax.set_ylim(-0.3, budget * 3)
    ax.set_ylabel("trajectories to thermalization", fontsize=10, color=INK)
    ax.set_title("(a)  $t_{\\mathrm{therm}}$ — and the arms tie",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    ax.legend(fontsize=8, frameon=False, labelcolor=INK, ncol=len(obs),
              loc="upper left", handletextpad=0.4, columnspacing=1.0)
    dress(ax)

    ax = axes[1]
    pre = [r.get("rel_err_pre_retherm") for r in rows]
    have = [i for i, v in enumerate(pre) if v is not None]
    ax.bar([x[i] for i in have], [abs(pre[i]) for i in have], width=0.6,
           color=[STYLE.get(rows[i]["arm"], (MUTED, ""))[0] for i in have],
           alpha=0.9, zorder=3)
    for i in have:
        ax.annotate(f"{abs(pre[i]):.1e}", (x[i], abs(pre[i])),
                    textcoords="offset points", xytext=(0, 5), ha="center",
                    fontsize=7.5, color=INK, rotation=90, va="bottom")
    for i in range(len(rows)):
        if i not in have:
            ax.text(x[i], 1e-6, "n/a", ha="center", va="bottom", fontsize=8,
                    color=MUTED, style="italic")
    ax.set_yscale("log")
    ax.set_ylabel("$|$rel. err$|$ on the plaquette,\nbefore rethermalization",
                  fontsize=10, color=INK)
    ax.set_title("(b)  Before the local sweeps — and they do not",
                 fontsize=10.5, color=INK, loc="left", pad=10)
    dress(ax)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8.5, color=INK, rotation=20,
                           ha="right")

    fig.suptitle(f"Is the seed's advantage buyable without a model?   "
                 f"($L = {size}$, $\\beta = {beta:g}$)",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.995)
    fig.text(0.5, 0.012,
             "Every arm gets the ladder's own post-processing -- coarse-charge "
             "enforcement, 30 exact conditional SU(2) sweeps, 10 rethermalization "
             "sweeps -- so what differs is the lift and only the lift.\n"
             "Hatched bars did not converge inside the budget and are drawn above "
             "it, never dropped. Panel (b) is the honest column: the sweeps repair "
             "the local observables of a bad lift, and a post-retherm table alone "
             "cannot tell the two apart.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0.085, 1, 0.935))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=248)
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
