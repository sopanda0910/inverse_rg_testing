"""How much closer the preconditioned chain ends up, against coupling.

ONE number per coupling instead of two. Earlier versions plotted the cold and
preconditioned distances as separate series, which meant four interleaved point
clouds per panel and asked the reader to do a paired comparison by eye.
Plotting the comparison itself halves the series and turns "better or worse"
into a position on the axis.

    improvement = max(z_cold, 1) / max(z_preconditioned, 1)

with z = |bias| / standard error at the END of the budget, on the same band for
both arms. Flooring BOTH at one -- the resolution -- is what makes this usable:

  * it is symmetric, so 1 means the two arms are equally acceptable rather than
    meaning nothing;
  * above 1 the preconditioned chain ends closer, below 1 it does not;
  * and it cannot blow up. A raw ratio of deviations was tried twice and failed
    both times, because by the end of the budget the preconditioned arm's own
    deviation is consistent with zero (z = 0.0-2.9 across the grid), so the
    denominator approaches the resolution floor and the ratio ran from 0.1 to
    120 on noise alone.

Rows are volume, columns are observable from ultraviolet to infrared and then
topology, and the two series are the two classical samplers. Keeping beta on
the axis is deliberate: where the model degrades relative to its training
coverage is one of the paper's claims, and a version of this figure that
collapsed beta into a distribution lost it.

Related: `91_money_split_figure.py` reports the COST ratio, interval over
t_therm. That one falls with volume for a structural reason -- its numerator is
built from the normalized autocorrelation and is band-independent while its
denominator is a crossing against the band -- whereas here both arms are scored
against the same band and the band cancels.

NOTE: `28_crossover_scan.py` steps the sampler BEFORE its first record, so its
record 0 is the state after one trajectory rather than the initial
configuration. Raw record-0 seed quality lives in the seed benchmark
(`08_hmc_seed_benchmark.py`), which records before stepping.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "u1_2d" / "scripts"))
from _figstyle import apply_paper_font  # noqa: E402

apply_paper_font()
sys.path.insert(0, str(ROOT))
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact  # noqa: E402

BASE = ROOT / "out/u2_2d/coverage_scan_relaxation"
# Rebound by main() from --base; the default is the grid the paper's
# current numbers were read off, so it is never changed implicitly.
_BASE = BASE
ROWS = ((("crossover", "crossover_topo"), 32),
        (("crossover_L64", "crossover_L64_topo"), 64))
OBS = (("plaquette", 1, "plaquette"),
       ("wilson_4x4", 16, r"$W(4{\times}4)$"),
       ("charge", 0, r"topology, $\langle Q^2\rangle$"))
SAMPLERS = ((0, "vs plain HMC", "#0072B2"),
            (1, "vs winding HMC", "#D55E00"))


def improvement(ckpt, stem, obs, area):
    """beta and max(z_cold,1)/max(z_pre,1) at the end of the budget."""
    f = _BASE / ckpt / f"{stem}.json"
    if not f.exists():
        return None
    betas, vals = [], []
    for r in json.loads(f.read_text(encoding="utf-8")):
        beta, L = float(r["beta"]), int(r["lattice_size"])
        sf = _BASE / ckpt / "series" / f"{stem}_beta{beta:g}.npz"
        if not sf.exists():
            continue
        z = np.load(sf)
        if f"diffusion seed__{obs}" not in z:
            continue
        if obs == "charge":
            exact = float(r["q_squared_exact"])
            src = np.asarray(z["diffusion seed__charge"], dtype=float) ** 2
        else:
            exact = (plaquette_exact(beta, L) if obs == "plaquette"
                     else wilson_loop_exact(beta, area, lattice_size=L))
            src = np.asarray(z[f"diffusion seed__{obs}"], dtype=float)
        tail = src[len(src) // 2:]
        sig = float(np.mean([t.std(ddof=1) for t in tail]))
        if not np.isfinite(sig) or sig <= 0:
            continue
        zs = {}
        for arm in ("cold start", "diffusion seed"):
            a = np.asarray(z[f"{arm}__{obs}"], dtype=float)
            if obs == "charge":
                a = a ** 2
            sem = sig / math.sqrt(a.shape[1])
            zs[arm] = abs(a[-1].mean() - exact) / sem
        betas.append(beta)
        vals.append(max(zs["cold start"], 1.0)
                    / max(zs["diffusion seed"], 1.0))
    if not betas:
        return None
    o = np.argsort(betas)
    return np.asarray(betas)[o], np.asarray(vals)[o]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(BASE),
                    help="scan directory; coverage_scan_w8 for the "
                         "W(8x8) grid")
    ap.add_argument("--out",
                    default=str(ROOT / "out/u2_2d/figures/fig66_seed_quality.png"))
    ap.add_argument("--checkpoint", default="wide_dense")
    args = ap.parse_args()
    global _BASE
    _BASE = Path(args.base)

    fig, axes = plt.subplots(2, 3, figsize=(11.4, 6.2), sharey=True,
                             sharex=True)
    for row, (stems, L) in enumerate(ROWS):
        for col, (obs, area, olabel) in enumerate(OBS):
            ax = axes[row][col]
            ax.axhspan(0.2, 1.0, color="0.93", zorder=0)
            for si, slabel, colour in SAMPLERS:
                d = improvement(args.checkpoint, stems[si], obs, area)
                if d is None:
                    continue
                b, v = d
                ax.plot(b, v, "o-", color=colour, ms=4.8, lw=1.3,
                        label=slabel, zorder=3)
            ax.axhline(1.0, color="0.35", lw=1.0, zorder=2)
            ax.set_xscale("log")
            ax.set_yscale("log")
            # Flooring both z at 1 bounds this below by ~1/z_pre_max, so the
            # decades the old limits reserved below 0.2 were always empty.
            ax.set_ylim(0.22, 22)
            ax.grid(alpha=0.2, lw=0.5)
            if row == 0:
                ax.set_title(olabel, fontsize=11)
            if col == 0:
                ax.set_ylabel(f"$L={L}$\n" "times closer at the end",
                              fontsize=10)
            if row == 1:
                ax.set_xlabel(r"$\beta$", fontsize=11)

    key = [Line2D([], [], marker="o", color=c, lw=1.3, ms=4.8, label=lbl)
           for _, lbl, c in SAMPLERS]
    fig.legend(handles=key, loc="upper center", bbox_to_anchor=(0.5, 0.945),
               ncol=2, frameon=False, fontsize=10, columnspacing=3.0)
    fig.suptitle("How much closer to exact the preconditioned chain ends  "
                 f"({args.checkpoint.replace('_', '-')} checkpoint)",
                 fontsize=11.5)
    fig.text(0.5, 0.004,
             r"$\max(z_{\rm cold},1)/\max(z_{\rm pre},1)$ at the end of each "
             "coupling's budget. Above the line the preconditioned chain is "
             "closer; in the shaded band it is not.",
             ha="center", fontsize=8.5, color="0.35")
    fig.tight_layout(rect=(0, 0.035, 1, 0.91))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")

    for stems, L in ROWS:
        for si, slabel, _ in SAMPLERS:
            for obs, area, _ in OBS:
                d = improvement(args.checkpoint, stems[si], obs, area)
                if d is None:
                    continue
                _, v = d
                print(f"  L={L:3d} {slabel:16s} {obs:11s}  "
                      f"median {np.median(v):6.2f}  range "
                      f"{v.min():5.2f}-{v.max():<6.2f} "
                      f"above 1: {int((v > 1).sum()):2d}/{len(v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
