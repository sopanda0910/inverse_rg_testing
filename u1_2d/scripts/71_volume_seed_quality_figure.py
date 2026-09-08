"""Does the diffusion seed degrade with VOLUME? Scored on the endpoint of record.

Replaces the `t_therm` panels of `51_volume_scan_figure.py` (fig30). Those were
drawn with the superseded discrete threshold-crossing estimator, and more
importantly `t_therm` is not a seed-quality measure at all -- see
`docs/u1_2d/COVERAGE_TEST_PREREG.md` and the paper's
\\S relaxation-correction: a seed already at the target has no transient to
resolve, so the fit reports failure exactly when the seed is best.

What is plotted instead is the pre-registered endpoint, at record 0 of the
saved series (the raw seed, before any trajectory), over
{plaquette, W(2x2), W(4x4)} against the closed form:

    Z   = max |mean - exact| / SEM        PPM = max |mean - exact| / |exact| * 1e6

and the decomposition that explains the whole effect. Fixed beta_f = 14.1464,
three volumes (L = 32 / 64 / 128, a 16x range in sites), one lift each.

THE POINT, and it is the same z-vs-ratio trap this project has hit repeatedly:
the seed's per-site bias is FLAT in volume while the ensemble's SEM FALLS,
because the per-chain spatial mean self-averages and the chain count differs
per volume. A volume-independent seed therefore shows a GROWING z and a
growing t_therm while nothing about its quality has changed. Panel (b) draws
the two factors separately so the reader can see which one moves.

    python u1_2d/scripts/71_volume_seed_quality_figure.py
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from u1_2d.lgt import exact

SCAN = ROOT / "out/u1_2d/thermalization_volume"
OBS = ("plaquette", "wilson_2x2", "wilson_4x4")
AREA = {"plaquette": 1, "wilson_2x2": 4, "wilson_4x4": 16}
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
CZ, CP, CBIAS, CSEM = "#D55E00", "#0072B2", "#009E73", "#CC79A7"


def targets(beta: float, size: int) -> dict[str, float]:
    return {n: (exact.plaquette_exact(beta, "wilson", size) if n == "plaquette"
                else exact.wilson_loop_exact(beta, AREA[n], "wilson", size))
            for n in OBS}


def collect() -> list[dict]:
    rows = []
    for sf in sorted(glob.glob(str(SCAN / "*" / "*_summary.json"))):
        summ = json.loads(Path(sf).read_text(encoding="utf-8"))
        nf = sf.replace("_summary.json", "_series.npz")
        if not Path(nf).exists():
            continue
        d = np.load(nf, allow_pickle=True)
        L, beta = int(summ["lattice_size"]), float(summ["beta"])
        tg = targets(beta, L)
        zs, ppms, detail = [], [], {}
        for n in OBS:
            key = f"diffusion seed|{n}"
            if key not in d.files:
                continue
            s = np.asarray(d[key], dtype=np.float64)[0]          # record 0
            sem = s.std(ddof=1) / math.sqrt(len(s))
            bias = abs(float(s.mean()) - tg[n])
            zs.append(bias / sem if sem > 0 else float("inf"))
            ppms.append(bias / abs(tg[n]) * 1e6)
            if n == "plaquette":
                detail = dict(bias=bias, sem=sem, nchains=len(s))
        if not zs:
            continue
        rows.append(dict(L=L, beta=beta, V=2 * L * L, Z=max(zs), PPM=max(ppms), **detail))
    return sorted(rows, key=lambda r: r["L"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out/u1_2d/figures/fig71_volume_seed_quality.png"))
    args = ap.parse_args()

    rows = collect()
    if len(rows) < 2:
        print(f"need >=2 volumes, found {len(rows)}")
        return 1
    Ls = [r["L"] for r in rows]
    x = np.arange(len(rows))

    fig, (axa, axb) = plt.subplots(1, 2, figsize=(11.0, 4.3))

    # (a) everything relative to the smallest volume, on one axis
    z0 = rows[0]["Z"]; b0 = rows[0]["bias"]; s0 = rows[0]["sem"]
    axa.plot(x, [r["Z"] / z0 for r in rows], "-o", color=CZ, lw=2.0, ms=7,
             markeredgecolor="white", label=r"$Z=\max|z|$  (grows)")
    axa.plot(x, [r["bias"] / b0 for r in rows], "-o", color=CBIAS, lw=2.0, ms=7,
             markeredgecolor="white", label="|bias| of plaquette  (flat)")
    axa.plot(x, [r["sem"] / s0 for r in rows], "-s", color=CSEM, lw=2.0, ms=6,
             markeredgecolor="white", label="SEM of plaquette  (falls)")
    axa.axhline(1.0, color=MUTED, ls=":", lw=1.0)
    axa.set_yscale("log")
    axa.set_ylabel(r"change relative to $L=32$", fontsize=10)
    axa.legend(frameon=False, fontsize=9, loc="center left")
    axa.set_title(r"(a) $Z$ grows only because its denominator shrinks",
                  fontsize=10, color=INK, loc="left")

    # (b) why t_therm and z grow anyway
    axb.plot(x, [r["bias"] * 1e6 for r in rows], "-o", color=CBIAS, lw=1.8, ms=7,
             markeredgecolor="white", label=r"|bias| of plaquette (ppm of exact)")
    axb.plot(x, [r["sem"] * 1e6 for r in rows], "-s", color=CSEM, lw=1.8, ms=6,
             markeredgecolor="white", label="SEM of plaquette (same units)")
    axb.set_yscale("log")
    axb.set_ylabel(r"absolute size $\times10^{6}$", fontsize=10)
    axb.legend(frameon=False, fontsize=9, loc="best")
    axb.set_title("(b) the same two quantities, absolute",
                  fontsize=10, color=INK, loc="left")
    for xi, r in zip(x, rows):
        axb.annotate(f"$Z$={r['Z']:.1f}", (xi, r["bias"] * 1e6), fontsize=8,
                     color=CZ, ha="center", va="bottom", xytext=(0, 7),
                     textcoords="offset points")

    for ax in (axa, axb):
        ax.set_xticks(x)
        ax.set_xticklabels([f"$L={L}$\n$V={r['V']}$\n{r['nchains']} chains"
                            for L, r in zip(Ls, rows)], fontsize=9)
        ax.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
        ax.set_axisbelow(True)
        for sp in ("top",):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=9)

    fig.suptitle(r"Seed quality is flat in volume; $z$ grows because the SEM falls"
                 f"   ($\\beta_f={rows[0]['beta']:g}$, one lift per volume)",
                 fontsize=11, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white")
    print(f"wrote {out}")
    for r in rows:
        print(f"  L={r['L']:<4} V={r['V']:<6} chains={r['nchains']:<4} "
              f"Z={r['Z']:7.2f}  PPM={r['PPM']:9.1f}  "
              f"|bias|={r['bias']:.3e}  SEM={r['sem']:.3e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
