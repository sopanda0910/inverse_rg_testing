"""Figure 30 -- what multiple lifts cost, in both studies.

Reads BOTH packages' `60_/45_multi_lift_compounding.py` output, because the
result is a comparison between them: `out/u1_2d/multi_lift_*` and
`out/u2_2d/multi_lift_*`.

THREE THINGS THE FIGURE HAS TO SAY, and only the third was expected.

(a) ERROR DOES NOT COMPOUND. Three lifts to a fixed endpoint land within
    0.84-1.02x of the one-lift error, in both theories, at an in-coverage
    endpoint and at one past the training ceiling, with and without
    rethermalization between rungs. Eight independent cells, no trend.

(b) THE ERROR IS INJECTED BY THE LAST LIFT. The per-rung trace of the 3-lift
    arm shows the intermediate rungs landing at |z| of order 1-16 and the final
    rung at 150-250. The intermediate rungs sit deep inside training coverage;
    the endpoint does not. So what sets the endpoint's accuracy is the FINAL
    rung's distance from coverage, not the number of rungs climbed to reach it.
    That is the answer to "does laddering extend generalization": it does not
    extend the COUPLING reach, because every lift multiplies beta by ~4 and the
    last one always lands at the same place. What the ladder buys is VOLUME.

(c) THE LIFT PRESERVES TOPOLOGY EXACTLY; THE RETHERMALIZATION BETWEEN RUNGS
    DOES NOT. With no intermediate rethermalization, 100% of configurations
    keep their starting charge in all 8 cells -- 1, 2 and 3 lifts, both
    theories, both chains. Switch the ladder's own 10 sweeps back on and the
    3-lift arm loses charge wherever an intermediate rung is weakly coupled
    enough for local moves to shift it: u1 keeps only 33.6% at an L = 16 rung
    of beta = 3.87 and 81.2% at beta = 5.24, while u2 -- whose intermediate
    rungs are far stiffer -- keeps 98.4% and 100%.

    This is NOT corruption. `<Q^2>` moves TOWARD the exact value when it
    happens (u1 ceiling chain: 1.633 -> 1.539 against an exact 1.386), because
    a weakly coupled rung is one where local updates sample topology correctly.
    The precise claim is therefore: the ladder RE-SAMPLES topology at every
    rung where that is still valid, and transports it unchanged once the
    coupling is stiff enough that it is not. "Drawn at the base and carried to
    the top" is exactly true only with intermediate rethermalization off.

    python u2_2d/scripts/46_multi_lift_figure.py
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
U1C, U2C = "#0072B2", "#D55E00"

CASES = [
    ("u1", "in coverage", "out/u1_2d/multi_lift_incov", U1C, "-"),
    ("u1", "past ceiling", "out/u1_2d/multi_lift_ceiling", U1C, "--"),
    ("u2", "in coverage", "out/u2_2d/multi_lift_incov", U2C, "-"),
    ("u2", "past ceiling", "out/u2_2d/multi_lift_ceiling", U2C, "--"),
]


def load(base, r):
    p = Path(base) / f"multi_lift_r{r}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="out/u2_2d/figures/fig30_multi_lift.png")
    args = ap.parse_args()

    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.13))

    # ---- (a) no compounding ------------------------------------------------
    ax = axes[0]
    for theory, label, base, colour, ls in CASES:
        d = load(base, 10)
        if not d:
            continue
        n = [a["n_lifts"] for a in d["arms"]]
        z = [abs(a["final_raw"]["z_W1x1"]) for a in d["arms"]]
        ax.plot(n, z, "o" + ls, color=colour, lw=1.9, ms=7,
                markeredgecolor="white", markeredgewidth=0.7,
                label=f"{theory}, {label}")
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("number of lifts to the same endpoint", fontsize=10, color=INK)
    ax.set_ylabel(r"$|z|$ of the raw lift, $W(1{\times}1)$", fontsize=10, color=INK)
    ax.set_title("(a) error does not compound", fontsize=10.5, loc="left",
                 color=INK)
    ax.set_ylim(0, 320)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.annotate("same endpoint reached three ways;\nflat means the rung count "
                "is not a cost", xy=(0.97, 0.98), xycoords="axes fraction",
                fontsize=7.5, color=MUTED, ha="right", va="top")

    # ---- (b) the error is injected by the LAST lift -------------------------
    ax = axes[1]
    for theory, label, base, colour, ls in CASES:
        d = load(base, 10)
        if not d:
            continue
        arm = [a for a in d["arms"] if a["n_lifts"] == 3]
        if not arm:
            continue
        pr = arm[0]["per_rung"]
        ax.plot(range(1, len(pr) + 1), [abs(p["raw"]["z_W1x1"]) for p in pr],
                "o" + ls, color=colour, lw=1.9, ms=7,
                markeredgecolor="white", markeredgewidth=0.7,
                label=f"{theory}, {label}")
    ax.set_yscale("log")
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("rung of the 3-lift ladder", fontsize=10, color=INK)
    ax.set_ylabel(r"$|z|$ of the raw lift at that rung", fontsize=10, color=INK)
    ax.set_title("(b) injected by the final lift, not accumulated",
                 fontsize=10.5, loc="left", color=INK)
    ax.axhline(2.0, color=INK, lw=1.1, ls=(0, (4, 2)))
    ax.annotate(r"$|z| = 2$", xy=(1.02, 2.3), fontsize=7.5, color=MUTED)
    ax.annotate("intermediate rungs sit inside\ntraining coverage; "
                "the endpoint does not", xy=(0.03, 0.94),
                xycoords="axes fraction", fontsize=7.5, color=MUTED, va="top")

    # ---- (c) topology: the lift is exact, the tail is not -------------------
    ax = axes[2]
    width = 0.35
    xs = np.arange(len(CASES))
    for i, r in enumerate((0, 10)):
        vals = []
        for theory, label, base, colour, ls in CASES:
            d = load(base, r)
            arm = [a for a in d["arms"] if a["n_lifts"] == 3] if d else []
            vals.append(100 * arm[0]["charge_match_fraction"] if arm else np.nan)
        ax.bar(xs + (i - 0.5) * width, vals, width,
               color=("#2e7d32" if r == 0 else "#b3202b"),
               edgecolor="white", linewidth=0.8,
               label=("no retherm between rungs" if r == 0
                      else "10 retherm sweeps between rungs"))
        for x, v in zip(xs + (i - 0.5) * width, vals):
            if np.isfinite(v):
                ax.text(x, v + 1.5, f"{v:.1f}", ha="center", fontsize=7.5,
                        color=INK)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{t}\n{l}" for t, l, *_ in CASES], fontsize=8)
    ax.set_ylim(0, 168)
    ax.set_ylabel("% of configurations keeping their starting charge",
                  fontsize=9.5, color=INK)
    ax.set_title("(c) the LIFT transports Q exactly; the TAIL re-samples it",
                 fontsize=10.5, loc="left", color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper left",
              bbox_to_anchor=(0.0, 0.86))
    ax.annotate("3-lift arm. Loss tracks how weakly coupled the intermediate\n"
                "rung is, and moves " r"$\langle Q^2\rangle$" " TOWARD exact "
                "-- re-sampling where\nthat is still valid, not corruption.",
                xy=(0.02, 0.995), xycoords="axes fraction", fontsize=7.2,
                color=MUTED, ha="left", va="top")

    for a in axes:
        a.grid(alpha=0.25, color=GRID)
        a.set_axisbelow(True)
        for side in ("top", "right"):
            a.spines[side].set_visible(False)

    fig.suptitle("Climbing the ladder: the rung count is free, the final rung "
                 "sets the accuracy, and only the tail moves topology",
                 fontsize=12.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=441, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
