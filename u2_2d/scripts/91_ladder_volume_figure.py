"""Volume scaling of the improvement factor, along the matched ladder.

The three seed benchmarks are the ladder itself:

    (L, beta) = (32, 105.651) -> (64, 416.524) -> (128, 1660.076)

each step doubling L and quadrupling beta, which is the matching condition that
holds chi_t V fixed. So these are not three unrelated volumes, they are one
physical setup at three lattice spacings, and the volume axis is a
continuum-limit trajectory rather than a scan.

Four arms are common to all three rungs, which is what makes them comparable:

    A  lifted configuration, plain HMC
    D  cold start, HMC + the free even-charge winding move
    G  cold start, HMC + the expensive marginal odd-charge move
    H  lifted configuration, HMC + the marginal odd-charge move

COSTING. An independent, correctly distributed configuration costs

    classical:  interval        (t_therm is paid once and amortizes away)
    lift:       t_therm         (paid again for every configuration)

The asymmetry is not a favour to the lift, it is the opposite. A classical chain
pays its burn-in once and then waits out its own autocorrelation for each
configuration after that, so N of them cost t_therm + N * interval and the
per-configuration cost tends to the interval; charging it t_therm every time
would be the N = 1 answer. The lift has no interval to pay, because successive
lifts descend from independent base chains and are independent by construction,
but it does pay its own t_therm for every single configuration.

t_therm still gates the classical arm. Its interval is the cost of an
independent configuration only if the chain reached the right distribution at
all: one that never equilibrates decorrelates perfectly happily about the wrong
one, and calling that a supply of independent configurations is the error this
costing exists to avoid.

    python u2_2d/scripts/91_ladder_volume_figure.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from u2_2d.lgt.exact import (det_topological_charge_distribution as pq2,  # noqa: E402
                             wilson_loop_exact as u2x)
from u2_2d.validate.stats import integrated_autocorrelation_time  # noqa: E402

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
BUDGET = 400.0
OBS = (("wilson_1x1", 1), ("wilson_2x2", 4), ("wilson_4x4", 16))

RUNGS = [
    ("out/u2_2d/seed_benchmark_rung0", 32, 105.651),
    ("out/u2_2d/seed_benchmark", 64, 416.524),
    ("out/u2_2d/seed_benchmark_wide_L128", 128, 1660.076283),
]
ARMS = [
    ("arm_A_diffusion_seed", "lift", "#D55E00", "lift, plain HMC"),
    ("arm_H_diffusion_plus_odd_winding", "lift", "#E8A87C",
     r"lift $+$ odd winding"),
    ("arm_D_cold_plus_winding", "classical", "#0072B2",
     r"cold $+$ even winding"),
    ("arm_G_cold_plus_odd_winding", "classical", "#333333",
     r"cold $+$ odd winding"),
]


def series(path, stem, key):
    h = json.loads((ROOT / path / f"{stem}.json").read_text())["history"]
    arr = np.array([r["charge"] if key == "charge" else r[key + "_chain"]
                    for r in h], dtype=float)
    step = h[1]["trajectory"] - h[0]["trajectory"]
    return arr, step


def interval(arr, step):
    tail = arr[arr.shape[0] // 2:]
    if np.allclose(tail, tail[0]):
        return float("inf")
    taus, moving = [], 0
    for c in range(tail.shape[1]):
        col = tail[:, c]
        if np.allclose(col, col[0]):
            continue
        moving += 1
        t, _ = integrated_autocorrelation_time(col)
        if np.isfinite(t) and t > 0:
            taus.append(t)
    if not taus:
        return float("inf")
    return 2.0 * float(np.median(taus)) * step / max(moving / tail.shape[1], 1e-9)


def therm(arr, exact, step):
    n_rec, n_ch = arr.shape
    mean = arr.mean(axis=1)
    sem = arr[n_rec // 2:].std(axis=1).mean() / np.sqrt(n_ch)
    if not np.isfinite(sem) or sem <= 0:
        return float("nan")
    ok = np.abs(mean - exact) <= 2.0 * sem
    run = 0
    for i, v in enumerate(ok):
        run = run + 1 if v else 0
        if run >= 5:
            return float((i - 4) * step)
    return float("inf")


def measure(path, L, beta, stem):
    if not (ROOT / path / f"{stem}.json").exists():
        return None
    qv, pq = pq2(beta, L)
    q2ex = float((qv ** 2 * pq).sum())
    tts, ivs = [], []
    for key, area in OBS:
        arr, step = series(path, stem, key)
        tts.append(therm(arr, u2x(beta, area, lattice_size=L), step))
        ivs.append(interval(arr, step))
    arr, step = series(path, stem, "charge")
    tts.append(therm(arr ** 2, q2ex, step))
    ivs.append(interval(arr ** 2, step))
    return float(np.nanmax(tts)), max(ivs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out/u2_2d/figures/fig65_ladder.png"))
    args = ap.parse_args()

    data = {}
    for path, L, beta in RUNGS:
        for stem, kind, _, _ in ARMS:
            m = measure(path, L, beta, stem)
            if m is None:
                continue
            tt, iv = m
            cost = tt if kind == "lift" else (
                iv if np.isfinite(tt) and np.isfinite(iv) else float("inf"))
            data[(L, stem)] = (tt, iv, cost)
            print(f"L={L:4d} {stem[6:]:30s} t_therm={tt:7.1f} interval={iv:8.2f} "
                  f"cost={cost:8.1f}")

    Ls = [L for _, L, _ in RUNGS]
    x = np.arange(len(Ls))
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.3))

    ax = axes[0]
    ZERO = 0.55      # where an already-equilibrated arm, t_therm = 0, is drawn
    for stem, kind, colour, label in ARMS:
        xs, ys, bx = [], [], []
        off = 0.0 if kind == "lift" else (-0.07 if "even" in label else 0.07)
        for i, L in enumerate(Ls):
            if (L, stem) not in data:
                continue
            c = data[(L, stem)][2]
            if np.isfinite(c):
                xs.append(i + off); ys.append(max(c, ZERO))
            else:
                bx.append(i + off)
        ls = "-" if kind == "lift" else "none"
        mk = "o" if kind == "lift" else "s"
        if xs:
            ax.plot(xs, ys, ls, marker=mk, color=colour, ms=6.5, lw=1.8,
                    zorder=3, label=label, markeredgecolor="white",
                    markeredgewidth=0.6)
        for x0 in bx:
            ax.annotate("", xy=(x0, BUDGET * 6.0), xytext=(x0, BUDGET),
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=2.0))
    ax.axhline(ZERO, color=MUTED, ls=":", lw=1.0, zorder=1)
    ax.text(0.02, 0.055, "already equilibrated ($t_{\\rm therm}=0$)",
            transform=ax.transAxes, fontsize=7.5, color=MUTED)
    ax.set_ylim(0.35, BUDGET * 40)
    ax.set_ylabel("trajectories per independent\nconfiguration", fontsize=9.5,
                  color=INK, linespacing=1.4)
    ax.set_title("(a)  cost along the ladder", fontsize=9.5, color=INK, loc="left")
    ax.text(0.5, 0.965, "arrows: never, in $400$ trajectories",
            transform=ax.transAxes, ha="center", va="top", fontsize=7.5,
            color=MUTED)

    ax2 = axes[1]
    # No line is drawn through the bounds. Where the classical arm never
    # equilibrates the factor is unbounded, and the plotted height is only
    # budget/lift-cost: joining two such points draws a trend out of the
    # trajectory budget rather than out of the physics, and at L=64 and L=128
    # that fake trend slopes the wrong way.
    for stem, kind, colour, label in ARMS:
        if kind != "classical":
            continue
        for i, L in enumerate(Ls):
            if (L, stem) not in data or (L, "arm_A_diffusion_seed") not in data:
                continue
            cl = data[(L, stem)][2]
            lf = max(data[(L, "arm_A_diffusion_seed")][0], 1.0)
            off = -0.07 if "even" in label else 0.07
            if np.isfinite(cl):
                ax2.plot([i + off], [cl / lf], "s", color=colour, ms=7, zorder=4,
                         markeredgecolor="white", markeredgewidth=0.6,
                         label=None)
            else:
                y0 = BUDGET / lf
                ax2.annotate("", xy=(i + off, y0 * 9.0), xytext=(i + off, y0),
                             arrowprops=dict(arrowstyle="-|>", color=colour,
                                             lw=2.0))
    ax2.axhspan(BUDGET, 1e5, color="#2ca02c", alpha=0.07, zorder=0)
    ax2.axhline(1.0, color=MUTED, ls=":", lw=1.2, zorder=1)
    ax2.set_ylim(0.5, 1e5)
    ax2.set_ylabel("improvement factor", fontsize=9.5, color=INK)
    ax2.set_title("(b)  improvement factor", fontsize=9.5, color=INK, loc="left")
    ax2.text(0.5, 0.965,
             "arrows: classical arm never\nequilibrates, factor unbounded",
             transform=ax2.transAxes, ha="center", va="top", fontsize=7.5,
             color=MUTED, linespacing=1.4)

    for a in axes:
        a.set_yscale("log")
        a.set_xticks(x)
        a.set_xticklabels([f"${L}^2$\n" + r"$\beta=" + f"{b:.0f}$"
                           for (_, L, b) in RUNGS], fontsize=8.5)
        a.set_xlim(-0.35, len(Ls) - 0.65)
        a.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.tick_params(colors=MUTED, labelsize=8.5)

    # one legend only: panel (b) reuses panel (a)'s colours, and repeating them
    # as "vs cold + ..." doubled every entry
    h1, l1 = axes[0].get_legend_handles_labels()
    fig.legend(h1, l1, loc="lower center", ncol=4, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, -0.13))
    fig.suptitle("Climbing the matched ladder: the classical cost diverges, the lift's does not",
                 fontsize=10.5, color=INK, y=1.0)
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
