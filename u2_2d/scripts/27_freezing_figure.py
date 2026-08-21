"""Figure 19 -- what each sampler can and cannot reach at a frozen coupling.

The u2 analogue of u1's `31_frozen_traces.png`, and the figure that states this
study's premise: at L = 64, beta = 416.524 a standard HMC chain does not change
topological sector at all, so the question "is a diffusion configuration a good
seed?" is being asked exactly where the classical sampler has failed.

THREE SAMPLERS, NOT TWO. It is tempting to draw plain HMC against the diffusion
seed and stop. That overstates the case, and did so in this study's own writing
until 2026-08-20:

  plain HMC        0 sector changes. Completely frozen.
  + winding dQ=2   mobile in charge, but CANNOT change parity by construction,
                   so it reaches even sectors and stops -- 0 parity flips, and
                   it covers 0.507 of the exact P(Q) no matter how long it runs.
  + winding dQ=1   the marginal odd move (docs/INSTANTON.md). Genuinely ergodic:
                   2587 parity flips, full coverage. THIS is the honest baseline.

Against `winding_odd` the diffusion seed's advantage is no longer "the classical
arm cannot get there". It is that the classical arm must MANUFACTURE the sectors
the seed arrives holding -- 1100 s and thousands of accepted moves, against a
seed that is already correct at t = 0 having made no winding move at all.

    python u2_2d/scripts/27_freezing_figure.py
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OUT = Path("out/u2_2d")

# Okabe-Ito, colourblind-safe; every series also gets a distinct dash pattern so
# identity never rests on hue alone.
STYLE = {
    "B_cold_start": ("plain HMC (cold)", "#D55E00", (0, (5, 2)), 1.9),
    "D_cold_plus_winding": (r"+ winding $\Delta Q=2$", "#0072B2", (0, (1, 1.5)), 1.9),
    "G_cold_plus_odd_winding": (r"+ winding $\Delta Q=1$ (marginal)", "#009E73", "-", 1.9),
    "A_diffusion_seed": ("diffusion seed", "#CC79A7", "-", 2.6),
}
ORDER = ["B_cold_start", "D_cold_plus_winding", "G_cold_plus_odd_winding",
         "A_diffusion_seed"]

# Two-line tick labels for panel (c); the full legend names collide there.
SHORT = {
    "B_cold_start": "plain\nHMC",
    "D_cold_plus_winding": "+ wind\n$\\Delta Q\\!=\\!2$",
    "G_cold_plus_odd_winding": "+ wind\n$\\Delta Q\\!=\\!1$",
    "A_diffusion_seed": "diffusion\nseed",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", default="out/u2_2d/seed_benchmark/seed_benchmark.json")
    parser.add_argument("--out", default="out/u2_2d/figures/fig19_freezing.png")
    args = parser.parse_args()

    bench = json.loads(Path(args.bench).read_text(encoding="utf-8"))
    arms = {a["arm"]: a for a in bench["arms"]}
    # The aggregated summary keeps only per-trajectory MEANS; the per-arm files
    # keep the per-chain charge vector, which is what a trace figure needs.
    # Merge the richer history in where it exists.
    bench_dir = Path(args.bench).parent
    for name in list(arms):
        rich = bench_dir / f"arm_{name}.json"
        if rich.exists():
            data = json.loads(rich.read_text(encoding="utf-8"))
            if data.get("history") and "charge" in data["history"][0]:
                arms[name] = {**arms[name], "history": data["history"]}
    beta, size = bench["beta"], bench["lattice_size"]
    q2_exact = arms[ORDER[0]]["topology"]["q_squared_exact"]

    fig, axes = plt.subplots(1, 3, figsize=(14.4, 4.4))

    # (a) Q of a few individual chains -- the trace that shows freezing directly.
    ax = axes[0]
    for name in ORDER:
        arm = arms.get(name)
        if not arm:
            continue
        label, colour, ls, lw = STYLE[name]
        traj = [h["trajectory"] for h in arm["history"]]
        q = np.array([h["charge"] for h in arm["history"]])
        for chain in range(min(4, q.shape[1])):
            ax.plot(traj, q[:, chain], ls=ls, color=colour, lw=lw * 0.65,
                    alpha=0.85, label=label if chain == 0 else None)
    ax.set_ylabel("topological charge $Q$ (4 chains per arm)")
    ax.set_title("(a) two flat lines, opposite reasons", fontsize=10)
    # BOTH plain HMC and the diffusion seed are flat in this panel, and they are
    # flat for opposite reasons: plain HMC is stuck at Q = 0, which is the wrong
    # distribution, while the seed was already spread over the right sectors at
    # t = 0 and has no need to move. A reader who misses that misreads the
    # figure, so it is said on the axes rather than left to the caption.
    ax.annotate("plain HMC: stuck at $Q=0$\n(wrong distribution)",
                xy=(0.03, 0.04), xycoords="axes fraction", fontsize=7.5,
                color="#D55E00", va="bottom")
    ax.annotate("diffusion seed: flat because it\nstarted in the right sectors",
                xy=(0.97, 0.96), xycoords="axes fraction", fontsize=7.5,
                color="#CC79A7", ha="right", va="top")

    # (b) <Q^2> against the closed form.
    ax = axes[1]
    for name in ORDER:
        arm = arms.get(name)
        if not arm:
            continue
        label, colour, ls, lw = STYLE[name]
        traj = [h["trajectory"] for h in arm["history"]]
        q2 = [float(np.mean(np.asarray(h["charge"]) ** 2)) for h in arm["history"]]
        ax.plot(traj, q2, ls=ls, color=colour, lw=lw, label=label)
    ax.axhline(q2_exact, color="k", lw=1.1, ls=(0, (6, 3)), label="exact", zorder=1)
    ax.set_ylabel(r"$\langle Q^2 \rangle$")
    ax.set_title(r"(b) and so $\langle Q^2 \rangle$ never leaves zero", fontsize=10)

    # (c) The bar that says what each sampler can reach AT ALL. Coverage alone is
    # misleading -- the hot arm "covers" 1.000 while carrying <Q^2> = 109 -- so
    # parity flips are drawn beside it, which is the quantity that separates the
    # two winding moves.
    ax = axes[2]
    names, cover, flips, colours = [], [], [], []
    for name in ORDER:
        arm = arms.get(name)
        if not arm:
            continue
        label, colour, _, _ = STYLE[name]
        names.append(SHORT.get(name, label))
        cover.append(arm["topology"]["exact_probability_covered"])
        qs = np.array([h["charge"] for h in arm["history"]]).round().astype(int)
        flips.append(int((np.diff(qs % 2, axis=0) != 0).sum()))
        colours.append(colour)
    x = np.arange(len(names))
    ax.bar(x, cover, 0.6, color=colours, alpha=0.9)
    for xi, (c, f) in enumerate(zip(cover, flips)):
        ax.annotate(f"{c:.3f}\n{f} parity\nflips", (xi, c), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=7.5)
    ax.axhline(1.0, color="k", lw=1.0, ls=(0, (6, 3)))
    ax.set_ylim(0, 1.32)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("fraction of exact $P(Q)$ reached")
    ax.set_title("(c) what each sampler can reach at all", fontsize=10)

    for ax in axes[:2]:
        ax.set_xlabel("HMC trajectory")
        ax.legend(frameon=False, fontsize=8)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.suptitle(f"The regime this method targets: $L={size}$, "
                 rf"$\beta={beta:g}$ -- standard HMC is frozen", y=1.02)
    fig.tight_layout()
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")

    for name in ORDER:
        arm = arms.get(name)
        if arm:
            qs = np.array([h["charge"] for h in arm["history"]]).round().astype(int)
            print(f"  {name:28s} <Q^2>={arm['topology']['q_squared']:.3f} "
                  f"cover={arm['topology']['exact_probability_covered']:.3f} "
                  f"parity_flips={int((np.diff(qs % 2, axis=0) != 0).sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
