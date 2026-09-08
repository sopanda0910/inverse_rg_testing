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

U2_ARMS = [
    ("cov60", "#CC79A7", 60.0, r"cov60  (model $\beta_{max}\approx60$)"),
    ("default", "#0072B2", 104.132, r"default  ($\approx104$)"),
    ("wide", "#009E73", 2000.0, r"wide  ($\approx2000$)"),
    ("wide_dense", "#D55E00", 2000.0, r"wide_dense  (+31 density rungs)"),
]


def load(theory: str, L: int | None = None):
    """Return [(label, colour, ceiling, betas, Zs)], sorted by beta."""
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
                        np.array([d[k]["Z"] for k in ks])))
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
                                   []).append(v["Z"])
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
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    arms = load(args.theory, args.L)
    if not arms:
        print("no data found")
        return 1

    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    for label, colour, ceil, betas, zs in arms:
        ax.plot(betas, zs, "-o", color=colour, ms=4.5, lw=1.6, label=label,
                markeredgecolor="white", markeredgewidth=0.6, zorder=3)
        if np.isfinite(ceil) and betas.min() <= ceil <= betas.max() * 1.05:
            ax.axvline(ceil, color=colour, ls=":", lw=1.2, alpha=0.75, zorder=1)

    ax.axhspan(0, 2, color="#2ca02c", alpha=0.07, zorder=0)
    ax.axhline(2, color="#2ca02c", ls="--", lw=1.0, alpha=0.65, zorder=2)
    ax.text(0.995, 2, "  seed indistinguishable from exact  ", color="#2ca02c",
            fontsize=8, va="bottom", ha="right", transform=ax.get_yaxis_transform())

    ax.set_xscale("log")
    ax.set_yscale("log")
    xlabel = (r"fine coupling $\beta_f$   ($L=8\to16$)" if args.theory == "u1"
              else r"model coupling $\beta$")
    ax.set_xlabel(xlabel, fontsize=10, color=INK)
    ax.set_ylabel(r"raw seed $Z=\max|z|$ at record 0   (lower is better)",
                  fontsize=10, color=INK)
    ax.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fmt = FuncFormatter(lambda v, _: f"{v:g}")
    ax.xaxis.set_major_formatter(fmt)
    ax.yaxis.set_major_formatter(fmt)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    vol = "" if args.theory == "u1" else f"$L={args.L}$.  "
    ax.set_title(vol + "Dotted vertical lines mark each checkpoint's own "
                 "training ceiling; the two HMC rounds are collapsed to their median",
                 fontsize=9, color=MUTED, loc="left", pad=8)
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
