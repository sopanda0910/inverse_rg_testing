"""Autocorrelation Gamma(delta) vs separation delta for fast and slow observables.

For each rung of the thermalization benchmark (05_hmc_thermalization.py) this
computes the normalized autocorrelation function of the per-trajectory series
of every requested observable -- Wilson loops (plaquette, 2x2, 4x4, 6x6) as the
fast/local modes, topological charge Q and Q^2 as the slow modes -- on the
equilibrated window (trajectories after that start's measured t_therm; second
half of the series when the start never thermalizes), per chain, then averaged
over chains with SEM error bars.

Estimators:
  - generic observable:  Gamma(delta) = <(x_t - mu)(x_{t+delta} - mu)> / var(x),
    per chain; a frozen (zero-variance) chain is perfectly correlated, Gamma = 1
  - Q (paper-style, Eq. 7 of the NTHMC reference):  Gamma(delta) =
    <Q_t Q_{t+delta}> / <Q^2>, no mean subtraction (<Q> = 0 in equilibrium),
    normalized by the ensemble <Q^2> -- a chain frozen in one sector shows a
    flat Gamma instead of a 0/0 artifact

Figures per observable: {obs}_autocorrelation_by_beta.png (panels = rungs,
curves = starts) and {obs}_autocorrelation_by_start.png (panels = starts,
curves = rungs). Plus one combined figure, autocorrelation_modes.png (rows =
starts, cols = rungs, curves = observables), for the slow-vs-fast comparison.

Reads the {label}_series.npz / {label}_summary.json the benchmark saves; no
HMC is run. Q and wilson_6x6 require series saved after 05 started recording
them; observables missing from a series file are skipped.

    python diffusion/scripts/11_autocorrelation.py --dir out/diffusion/demo/thermalization
    python diffusion/scripts/11_autocorrelation.py --obs plaquette,Q --max-lag 40
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.validate.stats import normalized_autocorrelation

GEN_COLOR = "#2a78d6"
HOT_COLOR = "#d64550"
COLD_COLOR = "#8a63c9"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

STARTS = ["diffusion seed", "cold start", "hot start"]
START_STYLE = {
    "diffusion seed": (GEN_COLOR, "o", "-"),
    "cold start": (COLD_COLOR, "D", (0, (4, 2))),
    "hot start": (HOT_COLOR, "^", "-"),
}
OBS_ORDER = ["plaquette", "wilson_2x2", "wilson_4x4", "wilson_6x6", "Q", "Q^2"]
LOOP_OBS = ["plaquette", "wilson_2x2", "wilson_4x4", "wilson_6x6"]
OBS_STYLE = dict(
    zip(LOOP_OBS, [(tuple(c), m) for c, m in
                   zip(plt.cm.Blues(np.linspace(0.4, 0.95, len(LOOP_OBS))),
                       ["o", "s", "^", "D"])])
) | {"Q": (HOT_COLOR, "v"), "Q^2": ("#f5a623", "P")}
OBS_FILENAME = {"Q^2": "Q2"}


def frozen_chains(window: np.ndarray) -> np.ndarray:
    return np.all(window == window[0], axis=0)


def gamma_chains(window: np.ndarray, obs: str, max_lag: int) -> np.ndarray:
    """Per-chain Gamma(delta), [n_lags + 1, B]."""
    n = window.shape[0]
    max_lag = max(0, min(max_lag, n - 2))
    if obs == "Q":
        denom = (window**2).mean()
        if denom < 1e-12:
            return np.ones((max_lag + 1, window.shape[1]))
        gamma = np.empty((max_lag + 1, window.shape[1]))
        gamma[0] = (window**2).mean(axis=0) / denom
        for lag in range(1, max_lag + 1):
            gamma[lag] = (window[:-lag] * window[lag:]).mean(axis=0) / denom
        return gamma
    gamma = normalized_autocorrelation(window, max_lag)
    gamma[:, frozen_chains(window)] = 1.0
    return gamma


def equilibrated_window(series: np.ndarray, t_therm: float | None) -> tuple[np.ndarray, bool]:
    """Post-thermalization window [T', B] and whether the start ever thermalized.
    A never-thermalizing start falls back to the second half of its series."""
    thermalized = t_therm is not None and math.isfinite(t_therm)
    discard = int(t_therm) if thermalized else series.shape[0] // 2
    return series[discard:], thermalized


def load_rung(therm_dir: Path, label: str, obs_list: list[str], max_lag: int) -> dict:
    summary = json.loads((therm_dir / f"{label}_summary.json").read_text(encoding="utf-8"))
    series = np.load(therm_dir / f"{label}_series.npz")
    rung = {"label": label, "beta": summary["beta"], "lattice_size": summary["lattice_size"],
            "obs": {}}
    for obs in obs_list:
        window_key = "Q^2" if obs == "Q" else obs
        starts = {}
        for start in STARTS:
            key = f"{start}|{obs}"
            if key not in series:
                continue
            window, thermalized = equilibrated_window(
                series[key], summary["t_therm"][start].get(window_key)
            )
            gamma = gamma_chains(window, obs, max_lag)
            starts[start] = {
                "gamma": gamma.mean(axis=1),
                "sem": gamma.std(axis=1, ddof=1) / math.sqrt(gamma.shape[1]),
                "thermalized": thermalized,
                "window_length": window.shape[0],
                "n_chains": window.shape[1],
                "n_frozen": int(frozen_chains(window).sum()),
            }
        if starts:
            rung["obs"][obs] = starts
    return rung


def style_axis(ax) -> None:
    ax.grid(color=GRID_COLOR, lw=0.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)


def start_label(start: str, data: dict) -> str:
    return start if data["thermalized"] else f"{start} (never thermalizes)"


def plot_by_beta(rungs: list[dict], obs: str, out_path: Path) -> None:
    with_obs = [r for r in rungs if obs in r["obs"]]
    fig, axes = plt.subplots(1, len(with_obs), figsize=(4.4 * len(with_obs), 4.2),
                             sharey=True, squeeze=False)
    for ax, rung in zip(axes.flat, with_obs):
        for start in STARTS:
            if start not in rung["obs"][obs]:
                continue
            data = rung["obs"][obs][start]
            color, marker, ls = START_STYLE[start]
            x = np.arange(len(data["gamma"]))
            ax.errorbar(x, data["gamma"], yerr=data["sem"], color=color, ls=ls,
                        marker=marker, ms=3.5, lw=1.3, capsize=2, elinewidth=0.9,
                        label=start_label(start, data))
        ax.axhline(0.0, color=INK, lw=0.8, ls=(0, (1, 1)))
        ax.set_title(rf"L={rung['lattice_size']}, $\beta$={rung['beta']:g}",
                     fontsize=10, color=INK)
        ax.set_xlabel(r"separation $\delta$ (HMC trajectories)", fontsize=9)
        ax.legend(fontsize=8, frameon=False)
        style_axis(ax)
    axes.flat[0].set_ylabel(rf"autocorrelation $\Gamma(\delta)$ of {obs}", fontsize=9)
    fig.suptitle(f"{obs} autocorrelation on the equilibrated window, by start", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_by_start(rungs: list[dict], obs: str, out_path: Path) -> None:
    ordered = sorted((r for r in rungs if obs in r["obs"]), key=lambda r: r["beta"])
    shades = plt.cm.Blues(np.linspace(0.45, 0.9, len(ordered)))
    markers = ["o", "s", "^", "D", "v", "P"]
    fig, axes = plt.subplots(1, len(STARTS), figsize=(4.4 * len(STARTS), 4.2),
                             sharey=True, squeeze=False)
    for ax, start in zip(axes.flat, STARTS):
        for shade, marker, rung in zip(shades, markers, ordered):
            if start not in rung["obs"][obs]:
                continue
            data = rung["obs"][obs][start]
            x = np.arange(len(data["gamma"]))
            label = rf"$\beta$={rung['beta']:g}, L={rung['lattice_size']}"
            if not data["thermalized"]:
                label += " (never thermalizes)"
            ax.errorbar(x, data["gamma"], yerr=data["sem"], color=shade, marker=marker,
                        ms=3.5, lw=1.3, capsize=2, elinewidth=0.9, label=label)
        ax.axhline(0.0, color=INK, lw=0.8, ls=(0, (1, 1)))
        ax.set_title(start, fontsize=10, color=INK)
        ax.set_xlabel(r"separation $\delta$ (HMC trajectories)", fontsize=9)
        ax.legend(fontsize=8, frameon=False)
        style_axis(ax)
    axes.flat[0].set_ylabel(rf"autocorrelation $\Gamma(\delta)$ of {obs}", fontsize=9)
    fig.suptitle(f"{obs} autocorrelation on the equilibrated window, by coupling", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_modes(rungs: list[dict], obs_list: list[str], out_path: Path) -> None:
    """Slow vs fast modes: rows = starts, cols = rungs, curves = observables."""
    fig, axes = plt.subplots(len(STARTS), len(rungs),
                             figsize=(4.4 * len(rungs), 3.4 * len(STARTS)),
                             sharex=True, sharey=True, squeeze=False)
    for i, start in enumerate(STARTS):
        for j, rung in enumerate(rungs):
            ax = axes[i, j]
            for obs in obs_list:
                data = rung["obs"].get(obs, {}).get(start)
                if data is None:
                    continue
                color, marker = OBS_STYLE[obs]
                x = np.arange(len(data["gamma"]))
                ax.errorbar(x, data["gamma"], yerr=data["sem"], color=color,
                            marker=marker, ms=3, lw=1.2, elinewidth=0.8, label=obs)
            ax.axhline(0.0, color=INK, lw=0.8, ls=(0, (1, 1)))
            if i == 0:
                ax.set_title(rf"L={rung['lattice_size']}, $\beta$={rung['beta']:g}",
                             fontsize=10, color=INK)
            if j == 0:
                ax.set_ylabel(f"{start}\n" + r"$\Gamma(\delta)$", fontsize=9)
            if i == len(STARTS) - 1:
                ax.set_xlabel(r"separation $\delta$ (HMC trajectories)", fontsize=9)
            style_axis(ax)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels),
               fontsize=9, frameon=False)
    fig.suptitle("Fast modes (Wilson loops) vs slow modes (topology): "
                 "autocorrelation on the equilibrated window", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="out/diffusion/demo/thermalization",
                        help="thermalization benchmark output directory")
    parser.add_argument("--obs", default="all",
                        help="comma-separated observables, or 'all' "
                        f"(known: {', '.join(OBS_ORDER)})")
    parser.add_argument("--max-lag", type=int, default=20, dest="max_lag")
    parser.add_argument("--out", default=None,
                        help="output directory (default: --dir)")
    args = parser.parse_args()
    therm_dir = Path(args.dir)
    out_dir = Path(args.out) if args.out else therm_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    obs_list = OBS_ORDER if args.obs == "all" else [v.strip() for v in args.obs.split(",")]
    labels = sorted(p.name[: -len("_series.npz")] for p in therm_dir.glob("*_series.npz"))
    if not labels:
        raise SystemExit(f"no *_series.npz under {therm_dir}; run 05_hmc_thermalization.py first")

    rungs = [load_rung(therm_dir, label, obs_list, args.max_lag) for label in labels]
    rungs = [r for r in rungs if r["obs"]]
    if not rungs:
        raise SystemExit(f"none of {obs_list} found in any series file")
    rungs.sort(key=lambda r: r["beta"])
    present = [obs for obs in obs_list if any(obs in r["obs"] for r in rungs)]

    for obs in present:
        stem = OBS_FILENAME.get(obs, obs)
        plot_by_beta(rungs, obs, out_dir / f"{stem}_autocorrelation_by_beta.png")
        plot_by_start(rungs, obs, out_dir / f"{stem}_autocorrelation_by_start.png")
        np.savez_compressed(
            out_dir / f"{stem}_autocorrelation.npz",
            **{f"{r['label']}|{start}|{field}": data[field]
               for r in rungs for start, data in r["obs"].get(obs, {}).items()
               for field in ("gamma", "sem")},
        )
    if len(present) > 1:
        plot_modes(rungs, present, out_dir / "autocorrelation_modes.png")

    for rung in rungs:
        print(f"{rung['label']} (beta={rung['beta']:g}, L={rung['lattice_size']})")
        for obs in present:
            for start in STARTS:
                data = rung["obs"].get(obs, {}).get(start)
                if data is None:
                    continue
                tags = [] if data["thermalized"] else ["never thermalizes"]
                if data["n_frozen"]:
                    tags.append(f"{data['n_frozen']}/{data['n_chains']} chains frozen")
                tag = f" ({', '.join(tags)})" if tags else ""
                print(f"  {obs:>10} | {start:<14}: Gamma({len(data['gamma']) - 1}) = "
                      f"{data['gamma'][-1]:+.3f} +- {data['sem'][-1]:.3f}{tag}")
    print(f"\nmodes figure: {out_dir / 'autocorrelation_modes.png'}")


if __name__ == "__main__":
    main()
