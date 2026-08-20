"""Figure 29 — trajectories to thermalization vs beta, by starting configuration.

The headline figure for the prolongator framing: what a diffusion-generated
starting configuration costs an exact HMC chain, against every non-learned
alternative, over a 586x range in coupling.

Two sources, two budgets, and the difference matters enough to draw:

  * `thermalization/crossover_window.json` -- 35 couplings, arms `seed` / `hot` /
    `cold`, scanned to **640** trajectories. This is Fig. 12's own scan.
  * `tiling_baseline_2000/tiling_baseline.json` -- 5 couplings, the four
    non-learned prolongators (`tile`, `halve`, `flux`, `ape`), scanned to
    **2000** trajectories (Table S6b, re-run 2026-08-14).

Non-converging entries are drawn, never dropped: an arm that did not thermalize
inside its budget is an open marker with an up-arrow just above *its own* budget
line. Writing "never" for what is a budget-limited observation is the mistake
Table S6b already had to correct once (NARRATIVE Section 25.5, lesson 5).

Colors are the Okabe-Ito colorblind-safe set, validated for adjacent-pair CVD
separation; every series also carries a distinct marker and a direct label, so
identity never rests on hue alone.

    python u1_2d/scripts/50_seed_quality_figure.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT = Path("out/u1_2d")
FIG = OUT / "paper_appendix" / "figures" / "29_seed_quality.png"

SEED_BUDGET = 640      # crossover_window.json scan ceiling
PROL_BUDGET = 2000     # tiling_baseline_2000 scan ceiling

# Okabe-Ito, fixed order, never cycled. Validated light-mode:
# lightness band PASS, chroma floor PASS, normal-vision floor PASS (18.7),
# CVD separation 7.6 (floor band -> secondary encoding required, supplied by
# distinct markers + direct labels).
STYLE = {
    "seed": ("#D55E00", "o", "diffusion seed"),
    "cold": ("#0072B2", "s", "fresh cold start"),
    "hot":  ("#56B4E9", "^", "fresh hot start"),
    "ape":  ("#009E73", "D", "APE-smeared prolongator"),
    "geom": ("#CC79A7", "x", "geometric prolongators"),
}
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"


def load():
    rows = json.loads((OUT / "thermalization" / "crossover_window.json").read_text())["rows"]
    scan = {k: [(r["beta"], r[k]) for r in rows if r.get(k) is not None] for k in ("seed", "hot", "cold")}

    prol = json.loads((OUT / "tiling_baseline_2000" / "tiling_baseline.json").read_text())
    ape, geom = [], []
    for case in prol:
        b = case["fine_beta"]
        ape.append((b, case["arms"]["ape"]["t_therm_slowest"]))
        # the three purely geometric maps: plot the BEST of them, since the
        # claim is about the class, not about which member wins.
        vals = [case["arms"][a]["t_therm_slowest"] for a in ("tile", "halve", "flux")]
        finite = [v for v in vals if v is not None]
        geom.append((b, min(finite) if finite else None))
    return scan, ape, geom


def split(points, budget):
    """-> (converged xs, ys), (non-converged xs at the budget ceiling)."""
    cx, cy, nx = [], [], []
    for b, t in points:
        if t is None or t == float("inf"):
            nx.append(b)
        else:
            cx.append(b)
            cy.append(t)
    return (cx, cy), nx


def main() -> int:
    scan, ape, geom = load()
    fig, ax = plt.subplots(figsize=(8.2, 5.6))

    # linscale compresses the 0..1 linear band so it does not eat a whole decade
    ax.set_yscale("symlog", linthresh=1.0, linscale=0.38)
    ax.set_xscale("log")

    # budget ceilings -- two different scans, and the reader must see that.
    for budget, label, dash in ((SEED_BUDGET, "640-trajectory budget", (4, 3)),
                                (PROL_BUDGET, "2000-trajectory budget", (1, 2))):
        ax.axhline(budget, color=MUTED, lw=0.9, ls=(0, dash), zorder=1)
        ax.text(1.35, budget * 1.12, label, fontsize=7.5, color=MUTED, va="bottom")

    series = [
        ("seed", scan["seed"], SEED_BUDGET, 2.4, 7.0, 6),
        ("cold", scan["cold"], SEED_BUDGET, 1.4, 5.0, 4),
        ("hot",  scan["hot"],  SEED_BUDGET, 1.4, 5.0, 3),
        ("ape",  ape,          PROL_BUDGET, 1.6, 6.5, 5),
        ("geom", geom,         PROL_BUDGET, 1.2, 6.5, 2),
    ]

    for key, pts, budget, lw, ms, z in series:
        color, marker, _ = STYLE[key]
        (cx, cy), nx = split(pts, budget)
        order = sorted(range(len(cx)), key=lambda i: cx[i])
        cx = [cx[i] for i in order]
        cy = [cy[i] for i in order]
        ax.plot(cx, cy, color=color, marker=marker, ms=ms, lw=lw, zorder=z,
                markeredgecolor="white" if marker not in ("x",) else color,
                markeredgewidth=0.6, alpha=0.95)
        # non-converged: open marker + arrow, just above that arm's own ceiling
        for b in nx:
            ax.plot([b], [budget * 1.45], color=color, marker=marker, ms=ms,
                    markerfacecolor="none", markeredgecolor=color,
                    markeredgewidth=1.2, zorder=z, clip_on=False)
            ax.annotate("", xy=(b, budget * 2.6), xytext=(b, budget * 1.7),
                        arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0,
                                        shrinkA=0, shrinkB=0), zorder=z)

    ax.text(1.45, PROL_BUDGET * 3.0, "did not converge within budget",
            fontsize=8, color=MUTED, style="italic")

    # direct labels -- secondary encoding for the CVD floor-band pair, and the
    # relief the contrast check requires.
    for key, x, y, va, ha in (("seed", 950, 6.0, "bottom", "right"),
                              ("cold", 950, 480, "bottom", "right"),
                              ("ape", 260, 120, "top", "right")):
        ax.annotate(STYLE[key][2], xy=(x, y), fontsize=9,
                    color=STYLE[key][0], ha=ha, va=va, fontweight="bold")

    ax.set_xlabel(r"fine coupling  $\beta_f$", fontsize=10, color=INK)
    ax.set_ylabel("trajectories to thermalization", fontsize=10, color=INK)
    ax.set_title("What a starting configuration costs an exact HMC chain   ($L = 32$)",
                 fontsize=11.5, color=INK, pad=12, loc="left")

    ax.set_yticks([0, 1, 10, 100, 1000])
    ax.set_yticklabels(["0", "1", "10", "100", "1000"])
    ax.set_ylim(-0.4, PROL_BUDGET * 6)
    ax.set_xlim(1.25, 1200)

    ax.grid(True, which="major", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8.5)

    handles = [Line2D([], [], color=c, marker=m, ms=6, lw=1.6, label=lab,
                      markeredgecolor="white" if m != "x" else c, markeredgewidth=0.6)
               for c, m, lab in STYLE.values()]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.135),
              fontsize=8.5, frameon=False, ncol=5, labelcolor=INK,
              handletextpad=0.5, columnspacing=1.6)

    fig.text(0.5, 0.006,
             "seed / hot / cold: 35-point scan to 640 trajectories.  "
             "prolongators: Table S6b, 5 couplings to 2000 trajectories.  "
             "geometric = best of tile / halve / flux.",
             fontsize=6.8, color=MUTED, ha="center")

    fig.tight_layout(rect=(0, 0.085, 1, 1))
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=200)
    print(f"wrote {FIG}")

    n_seed = len(scan["seed"])
    finite = [t for _, t in scan["seed"] if t not in (None, float("inf"))]
    print(f"  seed: {n_seed} couplings, t_therm range {min(finite):.0f}-{max(finite):.0f}, "
          f"median {sorted(finite)[len(finite)//2]:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
