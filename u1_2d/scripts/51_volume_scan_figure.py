"""Figure 30 — does the diffusion seed's thermalization cost grow with volume?

The one experiment the prolongator framing needed and the study did not have.
Fixed beta_f = 14.1464, three volumes (L = 32 / 64 / 128, V = 2L^2 = 2048 /
8192 / 32768) -- the same 16x range the sector-tail scaling used, so the two
answers are directly comparable.

The raw answer is that `t_therm` grows: 1 -> 3 -> 30 trajectories. Reporting
that alone would be wrong, because `t_therm` is defined by

    z(t) = (ensemble mean - exact) / SEM,     SEM = std_over_chains / sqrt(B)
    t_therm = first t with |z| <= 2 for 5 consecutive trajectories

and the per-chain spatial mean self-averages, so SEM falls with volume. A
*volume-independent* per-site bias therefore produces a z that GROWS like
sqrt(V), and the acceptance threshold tightens with no change in the seed.

That is what happens. The measured plaquette bias at t = 0 is flat --
+9.7e-4, +8.5e-4, +9.7e-4 -- while SEM falls 3.1e-4 -> 1.6e-4, so z climbs
3.11 -> 3.24 -> 6.06 on a seed of constant quality. Panel (b) draws both.

The asymmetry that explains why the seed is more sensitive to this than the
baseline: a cold start anneals an O(1) bias, so its t_therm is set by the
relaxation rate and the threshold enters only logarithmically; the seed starts
a hair above threshold, so its t_therm is set almost entirely by where the
threshold sits. Both grow; the seed's grows faster for a reason that is about
the measurement, not the model.

    python u1_2d/scripts/51_volume_scan_figure.py
"""

import glob
import json
import math
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from u1_2d.lgt import exact

OUT = Path("out/u1_2d")
SCAN = OUT / "thermalization_volume"
FIG = OUT / "paper_appendix" / "figures" / "30_volume_scan.png"

SEED, COLD, HOT = "#D55E00", "#0072B2", "#56B4E9"
BIAS, SEMC = "#009E73", "#CC79A7"
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
WILSON = ("plaquette", "wilson_2x2", "wilson_4x4")


def load():
    rows = []
    for f in glob.glob(str(SCAN / "*" / "*_summary.json")):
        s = json.loads(Path(f).read_text(encoding="utf-8"))
        if "t_therm" not in s:
            continue
        L, beta = s["lattice_size"], float(s["beta"])
        ser = np.load(f.replace("_summary.json", "_series.npz"), allow_pickle=True)
        sub = s["t_therm_subsample_size"]
        p = ser["diffusion seed|plaquette"][:, :sub]
        tgt = exact.plaquette_exact(beta, "wilson", L)
        rows.append({
            "L": L, "V": 2 * L * L, "beta": beta, "B": sub,
            "seed": max(s["t_therm"]["diffusion seed"][n] for n in WILSON),
            "cold": max(s["t_therm"]["cold start"][n] for n in WILSON),
            "hot": max(s["t_therm"]["hot start"][n] for n in WILSON),
            "bias0": float(p[0].mean() - tgt),
            "sem0": float(p[0].std(ddof=1) / math.sqrt(sub)),
        })
    return sorted(rows, key=lambda r: r["V"])


