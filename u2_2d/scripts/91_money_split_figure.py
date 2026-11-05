"""The improvement factor split by scale, against both classical samplers.

Replaces the single maximized-over-scales panel of `89_money_figure.py`. Three
things that figure could not show, and this one does:

  * UV and IR separately. The two timescales order the scales OPPOSITELY --
    the infrared decorrelates FASTER (measured, 10-12 sigma, and a genuine
    difference in the decay rate of rho(t) rather than signal-to-noise
    dilution) while it equilibrates SLOWER, because local repair is low-pass.
    One number maximized over scales hides both halves.
  * Both classical baselines on the same axes. Winding HMC is the baseline of
    record because plain HMC is topologically frozen, but for LOCAL observables
    plain HMC is a legitimate competitor and the gap between the two is the
    cost of the winding move. Putting them in one panel makes that gap legible
    instead of a cross-reference.
  * No budget-built "lower bounds". Where the classical arm did not equilibrate
    it supplied no independent configuration of the target, so no factor
    exists; those couplings are marked on a rug below the axis rather than
    given a numeric position they have not earned.

F = interval(classical) / t_therm(preconditioned), per scale, both in
trajectories.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "u1_2d" / "scripts"))
from _figstyle import apply_paper_font  # noqa: E402

apply_paper_font()

BASE = ROOT / "out/u2_2d/coverage_scan_relaxation"
# Rebound by main() from --base; the default is the grid the paper's
# current numbers were read off, so it is never changed implicitly.
_BASE = BASE
TIMESCALES = BASE / "_standard_timescales.json"

# One checkpoint in the main figure; the checkpoint comparison is its own
# figure. Four checkpoints x two baselines x two scales is unreadable.
CKPT = "wide_dense"

VOLUMES = (("crossover", 32), ("crossover_L64", 64))
SCALES = (("uv", "plaquette"), ("ir", r"$W(4\times4)$"),
          ("q", r"topology, $Q^2$"))
# stem suffix -> (label, colour).  "" is plain periodic HMC, "_topo" adds the
# winding update of Sec. III.
BASELINES = (("", "plain HMC", "#0072B2"),
             ("_topo", "winding HMC", "#D55E00"))


OBS_OF = {"uv": "plaquette", "ir": "wilson_4x4", "q": None}


def _record_every(ckpt, stem, beta):
    f = _BASE / ckpt / "series" / f"{stem}_beta{beta:g}.npz"
    with np.load(f) as z:
        return float(z["record_every"])


def _scan_tt(ckpt, stem):
    """t_therm per arm per observable, in TRAJECTORIES, from the scan JSON.

    NOT from the timescales file's therm_* fields: those use a one-sigma band
    the bias must stay inside for the whole remaining window, which returns
    roughly the budget for an equilibrated chain (396-398 against 0-11 records
    here). `t_therm_threshold_old` is the scan's own criterion and is what
    89_money_figure.py uses; it is a RECORD index, so it needs record_every.
    """
    f = _BASE / ckpt / f"{stem}.json"
    out = {}
    if not f.exists():
        return out
    for r in json.loads(f.read_text(encoding="utf-8")):
        beta = float(r["beta"])
        re_ = _record_every(ckpt, stem, beta)
        out[round(beta, 4)] = {
            arm: {o: (None if v is None or not np.isfinite(v) else float(v) * re_)
                  for o, v in d.items()}
            for arm, d in (r.get("t_therm_threshold_old") or {}).items()
        }
    return out


def _scan_qchanges(ckpt, stem):
    """Sector changes of the COLD arm, the gate for the topology panel."""
    f = _BASE / ckpt / f"{stem}.json"
    if not f.exists():
        return {}
    return {round(float(r["beta"]), 4):
            int((r.get("q_changes") or {}).get("cold start", 0))
            for r in json.loads(f.read_text(encoding="utf-8"))}


def collect(ts, ckpt, stem, scale):
    """(beta, F, failed) for one checkpoint/stem/scale."""
    obs = OBS_OF[scale]
    tts = _scan_tt(ckpt, stem)
    qchanges = _scan_qchanges(ckpt, stem)
    betas, factors, failed, unbounded = [], [], [], []
    for key, rec in ts.items():
        ck, st, _ = key.split("|")
        if ck != ckpt or st != stem:
            continue
        beta = float(rec["beta"])
        iv = rec.get(f"interval_{scale}_cold")
        arms = tts.get(round(beta, 4), {})
        if scale == "q":
            # TOPOLOGY. The gate is whether the classical chain changed sector
            # at all, NOT its tau_int: tau_int returns 0.5 on a zero-variance
            # series, so a chain frozen at Q = 0 reports the SHORTEST possible
            # interval when it supplies no independent charge at any budget.
            # The preconditioned arm needs no equilibration here -- its charge
            # is transported, correct at t = 0 -- so it is charged one
            # trajectory, as elsewhere.
            if qchanges.get(round(beta, 4), 0) <= 0 or iv is None:
                unbounded.append(beta)
                continue
            betas.append(beta)
            factors.append(float(iv))
            continue
        # THE DENOMINATOR IS THE SLOWEST OBSERVABLE, NOT THIS ONE.
        # A configuration is not usable because W(4x4) has converged while the
        # plaquette has not, so the cost of a usable configuration is set by
        # the slowest observable. Using each observable's own t_therm -- which
        # this figure did -- divides by a value that is 0 at many couplings for
        # the larger loops, gets charged as one trajectory to keep the ratio
        # finite, and reports an improvement that is really a floor. Measured:
        # at L = 64 the preconditioned W(4x4) t_therm is 0 at five of eight
        # couplings while the plaquette is 44-94 trajectories.
        def _worst(d):
            # `None` is "never reached the band", so it PROPAGATES: the cost of
            # a usable configuration is set by the slowest observable, and an
            # observable that never arrives makes that cost unbounded. Taking
            # max() over only the values that are not None would instead report
            # the slowest observable THAT CONVERGED -- which at beta = 1065 at
            # L = 32 credited the cold arm with 21 trajectories when the
            # plaquette, W(2x2) and W(4x4) had all never arrived.
            if not d:
                return None
            vals = list(d.values())
            if any(v is None for v in vals):
                return None
            return max(vals)
        tt = _worst(arms.get("diffusion seed"))
        cold_tt = _worst(arms.get("cold start"))
        # The classical arm must have equilibrated for its interval to count as
        # a supply of configurations of the TARGET; otherwise it decorrelates
        # happily about the wrong distribution.
        if iv is None or cold_tt is None:
            failed.append(beta)
            continue
        if tt is None:
            continue
        # t_therm = 0 is charged as one trajectory, which keeps the ratio
        # finite at the price of understating it.
        betas.append(beta)
        factors.append(float(iv) / max(float(tt), 1.0))
    order = np.argsort(betas)
    return (np.asarray(betas)[order], np.asarray(factors)[order],
            sorted(failed), sorted(unbounded))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=str(BASE),
                    help="scan directory; coverage_scan_w8 for the "
                         "W(8x8) grid")
    ap.add_argument("--out", default=str(ROOT / "out/u2_2d/figures/fig65_money_split.png"))
    ap.add_argument("--checkpoint", default=CKPT)
    args = ap.parse_args()
    global _BASE, TIMESCALES
    _BASE = Path(args.base)
    TIMESCALES = _BASE / "_standard_timescales.json"

    ts = json.loads(TIMESCALES.read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 3, figsize=(12.6, 6.6), sharex=True, sharey="row")

    for row, (stem, L) in enumerate(VOLUMES):
        for col, (scale, scale_label) in enumerate(SCALES):
            ax = axes[row][col]
            for suffix, blabel, colour in BASELINES:
                b, f, failed, unb = collect(ts, args.checkpoint,
                                            stem + suffix, scale)
                if len(b):
                    ax.plot(b, f, "o", color=colour, ms=5.5, ls="none",
                            label=blabel, zorder=3)
                # No finite factor because the classical chain never changed
                # sector: the factor is unbounded in our favour, so it is drawn
                # as an arrow at the top rather than given a value.
                if unb:
                    ax.plot(unb, [0.93] * len(unb), marker="^", ms=6,
                            ls="none", mfc="none", mec=colour, mew=1.3,
                            zorder=3, transform=ax.get_xaxis_transform())
                # Couplings with no finite factor: marked on a rug at the
                # bottom of the axes, NOT given a numeric position. Drawn in
                # axis-fraction coordinates on the y axis -- plotting them at
                # get_ylim()[0] with clip_on=False on a log scale let the
                # markers sit far outside the data range, and bbox_inches
                # "tight" then grew the canvas to 130k pixels.
                if failed:
                    ax.plot(failed, [0.04] * len(failed), marker="|", ms=6,
                            ls="none", color=colour, alpha=0.8, zorder=2,
                            transform=ax.get_xaxis_transform())
            ax.axhline(1.0, color="0.45", lw=0.9, ls="--", zorder=1)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.grid(alpha=0.25, lw=0.5)
            if row == 0:
                ax.set_title(scale_label, fontsize=11)
            if col == 0:
                ax.set_ylabel(f"$L={L}$\nimprovement factor", fontsize=10)
            if row == 1:
                ax.set_xlabel(r"$\beta$", fontsize=11)

    # Figure-level key, horizontal, so it cannot overlap data and the two
    # failure markers are visually separate from the two baseline colours.
    from matplotlib.lines import Line2D
    key = [
        Line2D([], [], marker="o", color=BASELINES[0][2], ls="none", ms=5.5,
               label=BASELINES[0][1]),
        Line2D([], [], marker="o", color=BASELINES[1][2], ls="none", ms=5.5,
               label=BASELINES[1][1]),
        Line2D([], [], marker="^", mfc="none", mec="0.35", mew=1.3, ls="none",
               ms=6, label="charge never moved: factor unbounded"),
        Line2D([], [], marker="|", color="0.35", ls="none", ms=7,
               label="no equilibration within budget"),
    ]
    fig.legend(handles=key, loc="upper center", bbox_to_anchor=(0.5, 0.955),
               ncol=4, frameon=False, fontsize=9, handletextpad=0.6,
               columnspacing=2.2)
    fig.suptitle("Improvement factor over each classical sampler, by scale  "
                 f"({args.checkpoint.replace('_', '-')} checkpoint)",
                 fontsize=11.5)
    fig.text(0.5, 0.005,
             "Ticks: the classical sampler did not equilibrate, so no factor exists. "
             "Open triangles: its charge never moved, so it supplies no "
             "independent configuration of any sector and the factor is "
             "unbounded. Points are not joined because the gaps are those cases.",
             ha="center", fontsize=8.5, color="0.35")
    fig.tight_layout(rect=(0, 0.04, 1, 0.91))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")

    # the numbers behind the figure, so the text can quote them
    for stem, L in VOLUMES:
        for scale, lbl in SCALES:
            for suffix, blabel, _ in BASELINES:
                b, f, failed, unb = collect(ts, args.checkpoint,
                                            stem + suffix, scale)
                if not len(f):
                    print(f"  L={L:3d} {scale} vs {blabel:12s}: "
                          f"no finite points ({len(unb)} unbounded, "
                          f"{len(failed)} classical failures)")
                    continue
                print(f"  L={L:3d} {scale} vs {blabel:12s}: "
                      f"n={len(f):2d} median={np.median(f):6.2f} "
                      f"range {f.min():.2f}-{f.max():.2f}  "
                      f"({len(unb)} unbounded, {len(failed)} failures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
