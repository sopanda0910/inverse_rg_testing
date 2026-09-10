"""Coverage comparison drawn on the PRE-REGISTERED endpoint, for BOTH studies.

This replaces the cost-efficiency panels that `59_`/`67_` drew. Those plotted
`interval / t_therm(seed)`, and that denominator is the relaxation time shown
in `docs/u1_2d/COVERAGE_TEST_PREREG.md` to be inverted for good seeds: a seed
FAR from the exact value relaxes visibly and scores well, one ALREADY THERE
has no decay to resolve and scores badly. A figure built on it ranks
checkpoints by how much room their seeds left to relax.

What is plotted instead is the endpoint the coverage claim is about, and the
same one `84_raw_seed_quality.py` tests:

    Z = max over {plaquette, W(2x2), W(4x4)} of |mean - exact| / SEM

at record 0 of the saved series -- the raw diffusion seed, before any
trajectory. Lower is better, so unlike the cost-efficiency panels these axes
are INVERTED relative to "good is up"; the axis is labelled to say so and
drawn on a log scale, since the checkpoints separate by more than a decade.

One script for both theories, for the same reason `84_` is one script: u1 and
u2 are evaluated by the same method unless a difference is justified in
writing (CLAUDE.md).

    python u2_2d/scripts/85_coverage_seed_quality_figure.py --theory u1
    python u2_2d/scripts/85_coverage_seed_quality_figure.py --theory u2
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "rsq", ROOT / "u2_2d" / "scripts" / "84_raw_seed_quality.py")
rsq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rsq)

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"

U1_ARMS = [
    ("deployed", "out/u1_2d/coverage_scan/wide2000_L16target/deployed",
     "#0072B2", 60.0, r"deployed  ($\beta_{max}=60$)"),
    ("wide2000", "out/u1_2d/coverage_scan/wide2000_L16target/wide2000",
     "#009E73", 2000.0, r"wide2000  ($\beta_{max}=2000$)"),
    # The FINAL sectorfix build. The earlier sector-empty build is not
    # published -- it is a debugging artifact, not a second arm.
    ("wide2000_dense", "out/u1_2d/coverage_scan/wide2000_dense_sectorfix_L16target",
     "#D55E00", 2000.0, r"wide2000_dense  (+30 density rungs)"),
]

# The eight PRE-REGISTERED confirmatory couplings of
# docs/u1_2d/COVERAGE_TEST_PREREG.md. They were placed by inverting the ladder
# relation to fall in the GAPS between wide2000's training rungs, and were
# scored only after the analysis plan was written down; the other seven were
# run first and the endpoint was chosen after inspecting them. They therefore
# carry the coverage claim on their own and are drawn as open markers, so a
# reader can check the confirmatory subgroup without taking the text's word
# for which points it is.
U1_OFF_RUNG = {250.0, 350.0, 470.0, 650.0, 870.0, 1225.0, 1750.0, 2600.0}

# Ceilings are in MODEL beta, the axis these are plotted against, so they are
# the minimum-KL projection of each checkpoint's largest RAW training beta
# (227.3 -> 56.8, 416.5 -> 104.1, 2000 -> 500). Quoting a raw beta here reads as
# a model beta and overstates the wide checkpoints' reach by a factor of four.
U2_ARMS = [
    ("cov60", "#CC79A7", 56.831, r"cov60  (model $\beta_{max}\approx57$)"),
    ("default", "#0072B2", 104.132, r"default  ($\approx104$)"),
    ("wide", "#009E73", 500.0, r"wide  ($\approx500$)"),
    ("wide_dense", "#D55E00", 500.0, r"wide_dense  ($\approx500$, $+31$ density rungs)"),
]


def load(theory: str, L: int | None = None, metric: str = "Z"):
    """Return [(label, colour, ceiling, betas, values)], sorted by beta.

    `metric` selects the endpoint: "Z" is the worst-case standardized
    deviation of the raw seed and "PPM" the same in relative deviation. Both
    come from 84_raw_seed_quality, which computes them on the same record.
    """
    out = []
    if theory == "u1":
        for tag, path, colour, ceil, label in U1_ARMS:
            d = rsq.load_u1(Path(path))
            if not d:
                print(f"  WARNING: no series for {tag} at {path}")
                continue
            ks = sorted(d, key=lambda k: d[k]["beta"])
            out.append((label, colour, ceil,
                        np.array([d[k]["beta"] for k in ks]),
                        np.array([d[k][metric] for k in ks])))
    else:
        from u2_2d.lgt.exact import matched_u1_beta
        base = ROOT / "out/u2_2d/coverage_scan_relaxation"
        for tag, colour, ceil, label in U2_ARMS:
            d = rsq.load_u2(tag, base)
            if not d:
                print(f"  WARNING: no series for {tag}")
                continue
            # ONE VOLUME PER PANEL, AND THE TWO HMC ROUNDS COLLAPSED.
            # The 44 paired couplings pool two volumes and two rounds (plain /
            # topological), so several share a model beta. Drawing a line
            # through them connects unrelated points and jumps vertically at a
            # single coupling -- the first version of this figure did exactly
            # that and was unreadable. x axis is MODEL beta because that is
            # what training coverage is defined in, so a ceiling is one
            # vertical line rather than one per volume.
            grouped: dict[float, list[float]] = {}
            for v in d.values():
                if v["L"] != L:
                    continue
                grouped.setdefault(round(float(matched_u1_beta(v["beta"])), 4),
                                   []).append(v[metric])
            if not grouped:
                print(f"  WARNING: {tag} has no L={L} records")
                continue
            xs = sorted(grouped)
            out.append((label, colour, ceil, np.array(xs),
                        np.array([float(np.median(grouped[x])) for x in xs])))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theory", choices=("u1", "u2"), required=True)
    ap.add_argument("--L", type=int, default=32,
                    help="u2 only: which fine volume to draw (32 or 64). "
                         "One volume per panel -- see load().")
    ap.add_argument("--metric", choices=("Z", "PPM"), default="PPM",
                    help="endpoint: relative deviation in ppm (the paper's "
                         "convention) or the standardized version")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    arms = load(args.theory, args.L, metric=args.metric)
    if not arms:
        print("no data found")
        return 1

    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    for label, colour, ceil, betas, zs in arms:
        ax.plot(betas, zs, "-", color=colour, lw=1.6, label=label, zorder=3)
        # Filled = exploratory, open = the pre-registered confirmatory subgroup.
        off = np.array([round(float(b), 3) in U1_OFF_RUNG for b in betas]) \
            if args.theory == "u1" else np.zeros(len(betas), bool)
        ax.plot(betas[~off], zs[~off], "o", color=colour, ms=5.0, zorder=4,
                markeredgecolor="white", markeredgewidth=0.6)
        ax.plot(betas[off], zs[off], "o", color="white", ms=6.0, zorder=4,
                markeredgecolor=colour, markeredgewidth=1.8)
        if np.isfinite(ceil) and betas.min() <= ceil <= betas.max() * 1.05:
            ax.axvline(ceil, color=colour, ls=":", lw=1.2, alpha=0.75, zorder=1)

    if args.metric == "Z":
        ax.axhspan(0, 2, color="#2ca02c", alpha=0.07, zorder=0)
        ax.axhline(2, color="#2ca02c", ls="--", lw=1.0, alpha=0.65, zorder=2)
        ax.text(0.995, 2, "  indistinguishable from exact  ", color="#2ca02c",
                fontsize=8, va="bottom", ha="right",
                transform=ax.get_yaxis_transform())

    ax.set_xscale("log")
    ax.set_yscale("log")
    xlabel = (r"fine coupling $\beta_f$   ($L=8\to16$)" if args.theory == "u1"
              else r"model coupling $\beta$")
    ax.set_xlabel(xlabel, fontsize=10, color=INK)
    ax.set_ylabel("raw lift deviation from exact (ppm)\n(lower is better)"
                  if args.metric == "PPM" else
                  r"raw lift $\max|z|$ before any trajectory   (lower is better)",
                  fontsize=10, color=INK)
    ax.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fmt = FuncFormatter(lambda v, _: f"{v:g}")
    ax.xaxis.set_major_formatter(fmt)
    ax.yaxis.set_major_formatter(fmt)
    # A bare log locator labels only the decades, and the curves that matter
    # here live BETWEEN them -- u1's `deployed` sits at Z ~ 40-90, so with
    # decade-only ticks its value cannot be read off the axis at all. Label the
    # 1-2-5 subdivisions over whatever range the data actually occupies.
    ax.yaxis.set_minor_formatter(FuncFormatter(
        lambda v, _: f"{v:g}" if any(abs(v / (m * 10.0 ** e) - 1) < 1e-9
                                     for m in (2, 5) for e in range(-2, 6))
        else ""))
    ax.tick_params(axis="y", which="minor", labelsize=8, colors=MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    handles, labels = ax.get_legend_handles_labels()
    if args.theory == "u1":
        handles.append(plt.Line2D([], [], ls="none", marker="o", ms=6,
                                  markerfacecolor="white", markeredgecolor=MUTED,
                                  markeredgewidth=1.8))
        labels.append("open: pre-registered off-rung coupling")
    ax.legend(handles, labels, frameon=False, fontsize=9, loc="lower left")
    # Only u2 pools two HMC rounds per coupling (see load()); saying so on the
    # u1 panel, which has one round, would be simply false.
    if args.theory == "u1":
        sub = ("Dotted line marks wide2000's training ceiling; every coupling "
               "shown is past deployed's own ceiling of 60")
    else:
        sub = (f"$L={args.L}$.  Dotted vertical lines mark each checkpoint's own "
               "training ceiling (wide/wide_dense's lies off-scale at "
               r"$\approx2000$); the two HMC rounds are collapsed to their median")
    ax.set_title(sub, fontsize=9, color=MUTED, loc="left", pad=8, wrap=True)
    fig.tight_layout()

    if args.out:
        out = Path(args.out)
    elif args.theory == "u1":
        out = ROOT / "out/u1_2d/figures/fig67_coverage_comparison.png"
    else:
        out = ROOT / ("out/u2_2d/figures/fig59_coverage_comparison.png" if args.L == 32
                      else "out/u2_2d/figures/fig59b_coverage_comparison_L64.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white")
    print(f"wrote {out}")
    for label, _, _, betas, zs in arms:
        print(f"  {label:<44} n={len(zs):>3}  median Z={np.median(zs):8.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
