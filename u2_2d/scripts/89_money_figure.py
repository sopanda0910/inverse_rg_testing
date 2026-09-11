"""The money figure: what one independent configuration costs, in trajectories,
from a classical chain and from a lifted one, and how training coverage sets the
coupling at which the lift stops working.

BOTH TIMESCALES ARE STANDARD AND CITED. Nothing is invented except one stated
convention.

    interval = 2 tau_int, maximised over the scored observables INCLUDING Q^2,
        with tau_int from Sokal's automatic windowing [Madras & Sokal 1988;
        Wolff 2004]. N measurements carry N / (2 tau_int) independent samples,
        so this is the cost of one. The maximisation must include Q^2: a local
        observable decorrelates perfectly well in a chain whose topology has not
        moved once, so a plaquette-only interval never sees freezing. A frozen
        series is reported as infinite rather than integrated, since a constant
        has no autocorrelation and would otherwise return a spuriously SMALL
        tau_int. Computed by 90_standard_timescales.py.

    t_therm = the first trajectory after which the bias stays within two
        standard errors for five consecutive measurements, following Detmold &
        Endres' equilibration analysis [PRD 92, 114516; PRD 94, 114502]. The
        two-standard-error window and the five-measurement run are a stated
        convention, and they are the only free choices anywhere in this figure.

TWO BASELINES, because they answer different questions and only one is a fair
fight. Plain HMC is the generic sampler: its interval is infinite from model
beta ~6 upward, since topology never moves, so the improvement factor there is a
LOWER BOUND set by the trajectory budget. HMC plus the winding update is the
best classical sampler that exists for this theory, and it stays finite to model
beta ~400; against it the lift is roughly break-even in trajectories, which is
the honest result and is reported as such. The winding move exists only because
the theory is 2D and abelian, which is exactly what does not carry to 4D SU(3).

    python u2_2d/scripts/89_money_figure.py
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BASE = ROOT / "out/u2_2d/coverage_scan_relaxation"
TIMESCALES = BASE / "_standard_timescales.json"

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
WHMC_C, PLAIN_C = "#333333", "#8a8a8a"
BUDGET = 400.0

# Ceilings in RAW beta, the coefficient in the Wilson action, which is what the
# abstract and the rest of the paper quote. The network is conditioned on the
# matched model coupling, which is roughly a quarter of it, and plotting in that
# convention made a scan that reaches beta = 1660 look as though it stopped
# at 400.
ARMS = [
    ("cov60", "#CC79A7", 227.3, r"cov60 ($\beta_{\max}=227$)"),
    ("default", "#0072B2", 416.5, r"default ($\beta_{\max}=416$)"),
    ("wide", "#009E73", 2000.0, r"wide ($\beta_{\max}=2000$)"),
    # matplotlib is not in LaTeX mode here, so the underscore is written plainly
    # rather than escaped: an escaped one renders as a literal backslash.
    ("wide_dense", "#D55E00", 2000.0, "wide_dense " + r"($\beta_{\max}=2000$)"),
]

# Only two are drawn: the deployed checkpoint and the widest one, which is the
# sharpest contrast the grid contains and keeps four curves per panel from
# burying it. All four are tabulated in the appendix.
PLOT = ("default", "wide_dense")


def worst(d, arm):
    v = (d or {}).get(arm)
    if not isinstance(v, dict):
        return float(v) if v is not None else float("nan")
    vals = [float(x) for x in v.values() if x is not None]
    return max(vals) if vals else float("nan")


def record_every(ckpt, stem, beta):
    """Records-to-trajectories factor for one scan point.

    `t_therm_threshold_old` is a RECORD INDEX -- 28_crossover_scan.py writes it
    straight out of `thermalization_time` with no `record_every` factor --
    while the interval it is divided into is in TRAJECTORIES, because
    90_standard_timescales.py multiplies by `record_every`. Dividing one by the
    other unconverted inflates every improvement factor by this factor.
    """
    f = BASE / ckpt / "series" / f"{stem}_beta{beta:g}.npz"
    if not f.exists():
        raise FileNotFoundError(
            f"no series file for {ckpt}/{stem} at beta={beta:g}; "
            "the records-to-trajectories factor cannot be recovered")
    with np.load(f) as z:
        return float(z["record_every"])


def load(ckpt, stem, ts):
    """model beta, lift equilibration cost, and both classical intervals."""
    f = BASE / ckpt / f"{stem}.json"
    if not f.exists():
        return None
    plain_stem = stem.replace("_topo", "")
    rows = json.loads(f.read_text())
    d = {k: [] for k in ("beta", "lift", "cost_wind", "cost_plain")}
    for r in rows:
        b = r["beta"]
        d["beta"].append(b)
        # Each lift descends from an independent base chain, so successive
        # lifts are independent by construction and the per-configuration cost
        # is the equilibration cost alone. A classical chain has to pay both.
        d["lift"].append(worst(r.get("t_therm_threshold_old", {}),
                               "diffusion seed")
                         * record_every(ckpt, stem, b))
        for key, st in (("cost_wind", stem), ("cost_plain", plain_stem)):
            iv = ts.get(f"{ckpt}|{st}|{b:g}", {}).get("interval_cold")
            meta = (BASE / ckpt / f"{st}.json")
            tt = np.inf
            if meta.exists():
                for rr in json.loads(meta.read_text()):
                    if abs(rr["beta"] - b) < 1e-9:
                        # only tested for finiteness below, so the
                        # records-to-trajectories factor is irrelevant here
                        tt = worst(rr.get("t_therm_threshold_old", {}),
                                   "cold start")
                        break
            # THE STEADY-STATE COST IS THE INTERVAL ALONE. A classical chain
            # pays t_therm once and an interval for every configuration after
            # it, so N configurations cost t_therm + N * interval and the
            # per-configuration cost tends to the interval. Charging t_therm
            # per configuration would be the N = 1 answer and it flatters the
            # lift, which really does pay its own t_therm every time because
            # each lift starts a fresh chain.
            #
            # t_therm still enters as a GATE. An interval is the cost of an
            # independent configuration only if the chain is sampling the right
            # distribution: one that never equilibrates decorrelates happily
            # about the WRONG one, so it supplies nothing at any budget.
            d[key].append(np.inf if (iv is None or not np.isfinite(tt))
                          else float(iv))
    return {k: np.asarray(v, dtype=float) for k, v in d.items()}


def _style(ax, title, ylab):
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"coupling $\beta$", fontsize=9.5, color=INK)
    ax.set_ylabel(ylab, fontsize=9.5, color=INK)
    ax.set_title(title, fontsize=9.5, color=INK, loc="left")
    ax.grid(True, which="both", color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8.5)


def ratio_panel(ax, stem, title, ts):
    top = 2.0e3
    for ck, colour, ceil, label in ARMS:
        if ck not in PLOT:
            continue
        d = load(ck, stem, ts)
        if d is None:
            continue
        b, s, iv = d["beta"], d["lift"], d["cost_wind"]
        alive = np.isfinite(s)
        cost = np.maximum(s, 1.0)
        meas = alive & np.isfinite(iv)
        bound = alive & ~np.isfinite(iv)
        F = np.where(np.isfinite(iv), iv / cost, BUDGET / cost)
        ax.plot(b[alive], F[alive], "-", color=colour, lw=1.5, alpha=0.8,
                zorder=3, label=label)
        ax.plot(b[meas], F[meas], "o", color=colour, ms=5, zorder=4,
                markeredgecolor="white", markeredgewidth=0.6)
        ax.plot(b[bound], F[bound], "^", color=colour, ms=7, zorder=4,
                markeredgecolor="white", markeredgewidth=0.6)
        if (~alive).any():
            ax.plot(b[~alive], np.full((~alive).sum(), 0.45), "x",
                    color=colour, ms=7, mew=2.0, zorder=4)
        if b.min() <= ceil <= b.max() * 1.05:
            ax.axvline(ceil, color=colour, ls=":", lw=1.2, alpha=0.8, zorder=1)

    ax.axhspan(1.0, top, color="#2ca02c", alpha=0.06, zorder=0)
    ax.axhline(1.0, color=WHMC_C, lw=1.0, ls="--", alpha=0.8, zorder=2)
    ax.set_ylim(0.35, top)
    ax.text(0.025, 0.965, "lift cheaper", transform=ax.transAxes, fontsize=7.5,
            color="#2ca02c", va="top")
    # kept clear of the markers themselves: at the bottom of the panel this
    # legend sat directly behind the crosses it was explaining
    # The cross marks a MEASURED failure of the lift, not a gap in the data:
    # every coupling is evaluated for every checkpoint. It is not the same
    # thing as the training ceiling (dotted line), and at L=64 the narrow
    # checkpoints fail well before theirs.
    ax.text(0.025, 0.895, r"$\times$ = lift did not equilibrate",
            transform=ax.transAxes, fontsize=7.5, color=MUTED, va="top")
    ax.text(0.975, 0.965, r"$\blacktriangle$ lower bound", transform=ax.transAxes,
            fontsize=7.5, color=MUTED, ha="right", va="top")
    _style(ax, title, "improvement factor over HMC $+$ winding")


def cost_panel(ax, stem, title, ts, only=None):
    """`only` restricts the lift curves to one checkpoint: six series in one
    panel was unreadable, and the divergence of the classical arms is the point
    here rather than the spread between checkpoints."""
    plain, wind, betas = [], [], None
    for ck, _, _, _ in ARMS:
        d = load(ck, stem, ts)
        if d is None:
            continue
        betas = d["beta"]
        plain.append(d["cost_plain"])
        wind.append(d["cost_wind"])
    plain = np.nanmedian(np.vstack(plain), axis=0)
    wind = np.nanmedian(np.vstack(wind), axis=0)

    for arr, colour, lab, mk in ((plain, PLAIN_C, "plain HMC", "D"),
                                 (wind, WHMC_C, r"HMC $+$ winding", "s")):
        fin = np.isfinite(arr)
        ax.plot(betas[fin], arr[fin], mk + "-", color=colour, ms=4.5, lw=1.7,
                zorder=4, label=lab)
        ax.plot(betas[~fin], np.full((~fin).sum(), BUDGET), "^", color=colour,
                ms=7, zorder=4)

    for ck, colour, _, label in ARMS:
        if only and ck != only:
            continue
        d = load(ck, stem, ts)
        if d is None:
            continue
        s, b = d["lift"], d["beta"]
        f = np.isfinite(s)
        ax.plot(b[f], np.maximum(s[f], 0.6), "-o", color=colour, ms=4.5, lw=1.6,
                zorder=3, markeredgecolor="white", markeredgewidth=0.5,
                label=f"lift, {label}")
        ax.plot(b[~f], np.full((~f).sum(), BUDGET), "^", color=colour, ms=6,
                zorder=3)
    ax.set_ylim(0.4, BUDGET * 3.6)
    ax.text(0.975, 0.965, r"$\blacktriangle$ never, in $400$ trajectories",
            transform=ax.transAxes, ha="right", va="top", fontsize=7.5,
            color=MUTED)
    _style(ax, title, "trajectories per independent configuration")


def save(fig, path, ncol, handles=None, labels=None, anchor=-0.13):
    if handles:
        fig.legend(handles, labels, loc="lower center", ncol=ncol, frameon=False,
                   fontsize=9, bbox_to_anchor=(0.5, anchor))
    fig.tight_layout()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out/u2_2d/figures/fig64_money.png"))
    ap.add_argument("--out-cost",
                    default=str(ROOT / "out/u2_2d/figures/fig65_cost.png"))
    args = ap.parse_args()
    ts = json.loads(TIMESCALES.read_text())

    # The money plot on its own: four curves per panel and nothing else.
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.2), sharey=True)
    ratio_panel(axes[0], "crossover_topo", r"(a)  $L=32$", ts)
    ratio_panel(axes[1], "crossover_L64_topo", r"(b)  $L=64$", ts)
    axes[1].set_ylabel("")
    h, lab = axes[0].get_legend_handles_labels()
    fig.suptitle("Training coverage sets the coupling at which the lift stops working",
                 fontsize=10.5, color=INK, y=1.0)
    save(fig, args.out, 4, h, lab)

    # The absolute costs, one representative checkpoint against both baselines,
    # so the divergence of the classical arms is legible.
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.2), sharey=True)
    cost_panel(axes[0], "crossover_topo", r"(a)  $L=32$", ts, only="wide_dense")
    cost_panel(axes[1], "crossover_L64_topo", r"(b)  $L=64$", ts, only="wide_dense")
    axes[1].set_ylabel("")
    h, lab = axes[0].get_legend_handles_labels()
    fig.suptitle("Plain HMC stops producing independent configurations; the lift does not",
                 fontsize=10.5, color=INK, y=1.0)
    save(fig, args.out_cost, 3, h, lab)

    for stem, lab in (("crossover_topo", "L32"), ("crossover_L64_topo", "L64")):
        for ck, _, ceil, _ in ARMS:
            d = load(ck, stem, ts)
            if d is None:
                continue
            b, s, iv = d["beta"], d["lift"], d["cost_wind"]
            alive = np.isfinite(s)
            meas = alive & np.isfinite(iv)
            F = iv[meas] / np.maximum(s[meas], 1.0)
            print(f"{lab} {ck:11s} alive {alive.sum():2d}/{len(s)}  "
                  f"top live mb={b[alive].max() if alive.any() else np.nan:6.1f}  "
                  f"F median={np.median(F) if meas.any() else np.nan:5.2f} "
                  f"range=[{F.min() if meas.any() else np.nan:5.2f},"
                  f"{F.max() if meas.any() else np.nan:6.2f}]  "
                  f"bounds={int(alive.sum() - meas.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