def main() -> int:
    rows = load()
    V = [r["V"] for r in rows]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.9, 2.82))

    # ---- panel (a): the raw t_therm answer -------------------------------
    for key, color, marker, label in (("seed", SEED, "o", "diffusion seed"),
                                      ("cold", COLD, "s", "fresh cold start"),
                                      ("hot", HOT, "^", "fresh hot start")):
        vals = [r[key] for r in rows]
        fin = [(v, y) for v, y in zip(V, vals) if np.isfinite(y)]
        if fin:
            ax.plot([v for v, _ in fin], [y for _, y in fin], color=color,
                    marker=marker, ms=7, lw=2.0,
                    markeredgecolor="white", markeredgewidth=0.6, label=label)
        else:  # never converged anywhere -- still needs to appear in the legend
            ax.plot([], [], color=color, marker=marker, ms=7, lw=2.0,
                    markerfacecolor="none", markeredgewidth=1.3, label=label)
        for v, y in zip(V, vals):
            if not np.isfinite(y):
                ax.plot([v], [900], color=color, marker=marker, ms=7,
                        markerfacecolor="none", markeredgecolor=color, markeredgewidth=1.3)
                ax.annotate("", xy=(v, 1500), xytext=(v, 1020),
                            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0,
                                            shrinkA=0, shrinkB=0))
    ax.axhline(640, color=MUTED, lw=0.9, ls=(0, (4, 3)))
    ax.text(2.9e4, 700, "640-trajectory budget", fontsize=7.5, color=MUTED, ha="right")
    ax.text(2050, 2300, "never converged", fontsize=8, color=MUTED, style="italic")

    for r in rows:
        if np.isfinite(r["seed"]):
            ax.annotate(f"{r['seed']:.0f}", xy=(r["V"], r["seed"]), xytext=(0, -14),
                        textcoords="offset points", ha="center", fontsize=8.5,
                        color=SEED, fontweight="bold")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(V)
    ax.set_xticklabels([f"$2^{{{int(round(math.log2(v)))}}}$\n$L={r['L']}$" for v, r in zip(V, rows)])
    ax.set_ylim(0.55, 4000)
    ax.set_xlabel("volume  $V = 2L^2$", fontsize=10, color=INK)
    ax.set_ylabel("trajectories to thermalization", fontsize=10, color=INK)
    ax.set_title("(a)  raw answer: $t_{\\mathrm{therm}}$ does grow", fontsize=10.5,
                 color=INK, loc="left", pad=10)
    ax.legend(fontsize=8.5, frameon=False, loc="center left", labelcolor=INK)

    # ---- panel (b): why -- flat bias, shrinking SEM ----------------------
    bias = [abs(r["bias0"]) for r in rows]
    sem = [r["sem0"] for r in rows]
    bx.plot(V, bias, color=BIAS, marker="D", ms=7, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.6, label="|plaquette bias| of the seed")
    bx.plot(V, sem, color=SEMC, marker="v", ms=7, lw=2.0,
            markeredgecolor="white", markeredgewidth=0.6,
            label="SEM (the $|z|\\leq2$ acceptance width)")
    bx.fill_between(V, sem, bias, color=SEMC, alpha=0.10, lw=0)

    for v, b, s in zip(V, bias, sem):
        bx.annotate(f"z={b/s:.1f}", xy=(v, math.sqrt(b * s)), ha="center", va="center",
                    fontsize=8.5, color=INK, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.85))

    bx.set_xscale("log")
    bx.set_yscale("log")
    bx.set_xticks(V)
    bx.set_xticklabels([f"$2^{{{int(round(math.log2(v)))}}}$\n$L={r['L']}$" for v, r in zip(V, rows)])
    bx.set_xlabel("volume  $V = 2L^2$", fontsize=10, color=INK)
    bx.set_ylabel("plaquette (absolute units)", fontsize=10, color=INK)
    bx.set_title("(b)  why: the seed is unchanged, the threshold tightens", fontsize=10.5,
                 color=INK, loc="left", pad=10)
    bx.legend(fontsize=8.5, frameon=False, loc="lower left", labelcolor=INK)

    for a in (ax, bx):
        a.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        a.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        a.grid(True, which="major", color=GRID, lw=0.6)
        a.set_axisbelow(True)
        for side in ("top", "right"):
            a.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            a.spines[side].set_color(MUTED)
            a.spines[side].set_linewidth(0.8)
        a.tick_params(colors=MUTED, labelsize=8.5)

    fig.suptitle("Does the seed's thermalization cost grow with volume?   "
                 "($\\beta_f = 14.1464$ fixed)",
                 fontsize=12, color=INK, x=0.008, ha="left", y=0.985)
    fig.text(0.5, 0.008,
             "Chains used for $t_{\\mathrm{therm}}$: 32 / 16 / 8 -- part of the SEM decrease is "
             "this, not self-averaging alone. A cleaner rerun would hold the chain count fixed.",
             fontsize=7, color=MUTED, ha="center")

    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=319)
    print(f"wrote {FIG}")
    for r in rows:
        print(f"  L={r['L']:4d} V={r['V']:6d} B={r['B']:3d}  seed={r['seed']:6.0f} "
              f"cold={r['cold']:6.0f} hot={r['hot']}  bias={r['bias0']:+.6f} "
              f"sem={r['sem0']:.6f} z={r['bias0']/r['sem0']:5.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
