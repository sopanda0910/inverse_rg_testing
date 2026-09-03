"""Cost-efficiency figure: what the diffusion seed saves against classical HMC,
as a single dimensionless number, vs beta and volume.

DEFINITION (the point of this script -- read before changing the plot).
`28_crossover_scan.py` already measures everything this needs per (L, beta):
  * t_therm(arm)  -- trajectories until every local observable (plaquette,
    W(2x2), W(4x4)) is within 2 sigma of the closed form for 5 consecutive
    records, for the diffusion-seeded / cold-start / hot-start arms.
  * interval       -- 2 tau_int(plaquette) of an EQUILIBRATED chain of the same
    sampler: the number of trajectories a chain that is already thermalized
    needs between two independent configurations. This is the steady-state
    per-sample cost of running HMC at all, seed or no seed.

Two ratios, both dimensionless, both already sitting in the JSON, and they
answer two different questions -- report both, never just one:

  FIRST-CONFIGURATION SPEEDUP  (field: "speedup")
      speedup = min(t_therm(cold), t_therm(hot)) / t_therm(seed)
    "Starting a chain from scratch, how many fewer trajectories does the seed
    need to reach equilibrium than a naive HMC chain does?" This is the
    number that goes to infinity (a LOWER BOUND, drawn as an arrow) once the
    coupling is stiff enough that cold/hot HMC never equilibrates in the
    budget at all -- "HMC dead" in `28`'s regime classification.

  STEADY-STATE COST-EFFICIENCY  (computed here: "cost_efficiency")
      cost_efficiency = interval / t_therm(seed)
    "Against a classical chain that is ALREADY running and already
    equilibrated -- the best case classical HMC can offer -- how does the
    seed's one-shot thermalization cost compare to the steady-state cost of
    pulling one more independent sample out of it?" cost_efficiency > 1 means
    the pipeline beats even an idealized always-equilibrated classical chain;
    < 1 means the seed is slower than simply continuing to run one. This is
    the harder bar and the more honest one -- it is the ratio
    `30_seed_quality_figure.py` already draws as "the yardstick" against
    t_therm(seed), just expressed as a single number instead of two curves.
    Note it stays FINITE even in the "HMC dead" regime, because `interval` is
    measured off whichever chain in the record actually equilibrated (falling
    back to the seed's own post-thermalization tail when cold/hot never get
    there) -- so cost_efficiency < 1 there is a real, conservative statement:
    even a chain nobody can reach classically decorrelates faster than the
    seed thermalizes.

Both ratios are read off couplings, plotted against beta_f on a log axis,
split by lattice volume (colour) and HMC round -- plain vs HMC + marginal
winding (linestyle) -- and the model's TRAINING RANGE (in model beta, the
minimum-KL U(1) projection every rung is conditioned on -- see CLAUDE.md /
DESIGN.md) is shaded: couplings past the checkpoint's highest training rung
are extrapolation and are hatched exactly as `30_seed_quality_figure.py`
hatches them.

Consumes whatever `28_crossover_scan.py` has already written under
--dirs (one directory per volume; sharded output files are merged the same
way `30_seed_quality_figure.py` does). Produces NO new HMC -- this is a
plotting/analysis pass over existing JSON.

    python u2_2d/scripts/57_cost_efficiency_figure.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
VOLUME_COLOUR = {8: "#009E73", 16: "#0072B2", 32: "#D55E00", 64: "#CC79A7"}
ROUND_STYLE = {False: ((0, ()), "plain HMC"),
              True: ((0, (5, 2)), r"HMC + marginal winding ($\Delta Q=1$)")}

# Training rungs of the deployed checkpoint (det_score_net.pt), in model beta.
# Ported verbatim from `30_seed_quality_figure.py` -- see that file's comment
# for why this list, not L, is the coverage axis. Override with
# --train-model-beta-max for a different checkpoint.
DEFAULT_TRAIN_MODEL_BETA_MAX = 104.132


def load_rounds(dirs: list[str]) -> dict:
    """-> {lattice_size: {topological_updates(bool): {beta: row}}}."""
    by_volume: dict = {}
    for d in dirs:
        src = Path(d)
        if not src.exists():
            continue
        for path in sorted(src.glob("*.json"), key=lambda q: q.stat().st_mtime):
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(rows, list):
                continue
            for r in rows:
                if "beta" not in r or "t_therm" not in r:
                    continue
                L = r.get("lattice_size")
                flag = bool(r.get("topological_updates"))
                by_volume.setdefault(L, {False: {}, True: {}})[flag][r["beta"]] = r
    return by_volume


def slowest(record, arm):
    vals = record["t_therm"].get(arm)
    if not vals:
        return float("inf")
    return max(float(v) for v in vals.values())


def cost_efficiency(record) -> float | None:
    """interval / t_therm(seed). None if interval is unmeasured; 0.0 if the
    seed itself never thermalizes (the pipeline delivers nothing usable)."""
    interval = record.get("interval")
    if not interval or not math.isfinite(interval):
        return None
    seed_t = slowest(record, "diffusion seed")
    if math.isinf(seed_t):
        return 0.0
    return interval / max(seed_t, 1.0)


def draw_metric(ax, by_volume, metric_fn, ylabel, train_max, log_floor, log_ceil):
    for L in sorted(by_volume):
        colour = VOLUME_COLOUR.get(L, "#444444")
        for flag in (False, True):
            rows = sorted(by_volume[L][flag].values(), key=lambda r: r["beta"])
            if not rows:
                continue
            ls, _ = ROUND_STYLE[flag]
            xs, ys, lo_xs, hi_xs = [], [], [], []
            for r in rows:
                v = metric_fn(r)
                if v is None:
                    continue
                if v <= 0.0:
                    lo_xs.append(r["beta"])
                elif math.isinf(v):
                    hi_xs.append(r["beta"])
                else:
                    xs.append(r["beta"])
                    ys.append(min(max(v, log_floor), log_ceil))
            if xs:
                ax.plot(xs, ys, color=colour, ls=ls, lw=1.8, marker="o", ms=4.5,
                        markeredgecolor="white", markeredgewidth=0.4, zorder=4,
                        alpha=0.95)
            for b in lo_xs:
                ax.plot([b], [log_floor], marker="v", ms=7, color=colour,
                        markerfacecolor="none", markeredgewidth=1.4, zorder=5)
            for b in hi_xs:
                ax.plot([b], [log_ceil], marker="^", ms=7, color=colour,
                        markerfacecolor="none", markeredgewidth=1.4, zorder=5)

    ax.axhline(1.0, color=INK, lw=1.1, ls=(0, (1, 1)), zorder=2)
    ax.set_yscale("log")
    ax.set_ylim(log_floor * 0.8, log_ceil * 1.25)
    ax.set_xscale("log")
    ax.set_ylabel(ylabel, fontsize=9.5, color=INK)
    ax.grid(True, which="major", color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))


def shade_training_range(ax, by_volume, train_max):
    all_rows = [r for vol in by_volume.values() for flag in vol.values()
                for r in flag.values()]
    mbetas = {r["beta"]: r.get("model_beta") for r in all_rows}
    inside = [b for b, m in mbetas.items() if m and m <= train_max]
    outside = [b for b, m in mbetas.items() if m and m > train_max]
    if not inside or not outside:
        return
    edge = math.sqrt(max(inside) * min(outside))
    xlo, xhi = ax.get_xlim()
    ax.axvspan(edge, xhi, facecolor="none", edgecolor="#5a3a8a", hatch="///",
              lw=0.0, alpha=0.5, zorder=1)
    ax.axvline(edge, color="#5a3a8a", lw=1.1, ls=(0, (3, 2)), zorder=3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dirs", nargs="+",
                        default=["out/u2_2d/crossover", "out/u2_2d/crossover_L64"],
                        help="directories to merge crossover-scan JSON from")
    parser.add_argument("--train-model-beta-max", type=float,
                        default=DEFAULT_TRAIN_MODEL_BETA_MAX,
                        help="highest model beta this checkpoint was trained on")
    parser.add_argument("--label", default="deployed checkpoint (det_score_net.pt)")
    parser.add_argument("--out", default="out/u2_2d/figures/fig57_cost_efficiency.png")
    args = parser.parse_args()

    by_volume = load_rounds(args.dirs)
    if not by_volume:
        print("no crossover-scan json found under " + ", ".join(args.dirs))
        return 1

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(6.9, 6.4), sharex=True,
        gridspec_kw={"height_ratios": (1.0, 1.0), "hspace": 0.10})

    draw_metric(ax_top, by_volume,
               lambda r: (r.get("speedup") if r.get("speedup") not in (None,)
                          else None),
               "first-configuration speedup\n" r"$\min(t_{cold},t_{hot})\,/\,t_{seed}$",
               args.train_model_beta_max, log_floor=0.3, log_ceil=1000.0)
    draw_metric(ax_bot, by_volume, cost_efficiency,
               "steady-state cost-efficiency\n" r"$\mathrm{interval}\,/\,t_{seed}$",
               args.train_model_beta_max, log_floor=0.03, log_ceil=10.0)
    for ax in (ax_top, ax_bot):
        shade_training_range(ax, by_volume, args.train_model_beta_max)
    ax_bot.set_xlabel(r"fine coupling  $\beta_f$", fontsize=10, color=INK)

    handles = [Line2D([], [], color=c, lw=2.0, label="L = %d" % L)
               for L, c in sorted(VOLUME_COLOUR.items()) if L in by_volume]
    handles += [Line2D([], [], color=INK, ls=ls, lw=1.6, label=lab)
                for ls, lab in ROUND_STYLE.values()]
    handles.append(Line2D([], [], color=INK, lw=1.1, ls=(0, (1, 1)),
                          label="breakeven (=1)"))
    handles.append(Line2D([], [], color=MUTED, marker="v", ms=7, lw=0,
                          markerfacecolor="none", markeredgewidth=1.4,
                          label="seed itself fails to thermalize"))
    handles.append(Line2D([], [], color=MUTED, marker="^", ms=7, lw=0,
                          markerfacecolor="none", markeredgewidth=1.4,
                          label="classical arm never thermalizes (lower bound)"))
    handles.append(Line2D([], [], color="none", marker="s", ms=0,
                          label="hatched: past training coverage"))
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.05),
              fontsize=8, frameon=False, ncol=3, labelcolor=INK)

    fig.suptitle("Cost efficiency of a diffusion seed vs classical HMC   ("
                 + args.label + ")", fontsize=11.5, color=INK, x=0.02, ha="left")
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote " + str(dest))

    print("\ncost-efficiency by coupling (winding round preferred, plain as fallback)")
    header = "  L".rjust(4) + "beta".rjust(11) + "model_b".rjust(10) + "speedup".rjust(11) + "cost_eff".rjust(11)
    print(header)
    for L in sorted(by_volume):
        rows = {**by_volume[L][False], **by_volume[L][True]}
        for b in sorted(rows):
            r = rows[b]
            ce = cost_efficiency(r)
            print("  " + "".join([
                str(L).rjust(4), "%11.2f" % b,
                "%10.2f" % (r.get("model_beta") or float("nan")),
                "%11s" % ("inf" if r.get("speedup_is_bound") else "%.2f" % r.get("speedup", float("nan"))),
                "%11s" % ("fail" if ce == 0.0 else ("-" if ce is None else "%.2f" % ce)),
            ]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
