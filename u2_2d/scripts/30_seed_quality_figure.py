"""Figure 21 -- trajectories to thermalization vs beta. The u2 lead figure.

The port of u1's `50_seed_quality_figure.py` (its Fig. 29), and the figure this
study's central claim lives or dies on: what a diffusion-generated starting
configuration costs an exact HMC chain, across the coupling range that crosses
INTO the frozen regime.

SIX ARMS, NOT THREE. `28_crossover_scan.py` is run twice over the same couplings
with the same seed, so the cold and hot initialisations are PAIRED:

  plain round    every arm runs plain HMC. This is u1's experiment verbatim.
  winding round  every arm runs HMC + the marginal odd winding move
                 (docs/INSTANTON.md), which is the honest ergodic classical
                 baseline for this theory since 2026-08-20.

Neither round is "the" answer and the figure draws both rather than choosing:
against plain HMC the seed's advantage is partly that HMC cannot do topology at
all, which is a different and weaker claim than the one this study wants; against
the winding round the comparison is like-for-like and the seed has to earn it.

THE YARDSTICK IS `interval`, NOT THE COLD ARM. A ratio against a cold start
flatters the seed at every coupling and means nothing on its own. What means
something is `interval` = 2 tau_int, the number of trajectories a WORKING chain
of that same sampler needs between two independent configurations. A seed that
thermalizes in fewer trajectories than that is cheaper per independent
configuration; a seed that thermalizes in more is not, however large its ratio
against a cold start. u1 draws that line and so does this.

ONE PHYSICS CAVEAT THE FIGURE CARRIES ON ITS FACE. At FIXED L, raising beta
shrinks the exact <Q^2>, so the right-hand end of this scan is not "hard
topology" but a theory with almost no topology, where a frozen chain reproduces
P(Q) nearly correctly by accident. The <Q^2> track is drawn under the main axes
for exactly that reason -- the frozen regime is only interesting while <Q^2> is
still O(1).

    python u2_2d/scripts/30_seed_quality_figure.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

# Okabe-Ito, colourblind-safe, fixed order; every series also carries a distinct
# marker so identity never rests on hue alone.
STYLE = {
    "diffusion seed": ("#D55E00", "o", "diffusion seed"),
    "cold start": ("#0072B2", "s", "fresh cold start"),
    "hot start": ("#56B4E9", "^", "fresh hot start"),
}
ARMS = ["diffusion seed", "cold start", "hot start"]
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
REGIME_SHADE = {
    "Q frozen": ("#9ecae1", 0.16),
    "parity frozen": ("#c6dbef", 0.16),
    "HMC dead": ("#fdae6b", 0.20),
}


def slowest(record, arm):
    vals = record["t_therm"].get(arm)
    if not vals:
        return float("inf")
    return max(float(v) for v in vals.values())


def split(points):
    """-> (converged xs, ys), (non-converged xs). Never drop a non-converger."""
    cx, cy, nx = [], [], []
    for b, t in points:
        if t is None or not math.isfinite(t):
            nx.append(b)
        else:
            cx.append(b)
            cy.append(t)
    order = sorted(range(len(cx)), key=lambda i: cx[i])
    return ([cx[i] for i in order], [cy[i] for i in order]), nx


# Training rungs of the DEPLOYED checkpoint, in model beta (the minimum-KL U(1)
# projection the score net is conditioned on, `lgt.exact.matched_u1_beta`). The
# net is fully convolutional and conditioned on this, NOT on L, so this list is
# the whole of its coverage. Above the maximum the model EXTRAPOLATES, and the
# scan's top couplings do exactly that -- beta_f = 537 is model beta 134, which
# is 29% past the last rung. Marking it is not decoration: without it a reader
# takes "seed does not thermalize at beta_f >= 537" for a statement about the
# method, when it is a statement about what this checkpoint was shown.
TRAIN_MODEL_BETA = [0.622, 1.705, 3.560, 7.020, 12.946, 14.008, 26.417,
                    50.789, 104.132]


def draw_round(ax, rows, budget, title):
    betas = [r["beta"] for r in rows]

    # Extrapolation region, and the training rungs that bound it.
    mb = {r["beta"]: r.get("model_beta") for r in rows}
    inside = [b for b in betas if mb.get(b) and mb[b] <= max(TRAIN_MODEL_BETA)]
    if inside and len(inside) < len(betas):
        edge = math.sqrt(max(inside) * min(b for b in betas if b > max(inside)))
        # Hatched and unfilled, NOT another wash of colour: the regime bands are
        # already orange/blue, and a third tint reads as a fourth regime rather
        # than as a statement about the model.
        ax.axvspan(edge, betas[-1] * 1.2, facecolor="none", edgecolor="#5a3a8a",
                   hatch="///", lw=0.0, alpha=0.55, zorder=2)
        ax.axvline(edge, color="#5a3a8a", lw=1.2, ls=(0, (3, 2)), zorder=3)
        ax.text(math.sqrt(edge * betas[-1]), 0.5,
                "model EXTRAPOLATES" + chr(10) + "(beyond training coverage)",
                fontsize=7, color="#5a3a8a", ha="center",
                va="center", style="italic")
    for t in TRAIN_MODEL_BETA:
        # Training rungs live in MODEL beta; place each at the fine beta whose
        # model beta matches, by interpolating the scan's own (beta, model_beta).
        pairs = sorted((v, k) for k, v in mb.items() if v)
        if not pairs or not (pairs[0][0] <= t <= pairs[-1][0]):
            continue
        for (v0, b0), (v1, b1) in zip(pairs, pairs[1:]):
            if v0 <= t <= v1:
                f = 0.0 if v1 == v0 else (t - v0) / (v1 - v0)
                ax.plot([b0 * (b1 / b0) ** f], [0], marker="|", ms=9,
                        color="#2e7d32", mew=1.6, clip_on=False, zorder=7)
                break

    # Regime bands first, so everything else sits on top of them.
    for i, r in enumerate(rows):
        shade = REGIME_SHADE.get(r.get("regime"))
        if shade is None:
            continue
        colour, alpha = shade
        lo = math.sqrt(betas[i - 1] * r["beta"]) if i else r["beta"] / 1.15
        hi = (math.sqrt(betas[i + 1] * r["beta"]) if i + 1 < len(betas)
              else r["beta"] * 1.15)
        ax.axvspan(lo, hi, color=colour, alpha=alpha, lw=0, zorder=0)

    ax.set_yscale("symlog", linthresh=1.0, linscale=0.38)
    ax.set_xscale("log")

    # PER-COUPLING budget ceiling. n_steps scales as sqrt(beta), so a flat budget
    # is unaffordable at the top of the scan; each coupling records the budget it
    # actually got and it is drawn as a step, because "did not converge" is a
    # statement about a specific ceiling and reading it against the wrong one is
    # the mistake u1's Table S6b had to correct once.
    caps = [float(r.get("n_traj") or budget) for r in rows]
    ax.step(betas, caps, where="mid", color=MUTED, lw=0.9, ls=(0, (4, 3)), zorder=1)
    ax.text(betas[0] * 0.92, caps[0] * 1.12, "trajectory budget",
            fontsize=7.5, color=MUTED, va="bottom")

    # THE YARDSTICK. Everything above this line costs more than simply running
    # the chain; everything below it is a saving.
    iv = [(r["beta"], r.get("interval")) for r in rows
          if r.get("interval") and math.isfinite(r["interval"])]
    if iv:
        ax.plot([b for b, _ in iv], [v for _, v in iv], color="#111111", lw=1.5,
                ls=(0, (6, 2, 1, 2)), zorder=6)
        ax.fill_between([b for b, _ in iv], 1e-3, [v for _, v in iv],
                        color="#111111", alpha=0.05, lw=0, zorder=0)

    for arm in ARMS:
        colour, marker, _ = STYLE[arm]
        pts = [(r["beta"], slowest(r, arm)) for r in rows]
        cap_of = dict(zip(betas, caps))
        (cx, cy), nx = split(pts)
        lw, ms, z = (2.4, 7.0, 5) if arm == "diffusion seed" else (1.4, 5.0, 4)
        ax.plot(cx, cy, color=colour, marker=marker, ms=ms, lw=lw, zorder=z,
                markeredgecolor="white", markeredgewidth=0.6, alpha=0.95)
        for b in nx:
            cap = cap_of[b]
            ax.plot([b], [cap * 1.45], color=colour, marker=marker, ms=ms,
                    markerfacecolor="none", markeredgecolor=colour,
                    markeredgewidth=1.2, zorder=z, clip_on=False)
            ax.annotate("", xy=(b, cap * 2.6), xytext=(b, cap * 1.7),
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.0,
                                        shrinkA=0, shrinkB=0), zorder=z)

    ax.set_yticks([0, 1, 10, 100, 1000])
    ax.set_yticklabels(["0", "1", "10", "100", "1000"])
    ax.set_ylim(-0.4, max(caps) * 6)
    ax.set_xlabel(r"fine coupling  $\beta_f$", fontsize=10, color=INK)
    ax.set_title(title, fontsize=10.5, color=INK, pad=10, loc="left")
    ax.grid(True, which="major", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))


def draw_q2(ax, rows):
    """The caveat track: exact <Q^2> falling as beta rises at fixed L."""
    ax.plot([r["beta"] for r in rows], [r["q_squared_exact"] for r in rows],
            color="#444444", lw=1.3, marker=".", ms=4)
    ax.axhline(1.0, color=MUTED, lw=0.8, ls=(0, (2, 2)))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylabel(r"exact $\langle Q^2\rangle$", fontsize=8.5, color=MUTED)
    ax.set_xlabel(r"fine coupling  $\beta_f$", fontsize=8.5, color=MUTED)
    ax.tick_params(colors=MUTED, labelsize=7.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    ax.grid(True, which="major", color=GRID, lw=0.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.annotate("below 1 there is barely any topology left to freeze",
                xy=(0.99, 0.10), xycoords="axes fraction", fontsize=7,
                color=MUTED, ha="right", style="italic")


def report(name, rows):
    print("")
    print(name + "  (" + str(len(rows)) + " couplings)")
    header = ("beta".rjust(9) + "<Q^2>ex".rjust(9) + "seed".rjust(8)
              + "cold".rjust(8) + "hot".rjust(8) + "2tau".rjust(8)
              + "flips".rjust(8) + "  regime")
    print("  " + header)
    for r in rows:
        s, c, h = (slowest(r, a) for a in ARMS)
        fl = r.get("parity_flips", {}).get("cold start")
        print("  " + "".join([
            "%9.2f" % r["beta"], "%9.3f" % r["q_squared_exact"],
            "%8.1f" % s, "%8.1f" % c, "%8.1f" % h,
            "%8.1f" % (r.get("interval") or float("nan")),
            ("-" if fl is None else str(fl)).rjust(8),
            "  " + str(r.get("regime", "?"))]))
    beats = [r for r in rows
             if math.isfinite(slowest(r, "diffusion seed")) and r.get("interval")
             and slowest(r, "diffusion seed") <= r["interval"]]
    line = ("  seed thermalizes inside the decorrelation interval at "
            + str(len(beats)) + "/" + str(len(rows)) + " couplings")
    if beats:
        line += " (beta >= %.1f)" % min(r["beta"] for r in beats)
    print(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="out/u2_2d/crossover")
    parser.add_argument("--budget", type=int, default=400)
    parser.add_argument("--out", default="out/u2_2d/figures/fig21_seed_quality.png")
    args = parser.parse_args()

    # The scan is split across processes so it finishes in an evening, so the
    # round a row belongs to is read off the ROW (`topological_updates`), never
    # off the filename. Duplicate couplings keep the most recent file's version.
    src = Path(args.dir)
    merged = {False: {}, True: {}}
    for path in sorted(src.glob("*.json"), key=lambda q: q.stat().st_mtime):
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(rows, list):
            continue
        for r in rows:
            if "beta" in r and "t_therm" in r:
                merged[bool(r.get("topological_updates"))][r["beta"]] = r

    rounds = []
    for flag, stem, title in (
            (False, "plain", "(a) plain HMC in every arm"),
            (True, "winding",
             r"(b) HMC + marginal winding ($\Delta Q=1$) in every arm")):
        rows = sorted(merged[flag].values(), key=lambda r: r["beta"])
        if rows:
            rounds.append((stem, title, rows))
    if not rounds:
        print("no crossover json under " + str(src))
        return 1

    n = len(rounds)
    fig = plt.figure(figsize=(7.4 * n, 6.4))
    gs = fig.add_gridspec(2, n, height_ratios=(3.2, 1.0), hspace=0.38, wspace=0.22)
    for i, (_, title, rows) in enumerate(rounds):
        ax = fig.add_subplot(gs[0, i])
        draw_round(ax, rows, args.budget, title)
        if i == 0:
            ax.set_ylabel("trajectories to thermalization", fontsize=10, color=INK)
        draw_q2(fig.add_subplot(gs[1, i]), rows)

    handles = [Line2D([], [], color=c, marker=m, ms=6, lw=1.6, label=lab,
                      markeredgecolor="white", markeredgewidth=0.6)
               for c, m, lab in STYLE.values()]
    handles.append(Line2D([], [], color="#111111", lw=1.5, ls=(0, (6, 2, 1, 2)),
                          label=r"$2\tau_{\rm int}$: the yardstick"))
    handles.append(Line2D([], [], color="#2e7d32", lw=0, marker="|", ms=9,
                          mew=1.6, label="training rung"))
    handles.append(Patch(facecolor="none", edgecolor="#5a3a8a", hatch="///",
                         label="model extrapolates"))
    handles.append(Line2D([], [], color="#9ecae1", lw=8, alpha=0.5, label="Q frozen"))
    handles.append(Line2D([], [], color="#fdae6b", lw=8, alpha=0.6, label="HMC dead"))
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.012),
               fontsize=8.5, frameon=False, ncol=len(handles), labelcolor=INK,
               handletextpad=0.5, columnspacing=1.6)

    fig.suptitle("What a starting configuration costs an exact HMC chain   "
                 r"($L_f = 32$, lifted from $L_c = 16$)",
                 fontsize=12, color=INK, x=0.02, ha="left", y=1.0)
    fig.text(0.5, -0.055,
             "t_therm is the SLOWEST of plaquette / W(2x2) / W(4x4) against the "
             "closed form; topology is excluded on purpose and tracked separately.  "
             "Both rounds share a seed, so cold and hot starts are paired.",
             fontsize=6.8, color=MUTED, ha="center")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote " + str(dest))

    for stem, title, rows in rounds:
        report(stem, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
