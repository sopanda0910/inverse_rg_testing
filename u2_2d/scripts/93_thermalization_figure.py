"""Trajectories to equilibrate, and the interval they are spent against.

This is the preconditioner's actual claim -- how long a chain takes to reach
the target -- and it is plotted directly rather than as the ratio
`F = interval / t_therm` of `91_money_split_figure.py`. Two reasons:

  * that ratio is structurally confounded. Its numerator is built from the
    NORMALIZED autocorrelation, so sigma_cfg cancels and it is
    band-independent; its denominator is a crossing against +-2 sigma_cfg/sqrt(n)
    and is not. The ratio therefore falls with volume and coupling even at
    fixed model quality;
  * and the headline here is that the cold chain does NOT equilibrate at most
    couplings, which a ratio hides inside an "unbounded" marker. Plotted
    directly it is the most visible thing in the figure.

Both timescales are shown together, which is what makes the cost legible: the
horizontal band is the decorrelation interval, the trajectories a classical
chain must spend per configuration ONCE equilibrated, so a t_therm far above it
is a burn-in that dominates, and a t_therm at or below it is a burn-in that
costs less than a single independent draw.

`t_therm` is `t_therm_threshold_old` from the scan, which is a RECORD index, so
it is multiplied by `record_every` to reach trajectories. The timescales file's
own `therm_*` fields are NOT used: they apply a one-sigma band that the bias
must stay inside for the whole remaining window, which returns roughly the
budget for a chain that is perfectly equilibrated (396-398 against 0-11 records
for the same arm and coupling).
"""
import argparse
import json
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

BASE = ROOT / "out/u2_2d/coverage_scan_relaxation"
# Rebound by main() from --base; the default is the grid the paper's
# current numbers were read off, so it is never changed implicitly.
_BASE = BASE
TIMESCALES = BASE / "_standard_timescales.json"
ROWS = ((("crossover", "crossover_topo"), 32),
        (("crossover_L64", "crossover_L64_topo"), 64))
COLS = ((0, "plain HMC"), (1, "winding HMC"))
ARMS = (("cold start", "#0072B2", "cold start"),
        ("diffusion seed", "#D55E00", "preconditioned"))


