"""Figure 26 -- topological transport is exact, configuration by configuration.

The paper's section 8 rests on one structural claim: because `det` is a
homomorphism, the coarse determinant plaquette is the exact wrapped sum of its
four fine children, so the coarse topological charge can be IMPOSED on the fine
configuration and the generative model cannot alter it. Everything else in the
section -- that the seed arrives carrying odd sectors a frozen HMC chain can
never manufacture -- follows from it.

It was asserted throughout the codebase and checked only on the BLOCKING map
(`09_verify_identities.py`). `36_transport_check.py` checks it on the GENERATIVE
path, which is what actually ships, and this draws the result.

WHAT MAKES THE FIGURE WORTH A PANEL rather than a sentence: the match rate is
100% at model beta 327, more than three times past the highest training rung
(104.13), where the score net's own output is so far out of coverage that the
seed does not thermalize on any local observable. Transport is not something the
network learned and can therefore lose -- it is a property of the blocking map.
That is exactly the distinction a referee needs, and it is visible only when the
axis runs past where the model works.

    python u2_2d/scripts/37_transport_figure.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
TOP_RUNG = 104.132


def load(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--l16", default="out/u2_2d/transport_check/L16/transport_check.json")
    ap.add_argument("--l32", default="out/u2_2d/transport_check/L32/transport_check.json")
    ap.add_argument("--out", default="out/u2_2d/figures/fig26_transport_exactness.png")
    args = ap.parse_args()

    series = [("L 16 " + chr(0x2192) + " 32", load(Path(args.l16)), "#0072B2", "o"),
              ("L 32 " + chr(0x2192) + " 64", load(Path(args.l32)), "#D55E00", "s")]
    if not any(rows for _, rows, _, _ in series):
        print("no transport_check.json found -- run 36_transport_check.py first")
        return 1

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.4))

    # ---- panel (a): match fraction vs model beta -----------------------------
    for label, rows, colour, marker in series:
        if not rows:
            continue
        x = [r["model_beta"] for r in rows]
        y = [100.0 * r["match_fraction"] for r in rows]
        ax.plot(x, y, marker + "-", color=colour, lw=2.0, ms=8,
                markeredgecolor="white", markeredgewidth=0.8, zorder=4,
                label=f"{label}  ({rows[0]['n_configs']} configs each)")
    ax.axhline(100.0, color=MUTED, lw=1.0, ls=(0, (4, 3)), zorder=2)
    ax.axvline(TOP_RUNG, color="#7A4FA3", lw=1.2, ls=(0, (1, 2)), zorder=3)
    ax.annotate("highest training rung\n(model " + r"$\beta$" + f" = {TOP_RUNG:.0f})",
                xy=(TOP_RUNG, 0.30), xycoords=("data", "axes fraction"),
                fontsize=7.5, color="#7A4FA3", ha="right", rotation=90)
    xmax = max(r["model_beta"] for _, rows, _, _ in series for r in rows)
    ax.axvspan(TOP_RUNG, xmax * 1.4, color="#7A4FA3", alpha=0.07, zorder=1)
    ax.annotate("the MODEL fails here;\ntransport does not",
                xy=(0.97, 0.16), xycoords="axes fraction", fontsize=8,
                color="#7A4FA3", ha="right", style="italic")
    ax.set_xscale("log")
    ax.set_xlim(right=xmax * 1.4)
    ax.set_ylim(0, 108)
    ax.set_xlabel(r"model $\beta$ of the fine rung", fontsize=10, color=INK)
    ax.set_ylabel("configurations with fine Q = coarse Q  (%)", fontsize=10,
                  color=INK)
    ax.set_title("(a) transport is exact, config by config", fontsize=10.5,
                 loc="left", color=INK)
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.grid(alpha=0.25, which="both", color=GRID)

    # ---- panel (b): coarse vs fine <Q^2>, the same statement as a scatter ----
    lo, hi = 1e9, 0.0
    for label, rows, colour, marker in series:
        if not rows:
            continue
        xc = [r["q_squared_coarse"] for r in rows]
        yf = [r["q_squared_fine"] for r in rows]
        ax2.plot(xc, yf, marker, color=colour, ms=9, markeredgecolor="white",
                 markeredgewidth=0.8, zorder=4, label=label)
        vals = [v for v in xc + yf if v > 0]
        if vals:
            lo, hi = min(lo, min(vals)), max(hi, max(vals))
    ax2.plot([lo * 0.6, hi * 1.6], [lo * 0.6, hi * 1.6], color=MUTED, lw=1.0,
             ls=(0, (4, 3)), zorder=2, label="y = x")
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel(r"coarse $\langle Q^2 \rangle$", fontsize=10, color=INK)
    ax2.set_ylabel(r"fine $\langle Q^2 \rangle$ after the lift", fontsize=10,
                   color=INK)
    ax2.set_title("(b) and not merely on average", fontsize=10.5, loc="left",
                  color=INK)
    ax2.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax2.grid(alpha=0.25, which="both", color=GRID)

    for a in (ax, ax2):
        a.set_axisbelow(True)
        for side in ("top", "right"):
            a.spines[side].set_visible(False)

    fig.suptitle("Topology is transported, not modelled", fontsize=12.5,
                 color=INK, x=0.02, ha="left")
    fig.text(0.5, -0.02,
             "The score network generates the determinant phase only; the coarse "
             "charge is imposed on the fine configuration and the lift cannot "
             "alter it. This is why a seed can carry a P(Q) sampled at a "
             "coupling where HMC is ergodic into one where it is frozen.",
             fontsize=7.5, color=MUTED, ha="center")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)

    n = sum(len(rows) for _, rows, _, _ in series)
    worst = min((r["match_fraction"] for _, rows, _, _ in series for r in rows),
                default=0.0)
    print(f"wrote {dest}")
    print(f"{n} couplings, worst match fraction {100*worst:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
