"""Figure 27 -- does the seed's advantage survive a doubling of the volume?

u1's main-text figure 13 (`30_volume_scan.png`) asks this and gives a two-sided
answer. This is the u2 equivalent, and it is the last figure-parity gap.

THE DESIGN. The L=64 scan's four bases were chosen by MODEL BETA, not by fine
beta, precisely so the comparison isolates volume from training coverage -- each
one sits within ~2% in model beta of an L=32 scan point, so the pairs differ in
volume and in almost nothing else. That makes a PAIRED plot legitimate, which is
what panel (b) draws.

THE RESULT, and it is genuinely two-sided:
* The coverage ORDERING transfers exactly. The point nearest a training rung is
  the best at both volumes; the point past the top rung is dead at both.
* But quality degrades with volume at FIXED coverage, and at one pair it
  degrades catastrophically: at model beta ~45, the same gap to the nearest
  training rung, `t_therm` is 6 at L=32 and never at L=64.

So volume is a second variable, not a re-labelling of coverage. Any claim of the
form "seed quality is governed by distance to training coverage" must carry this
caveat.

    python u2_2d/scripts/38_volume_figure.py
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
TOP_RUNG = 104.132
TRAIN_MODEL_BETA = [0.622, 1.705, 3.560, 7.020, 12.946, 14.008, 26.417,
                    50.789, TOP_RUNG]
CAP = 400.0   # plotting stand-in for `inf`, drawn as an up-arrow


def gap_pct(mb):
    r = min(TRAIN_MODEL_BETA, key=lambda t: abs(t - mb))
    return 100.0 * (mb - r) / r


def load(paths):
    rows = []
    for pat in paths:
        for f in sorted(glob.glob(pat)):
            rows += json.loads(Path(f).read_text(encoding="utf-8"))
    return sorted(rows, key=lambda r: r["model_beta"])


def val(r, key="seed"):
    v = r.get(key)
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--l32", nargs="*", default=["out/u2_2d/crossover/plain_*.json"])
    ap.add_argument("--l64", nargs="*",
                    default=["out/u2_2d/crossover_L64/volume_L64_plain.json"])
    ap.add_argument("--out", default="out/u2_2d/figures/fig27_volume_scan.png")
    args = ap.parse_args()

    a = load(args.l32)
    b = load(args.l64)
    if not a or not b:
        print("missing scan data")
        return 1

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.9, 2.69))

    # ---- panel (a): seed t_therm vs model beta, both volumes ----------------
    for rows, label, colour, marker in ((a, "L = 32 (from L = 16)", "#0072B2", "o"),
                                        (b, "L = 64 (from L = 32)", "#D55E00", "s")):
        xs = [r["model_beta"] for r in rows]
        ys = [val(r) for r in rows]
        # np.nan at a non-finite point so the line BREAKS there. Joining across
        # an `inf` draws a segment descending into it, which reads as the seed
        # improving through a coupling where it in fact never thermalizes.
        yy = [max(y, 0.7) if y is not None else np.nan for y in ys]
        ax.plot(xs, yy, marker + "-", color=colour, lw=2.0, ms=8,
                markeredgecolor="white", markeredgewidth=0.8, zorder=4,
                label=label)
        for x, y in zip(xs, ys):
            if y is None:
                ax.plot([x], [CAP * 0.55], marker=marker, color=colour, ms=8,
                        markeredgecolor="white", markeredgewidth=0.8, zorder=4)
                ax.annotate("", xy=(x, CAP * 1.15), xytext=(x, CAP * 0.68),
                            arrowprops=dict(arrowstyle="-|>", color=colour,
                                            lw=1.4), zorder=4)
    ax.axvline(TOP_RUNG, color="#5a3a8a", lw=1.2, ls=(0, (3, 2)), zorder=3)
    ax.axvspan(TOP_RUNG, 400, facecolor="none", edgecolor="#5a3a8a",
               hatch="///", lw=0.0, alpha=0.5, zorder=2)
    ax.annotate("model extrapolates", xy=(TOP_RUNG * 1.15, 1.1), fontsize=7.5,
                color="#5a3a8a", ha="left", style="italic")
    for t in TRAIN_MODEL_BETA:
        ax.plot([t], [0.62], marker="|", ms=9, color="#2e7d32", mew=1.6,
                clip_on=False, zorder=7)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_ylim(0.6, CAP * 2.2)
    ax.set_xlabel(r"model $\beta$ of the fine rung", fontsize=10, color=INK)
    ax.set_ylabel("trajectories to thermalization (seed)", fontsize=10, color=INK)
    ax.set_title("(a) both volumes, same axis", fontsize=10.5, loc="left", color=INK)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.grid(alpha=0.25, which="both", color=GRID)

    # ---- panel (b): the paired comparison ----------------------------------
    pairs = []
    for rb in b:
        ra = min(a, key=lambda r: abs(r["model_beta"] - rb["model_beta"]))
        if abs(ra["model_beta"] - rb["model_beta"]) / rb["model_beta"] < 0.06:
            pairs.append((ra, rb))
    idx = np.arange(len(pairs))
    w = 0.36
    for k, (ra, rb) in enumerate(pairs):
        for off, r, colour in ((-w / 2, ra, "#0072B2"), (w / 2, rb, "#D55E00")):
            v = val(r)
            h = v if v is not None else CAP
            ax2.bar(k + off, max(h, 0.8), width=w, color=colour,
                    edgecolor="white", linewidth=0.8,
                    hatch=None if v is not None else "///", zorder=3)
            ax2.annotate(f"{v:g}" if v is not None else "never",
                         xy=(k + off, max(h, 0.8)), fontsize=8,
                         color=INK if v is not None else "#b3261e",
                         ha="center", va="bottom", zorder=5)
    ax2.set_yscale("log")
    ax2.set_ylim(0.8, CAP * 6)
    ax2.set_xticks(idx)
    ax2.set_xticklabels([f"model " + r"$\beta$" + f"\n{rb['model_beta']:.0f}\n"
                         f"gap {gap_pct(rb['model_beta']):+.0f}%"
                         for _, rb in pairs], fontsize=8)
    ax2.set_ylabel("trajectories to thermalization (seed)", fontsize=10, color=INK)
    ax2.set_title("(b) paired: same coupling, same coverage gap, one volume apart",
                  fontsize=10.5, loc="left", color=INK)
    ax2.grid(alpha=0.25, axis="y", which="both", color=GRID)
    handles = [plt.Rectangle((0, 0), 1, 1, color="#0072B2"),
               plt.Rectangle((0, 0), 1, 1, color="#D55E00")]
    ax2.legend(handles, ["L = 32", "L = 64"], frameon=False, fontsize=8.5,
               loc="upper left")

    for axis in (ax, ax2):
        axis.set_axisbelow(True)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)

    fig.suptitle("The coverage ordering survives the volume; the quality does not",
                 fontsize=12.5, color=INK, x=0.02, ha="left")
    fig.text(0.5, -0.04,
             "Cold and hot starts are `inf` at every L = 64 coupling in both the "
             "plain and the winding round and are omitted for legibility. The "
             "L = 64 bases were chosen by MODEL BETA so each pair differs in "
             "volume and in almost nothing else.",
             fontsize=7.5, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=342, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")
    for ra, rb in pairs:
        va, vb = val(ra), val(rb)
        print(f"  model beta {rb['model_beta']:7.2f} (gap {gap_pct(rb['model_beta']):+6.1f}%)"
              f"   L=32 {('%g' % va) if va is not None else 'inf':>5s}"
              f"   L=64 {('%g' % vb) if vb is not None else 'inf':>5s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
