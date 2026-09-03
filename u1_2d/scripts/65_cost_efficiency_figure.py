"""Cost-efficiency figure: what the diffusion seed saves against classical HMC,
as a single dimensionless number, vs beta and volume. The u1 twin of
`u2_2d/scripts/57_cost_efficiency_figure.py` -- same definitions, same
conventions, adapted to u1's existing scan output rather than re-deriving them
independently, so a reader who has seen one understands the other for free.

DEFINITION (identical to u2's, restated for a reader who starts here).
`35_crossover_window.py` already merges u1's thermalization scans
(`out/u1_2d/thermalization/*/*_summary.json`) into
`out/u1_2d/thermalization/crossover_window.json`, one row per (L, beta) with
t_therm for the diffusion-seeded / cold-start / hot-start arms (`seed`,
`cold`, `hot`), the classical baseline's `interval` (2 tau_int of an
EQUILIBRATED chain of the same HMC+instanton sampler -- the number of
trajectories a chain that is already thermalized needs between two
independent configurations), and the precomputed `speedup`. Unlike u2, u1's
classical baseline of record already includes the winding/instanton update
(NARRATIVE / CLAUDE.md: "HMC + winding update, not PTBC and not plain HMC"),
so there is only one round here, not a plain/winding pair.

Two ratios, both dimensionless:

  FIRST-CONFIGURATION SPEEDUP  (field: "speedup", already computed)
      speedup = min(t_therm(cold), t_therm(hot)) / t_therm(seed)
    Starting a chain from scratch, how many fewer trajectories does the seed
    need to reach equilibrium than a naive HMC chain does? Goes to infinity
    (a LOWER BOUND, drawn as an open triangle) once cold/hot HMC never
    equilibrates in budget at all ("HMC dead").

  STEADY-STATE COST-EFFICIENCY  (computed here: "cost_efficiency")
      cost_efficiency = interval / t_therm(seed)
    Against a classical chain that is ALREADY running and equilibrated --
    the best case classical HMC can offer -- how does the seed's one-shot
    cost compare to the steady-state cost of pulling one more independent
    sample out of it? > 1 beats even an idealized always-equilibrated
    classical chain; < 1 is slower than simply continuing to run one.

Training coverage is shaded past beta = 60, the top of u1's dense random-beta
training range (`configs/v2.yaml` / `v3_scale.yaml`, `random_rungs`
`beta_max: 60.0` at every volume; see CLAUDE.md's u1 sampler-step and
observable-scan sections, which both key off this same boundary). Override
with --train-beta-max for a checkpoint trained on a different range.

Consumes existing JSON only -- no new HMC.

    python u1_2d/scripts/65_cost_efficiency_figure.py
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
DEFAULT_TRAIN_BETA_MAX = 60.0


def load_rows(paths: list[str]) -> list[dict]:
    rows: dict[tuple, dict] = {}
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        candidates = data["rows"] if isinstance(data, dict) and "rows" in data else data
        for r in candidates:
            if "beta" in r and "seed" in r and "interval" in r:
                rows[(r.get("L"), r["beta"])] = r
    return list(rows.values())


def cost_efficiency(row: dict) -> float | None:
    interval = row.get("interval")
    if not interval or not math.isfinite(interval):
        return None
    seed_t = row.get("seed")
    if seed_t is None or math.isinf(seed_t):
        return 0.0
    return interval / max(seed_t, 1.0)


def draw_metric(ax, rows_by_L, value_fn, ylabel, log_floor, log_ceil):
    for L in sorted(rows_by_L):
        colour = VOLUME_COLOUR.get(L, "#444444")
        rows = sorted(rows_by_L[L], key=lambda r: r["beta"])
        xs, ys, lo_xs, hi_xs = [], [], [], []
        for r in rows:
            v = value_fn(r)
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
            ax.plot(xs, ys, color=colour, lw=1.8, marker="o", ms=4.5,
                    markeredgecolor="white", markeredgewidth=0.4, zorder=4,
                    label="L = %d" % L)
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


def shade_training_range(ax, rows_by_L, train_max):
    betas = sorted({r["beta"] for rows in rows_by_L.values() for r in rows})
    inside = [b for b in betas if b <= train_max]
    outside = [b for b in betas if b > train_max]
    if not inside or not outside:
        return
    edge = math.sqrt(max(inside) * min(outside))
    xlo, xhi = ax.get_xlim()
    ax.axvspan(edge, xhi, facecolor="none", edgecolor="#5a3a8a", hatch="///",
              lw=0.0, alpha=0.5, zorder=1)
    ax.axvline(edge, color="#5a3a8a", lw=1.1, ls=(0, (3, 2)), zorder=3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", nargs="+",
                        default=["out/u1_2d/thermalization/crossover_window.json"])
    parser.add_argument("--train-beta-max", type=float, default=DEFAULT_TRAIN_BETA_MAX)
    parser.add_argument("--label", default="deployed checkpoint (score_net.pt)")
    parser.add_argument("--out", default="out/u1_2d/figures/fig65_cost_efficiency.png")
    args = parser.parse_args()

    rows = load_rows(args.paths)
    if not rows:
        print("no crossover-window json found under " + ", ".join(args.paths))
        return 1
    rows_by_L: dict = {}
    for r in rows:
        rows_by_L.setdefault(r.get("L"), []).append(r)

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(6.9, 6.4), sharex=True,
        gridspec_kw={"height_ratios": (1.0, 1.0), "hspace": 0.10})

    draw_metric(ax_top, rows_by_L, lambda r: r.get("speedup"),
               "first-configuration speedup\n" r"$\min(t_{cold},t_{hot})\,/\,t_{seed}$",
               log_floor=0.3, log_ceil=1000.0)
    draw_metric(ax_bot, rows_by_L, cost_efficiency,
               "steady-state cost-efficiency\n" r"$\mathrm{interval}\,/\,t_{seed}$",
               log_floor=0.03, log_ceil=10.0)
    for ax in (ax_top, ax_bot):
        shade_training_range(ax, rows_by_L, args.train_beta_max)
    ax_bot.set_xlabel(r"fine coupling  $\beta$", fontsize=10, color=INK)

    handles = [Line2D([], [], color=c, lw=2.0, marker="o", ms=5, label="L = %d" % L)
               for L, c in sorted(VOLUME_COLOUR.items()) if L in rows_by_L]
    handles.append(Line2D([], [], color=INK, lw=1.1, ls=(0, (1, 1)),
                          label="breakeven (=1)"))
    handles.append(Line2D([], [], color=MUTED, marker="v", ms=7, lw=0,
                          markerfacecolor="none", markeredgewidth=1.4,
                          label="seed itself fails to thermalize"))
    handles.append(Line2D([], [], color=MUTED, marker="^", ms=7, lw=0,
                          markerfacecolor="none", markeredgewidth=1.4,
                          label="classical arm never thermalizes (lower bound)"))
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.05),
              fontsize=8, frameon=False, ncol=3, labelcolor=INK)

    fig.suptitle("Cost efficiency of a diffusion seed vs classical HMC   ("
                 + args.label + ")", fontsize=11.5, color=INK, x=0.02, ha="left")
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote " + str(dest))

    print("\ncost-efficiency by coupling")
    print("  L".rjust(4) + "beta".rjust(11) + "speedup".rjust(11) + "cost_eff".rjust(11))
    for L in sorted(rows_by_L):
        for r in sorted(rows_by_L[L], key=lambda r: r["beta"]):
            ce = cost_efficiency(r)
            print("  " + "".join([
                str(L).rjust(4), "%11.2f" % r["beta"],
                "%11s" % ("inf" if r.get("speedup_is_bound") else "%.2f" % r.get("speedup", float("nan"))),
                "%11s" % ("fail" if ce == 0.0 else ("-" if ce is None else "%.2f" % ce)),
            ]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