def load(ckpt, stem, ts):
    """beta, per-arm t_therm in trajectories, the budget, and the interval."""
    f = _BASE / ckpt / f"{stem}.json"
    if not f.exists():
        return None
    out = {"beta": [], "budget": [], "interval": [],
           **{a: [] for a, _, _ in ARMS}}
    for r in json.loads(f.read_text(encoding="utf-8")):
        beta = float(r["beta"])
        sf = _BASE / ckpt / "series" / f"{stem}_beta{beta:g}.npz"
        if not sf.exists():
            continue
        with np.load(sf) as z:
            re_ = float(z["record_every"])
        tt = r.get("t_therm_threshold_old") or {}
        out["beta"].append(beta)
        out["budget"].append(float(r.get("n_traj", 400)))
        iv = (ts.get(f"{ckpt}|{stem}|{beta:g}", {}) or {}).get("interval_local_cold")
        out["interval"].append(float(iv) if iv else np.nan)
        for arm, _, _ in ARMS:
            # The slowest observable, and non-convergence must PROPAGATE:
            # the scan writes it as `Infinity`, which survives this filter and
            # carries through max(), so the isfinite test below catches it.
            # This is only safe because nothing converts that sentinel to None
            # upstream -- fig65's `_scan_tt` does, and there the identical
            # filter silently returned the slowest CONVERGENT observable
            # instead (FEEDBACK SS 18). Do not normalise inf to None here.
            vals = [v for v in (tt.get(arm) or {}).values() if v is not None]
            worst = max(vals) if vals else None
            out[arm].append(np.inf if worst is None or not np.isfinite(worst)
                            else worst * re_)
    if not out["beta"]:
        return None
    o = np.argsort(out["beta"])
    return {k: np.asarray(v, dtype=float)[o] for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(BASE),
                    help="scan directory; coverage_scan_w8 for the "
                         "W(8x8) grid")
    ap.add_argument("--out",
                    default=str(ROOT / "out/u2_2d/figures/fig67_thermalization.png"))
    ap.add_argument("--checkpoint", default="wide_dense")
    args = ap.parse_args()
    global _BASE, TIMESCALES
    _BASE = Path(args.base)
    TIMESCALES = _BASE / "_standard_timescales.json"

    ts = json.loads(TIMESCALES.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 2, figsize=(9.8, 6.4), sharex=True, sharey=True)
    for row, (stems, L) in enumerate(ROWS):
        for col, (si, slabel) in enumerate(COLS):
            ax = axes[row][col]
            d = load(args.checkpoint, stems[si], ts)
            if d is None:
                ax.set_axis_off()
                continue
            iv = np.nanmedian(d["interval"])
            if np.isfinite(iv):
                ax.axhspan(0.5, iv, color="#C9E3F5", alpha=0.75, zorder=0)
            for arm, colour, _ in ARMS:
                v = d[arm]
                ok = np.isfinite(v)
                # a t_therm of 0 is a real answer: already at target
                ax.plot(d["beta"][ok], np.maximum(v[ok], 0.6), "o-",
                        color=colour, ms=4.8, lw=1.3, zorder=3)
                if (~ok).any():
                    ax.plot(d["beta"][~ok], d["budget"][~ok] * 1.45, "^",
                            mfc="none", mec=colour, mew=1.4, ms=7,
                            ls="none", zorder=4)
            ax.plot(d["beta"], d["budget"], "--", color="0.55", lw=0.9,
                    zorder=1)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_ylim(0.45, 1500)
            ax.grid(alpha=0.2, lw=0.5)
            if row == 0:
                ax.set_title(slabel, fontsize=11)
            if col == 0:
                ax.set_ylabel(f"$L={L}$\n" "trajectories to equilibrate",
                              fontsize=10)
            if row == 1:
                ax.set_xlabel(r"$\beta$", fontsize=11)

    key = [Line2D([], [], marker="o", color=c, lw=1.3, ms=4.8, label=lbl)
           for _, c, lbl in ARMS]
    key += [
        Line2D([], [], marker="^", mfc="none", mec="0.35", mew=1.4, ls="none",
               ms=7, label="never, within budget"),
        Line2D([], [], color="0.55", ls="--", lw=0.9, label="budget"),
        Line2D([], [], color="#C9E3F5", lw=7,
               label="one decorrelation interval"),
    ]
    fig.legend(handles=key, loc="upper center", bbox_to_anchor=(0.5, 0.95),
               ncol=5, frameon=False, fontsize=8.8, handletextpad=0.6,
               columnspacing=1.6)
    fig.suptitle("Trajectories to equilibrate, against the interval they buy  "
                 f"({args.checkpoint.replace('_', '-')} checkpoint)",
                 fontsize=11.5)
    fig.text(0.5, 0.004,
             "Equilibration is the slowest of the plaquette, $W(2{\\times}2)$ "
             "and $W(4{\\times}4)$. Below the shaded band a burn-in costs less "
             "than one independent configuration.",
             ha="center", fontsize=8.5, color="0.35")
    fig.tight_layout(rect=(0, 0.035, 1, 0.915))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")

    for stems, L in ROWS:
        for si, slabel in COLS:
            d = load(args.checkpoint, stems[si], ts)
            if d is None:
                continue
            for arm, _, albl in ARMS:
                v = d[arm]
                fin = np.isfinite(v)
                med = np.median(v[fin]) if fin.any() else np.nan
                print(f"  L={L:3d} {slabel:12s} {albl:15s} "
                      f"equilibrated {int(fin.sum()):2d}/{len(v)}   "
                      f"median {med:7.1f} trajectories")
            print(f"  {'':3s} {'':12s} {'interval':15s} "
                  f"median {np.nanmedian(d['interval']):7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
