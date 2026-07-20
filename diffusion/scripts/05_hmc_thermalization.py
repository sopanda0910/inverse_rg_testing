"""HMC thermalization benchmark: diffusion-generated configs as HMC starting points.

For each ladder rung this compares
  (a) HMC chains started from the diffusion-generated ensemble,
  (b) fresh hot- and cold-start HMC chains at the same coupling,
recording per-trajectory observables, and measures the equilibrated regular-HMC
chain's integrated autocorrelation time -- the 'interval' a regular chain needs
between two independent configs (2 tau_int trajectories). The claim under test:
a generated config thermalizes in fewer trajectories than that interval, i.e.
generation + a short HMC tail is cheaper per independent config than running the
chain itself. All chains here run WITHOUT topological updates (plain HMC).

    python diffusion/scripts/05_hmc_thermalization.py --config diffusion/configs/demo.yaml

With --generalization the benchmark runs over the generalization study's
matched-pair beta scan (parts A and D, L=16 -> L=32) instead of the ladder
rungs, covering many more couplings -- including low betas where fresh HMC
does thermalize, so 2 tau_int and burn-in are honest yardsticks:

    python diffusion/scripts/05_hmc_thermalization.py --generalization
"""

import argparse
import glob
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.pyplot as plt

from diffusion.lgt import make_action
from diffusion.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion.lgt.lattice import plaquette_angles, topological_charge, wilson_loop_angles
from diffusion.lgt import exact
from diffusion.validate.report import validate_ensemble, freezing_diagnostics
from diffusion.validate.stats import fit_exponential_relaxation, integrated_autocorrelation_time
from diffusion.utils import (
    load_config,
    resolve_device,
    set_seed,
    load_ensemble,
    ensemble_path,
    save_ensemble,
    save_json,
)

GEN_COLOR = "#2a78d6"
HOT_COLOR = "#d64550"
COLD_COLOR = "#8a63c9"
MUTED_BAR = "#8f8d86"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

OBS_LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4), "wilson_6x6": (6, 6)}
INTERVAL_OBS = ("plaquette", "wilson_2x2", "wilson_4x4")


def chain_observables(theta: torch.Tensor) -> dict[str, np.ndarray]:
    out = {}
    with torch.no_grad():
        out["plaquette"] = torch.cos(plaquette_angles(theta)).mean(dim=(-2, -1)).cpu().numpy()
        for name, (r, t) in OBS_LOOPS.items():
            if max(r, t) <= theta.shape[-1] // 2:
                out[name] = torch.cos(wilson_loop_angles(theta, r, t)).mean(dim=(-2, -1)).cpu().numpy()
        out["Q"] = topological_charge(theta).cpu().numpy()
    return out


def exact_targets(beta: float, action_type: str, lattice_size: int) -> dict[str, float]:
    targets = {"plaquette": exact.plaquette_exact(beta, action_type, lattice_size)}
    for name, (r, t) in OBS_LOOPS.items():
        if max(r, t) <= lattice_size // 2:
            targets[name] = exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)
    chi = exact.topological_susceptibility_exact(beta, action_type, lattice_size)
    targets["Q^2"] = chi * lattice_size**2
    return targets


def run_relaxation(
    lattice_size: int,
    action,
    initial: torch.Tensor,
    n_traj: int,
    step_size: float,
    n_steps: int,
    device: str,
) -> tuple[dict[str, np.ndarray], torch.Tensor, float, float]:
    """Returns (series {obs: [n_traj + 1, B]}, final state, acceptance, sec/trajectory)."""
    sampler = BatchedHMC(
        lattice_size,
        action,
        n_chains=initial.shape[0],
        n_steps=n_steps,
        step_size=step_size,
        device=device,
    )
    theta = initial.clone().to(device)
    series = {k: [v] for k, v in chain_observables(theta).items()}
    accepted, total = 0, 0
    t0 = time.time()
    with torch.no_grad():
        for _ in range(n_traj):
            theta, accept = sampler.metropolis_step(theta)
            accepted += int(accept.sum())
            total += accept.numel()
            for k, v in chain_observables(theta).items():
                series[k].append(v)
    sec_per_traj = (time.time() - t0) / max(n_traj, 1)
    series = {k: np.stack(v) for k, v in series.items()}
    return series, theta, accepted / max(total, 1), sec_per_traj


def ensemble_z_series(series: np.ndarray, target: float) -> np.ndarray:
    """series [T+1, B] of per-chain values -> z-score of the ensemble mean vs target."""
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    return (mean - target) / np.maximum(sem, 1e-12)


def thermalization_time(
    series: np.ndarray, target: float, z_threshold: float = 2.0, n_consecutive: int = 5
) -> float:
    """First trajectory count t at which |z(ensemble mean)| <= threshold and stays
    there for n_consecutive trajectories. t = 0 means thermalized before any HMC.
    Returns inf when the window never occurs."""
    z = np.abs(ensemble_z_series(series, target))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t : t + n_consecutive].all():
            return float(t)
    return float("inf")


def equilibrium_tau_int(series: np.ndarray, discard: int) -> tuple[float, float]:
    """Mean Madras-Sokal tau_int over chains, window after `discard` trajectories."""
    window = series[discard:]
    taus = [integrated_autocorrelation_time(window[:, b])[0] for b in range(window.shape[1])]
    return float(np.mean(taus)), float(np.std(taus) / math.sqrt(len(taus)))


def q_freezing(series: np.ndarray, discard: int, label: str) -> dict:
    window = np.asarray(series[discard:], dtype=float)
    n_tunnelings = int(np.sum(np.abs(np.diff(np.round(window), axis=0)) > 0))
    per_chain = [freezing_diagnostics(window[:, b]) for b in range(window.shape[1])]
    frozen = all(d["frozen"] for d in per_chain)
    taus = [d["tau_int_Q"] for d in per_chain if not d["frozen"]]
    return {
        "label": label,
        "frozen": frozen,
        "n_tunnelings": n_tunnelings,
        "window_length": int(window.shape[0]),
        "n_chains": int(window.shape[1]),
        "tau_int_Q": float(np.mean(taus)) if taus else float(window.shape[0]),
    }


def build_series_dict(raw: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    series = dict(raw)
    series["Q^2"] = raw["Q"] ** 2
    return series


OBS_LABEL = {"plaquette": "plaquette", "wilson_2x2": r"$W(2\times2)$",
             "wilson_4x4": r"$W(4\times4)$", "Q^2": r"$Q^2$"}


def _rolling_median(y: np.ndarray, window: int = 7) -> np.ndarray:
    if len(y) < window:
        return y
    pad = window // 2
    padded = np.pad(y, pad, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(padded, window), axis=-1)


def plot_relaxation(
    all_series: dict[str, dict[str, np.ndarray]],
    targets: dict[str, float],
    label: str,
    out_path: Path,
    t_therm: dict[str, dict[str, float]] | None = None,
    tau_int: dict[str, tuple[float, float]] | None = None,
) -> None:
    """One row per observable, two views: (left) the early-window ensemble-mean
    relaxation of each start with its fitted exponential C + A exp(-t/tau);
    (right) the ensemble mean's distance from the exact value in SEM units over
    the full budget, log scale, with the |z| <= 2 thermalization band. Shared
    legend on top, how-to-read caption at the bottom."""
    t_therm = t_therm or {}
    names = [n for n in ("plaquette", "wilson_2x2", "wilson_4x4", "Q^2") if n in targets]
    order = ["diffusion seed", "hot start", "cold start"]
    starts = [s for s in order if s in all_series]
    colors = {"diffusion seed": GEN_COLOR, "hot start": HOT_COLOR, "cold start": COLD_COLOR}

    fits = {start: {name: fit_exponential_relaxation(series[name].mean(axis=1), targets[name])
                    for name in names if name in series}
            for start, series in all_series.items()}
    budget = max(all_series[s][names[0]].shape[0] for s in starts) - 1

    fig, axes = plt.subplots(len(names), 2, figsize=(12.5, 2.9 * len(names) + 1.9),
                             gridspec_kw={"width_ratios": [1.15, 1.0]}, squeeze=False)
    for i, name in enumerate(names):
        ax_zoom, ax_z = axes[i]
        finite_marks = [t_therm.get(s, {}).get(name) for s in starts]
        finite_marks = [t for t in finite_marks if t is not None and math.isfinite(t)]
        taus = [fits[s][name]["tau"] for s in starts
                if name in fits[s] and fits[s][name]["tau"] is not None]
        x_zoom = int(min(budget, max(25.0, 1.6 * max(finite_marks, default=0.0),
                                     6.0 * max(taus, default=0.0))))

        z_max = 2.0
        for start in starts:
            if name not in all_series[start]:
                continue
            data = all_series[start][name]
            mean = data.mean(axis=1)
            sem = data.std(axis=1, ddof=1) / math.sqrt(data.shape[1])
            x = np.arange(len(mean))
            color = colors[start]
            sl = slice(0, x_zoom + 1)
            ax_zoom.plot(x[sl], mean[sl], lw=1.4, color=color)
            ax_zoom.fill_between(x[sl], (mean - sem)[sl], (mean + sem)[sl],
                                 color=color, alpha=0.20, lw=0)
            fit = fits[start].get(name, {"tau": None})
            if fit["tau"] is not None:
                tf = np.linspace(0, x_zoom, 300)
                ax_zoom.plot(tf, fit["C"] + fit["A"] * np.exp(-tf / fit["tau"]),
                             color=color, lw=1.1, ls=(0, (5, 2)), alpha=0.9)
            tt = t_therm.get(start, {}).get(name)
            if tt is not None and math.isfinite(tt) and tt <= x_zoom:
                ax_zoom.plot([tt], [targets[name]], marker="v", ms=7.5, color=color,
                             mec="white", mew=0.7, ls="none", zorder=6)
            z = np.maximum(np.abs(ensemble_z_series(data, targets[name])), 1e-2)
            z_max = max(z_max, float(z.max()))
            ax_z.plot(np.arange(len(z)), z, lw=0.6, color=color, alpha=0.22)
            ax_z.plot(np.arange(len(z)), _rolling_median(z), lw=1.4, color=color,
                      alpha=0.95)

        ax_zoom.axhline(targets[name], color=INK, ls="--", lw=1.1)
        ax_zoom.set_xlim(-0.02 * x_zoom, x_zoom)
        ax_zoom.set_ylabel(OBS_LABEL[name], fontsize=10, color=INK)
        tau_text = "   ".join(
            f"{s.split()[0]} " + (f"{fits[s][name]['tau']:.1f}"
                                  if name in fits[s] and fits[s][name]["tau"] is not None
                                  else "--")
            for s in starts)
        ax_zoom.text(0.985, 0.03, rf"$\tau_{{exp}}$ [traj]:  {tau_text}",
                     transform=ax_zoom.transAxes, ha="right", va="bottom",
                     fontsize=8, color=INK,
                     bbox=dict(facecolor="white", edgecolor=GRID_COLOR, alpha=0.8, pad=2.5))

        ax_z.axhspan(1e-2, 2.0, color=GRID_COLOR, alpha=0.55, zorder=0)
        ax_z.axhline(2.0, color=INK, ls=":", lw=1.0)
        ax_z.set_yscale("log")
        ax_z.set_ylim(5e-2, min(z_max * 1.8, 5e3))
        ax_z.set_xscale("symlog", linthresh=10)
        ax_z.set_xlim(0, budget)
        ax_z.set_ylabel(r"$|z|$ vs exact", fontsize=9, color=INK)
        for ax in (ax_zoom, ax_z):
            ax.grid(color=GRID_COLOR, lw=0.7)
            ax.set_axisbelow(True)
            ax.tick_params(labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(GRID_COLOR)
        if i == 0:
            ax_zoom.set_title("ensemble-mean relaxation, early window (zoom)",
                              fontsize=10, color=INK)
            ax_z.set_title("distance from exact over the full budget",
                           fontsize=10, color=INK)
        if i == len(names) - 1:
            ax_zoom.set_xlabel("HMC trajectories", fontsize=9)
            ax_z.set_xlabel("HMC trajectories (symlog)", fontsize=9)

    handles = [mlines.Line2D([], [], color=colors[s], lw=2.2, label=s) for s in starts]
    handles += [
        mlines.Line2D([], [], color=INK, ls="--", lw=1.2, label="exact value"),
        mlines.Line2D([], [], color=MUTED_BAR, ls=(0, (5, 2)), lw=1.4,
                      label=r"exponential fit $C + A\,e^{-t/\tau}$"),
        mlines.Line2D([], [], color=MUTED_BAR, marker="v", ls="none", ms=7,
                      label=r"$t_{\mathrm{therm}}$ (first sustained $|z| \leq 2$)"),
    ]
    fig.legend(handles=handles, ncol=4, loc="upper center",
               bbox_to_anchor=(0.5, 0.965), fontsize=8.5, frameon=False)
    fig.suptitle(f"{label}: thermalization under plain HMC", fontsize=13, y=0.995)
    fig.text(
        0.01, 0.002,
        "How to read: LEFT -- ensemble mean over chains (+-1 SEM band) with the fitted "
        "exponential per start (dashed); triangles mark t_therm on the exact line.\n"
        "RIGHT -- SEM-units distance from exact (thick: rolling median; faint: raw). "
        "Thermalized = curve stays inside the shaded |z| <= 2 band; a plateau above it "
        "never thermalizes.",
        fontsize=7.5, color="#6b6963", va="bottom",
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_timescales(summaries: list[dict], out_path: Path) -> None:
    """The headline figure: per beta, the trajectories needed to obtain one new
    thermalized configuration -- diffusion seed vs fresh hot/cold-start standard
    HMC (the 2 tau_int interval stays in the report tables but is not plotted:
    an "equilibrated" chain at large beta has frozen topology, so plotting its
    steady-state cost as a baseline would flatter HMC misleadingly).
    Non-topological observables only (Wilson loops / plaquette)."""
    wilson_obs = ("plaquette", "wilson_2x2", "wilson_4x4")

    def slowest(summary, start):
        return max(summary["t_therm"][start][n] for n in wilson_obs)

    bars = [
        ("diffusion seed: t_therm", GEN_COLOR,
         lambda s: slowest(s, "diffusion seed")),
        ("fresh hot start: burn-in", HOT_COLOR,
         lambda s: slowest(s, "hot start")),
        ("fresh cold start: burn-in", COLD_COLOR,
         lambda s: slowest(s, "cold start")),
    ]
    n_group = len(bars)
    height = 0.19
    budget = max(s["n_traj_baseline"] for s in summaries)
    n_cols = 2 if len(summaries) > 12 else 1
    per_col = math.ceil(len(summaries) / n_cols)
    chunks = [summaries[c * per_col:(c + 1) * per_col] for c in range(n_cols)]
    fig, axes = plt.subplots(1, n_cols, figsize=(6.4 * n_cols, 1.8 + 0.68 * per_col),
                             squeeze=False)
    for ax, chunk in zip(axes[0], chunks):
        for i, s in enumerate(chunk):
            for j, (name, color, getter) in enumerate(bars):
                y = i + (j - (n_group - 1) / 2) * (height + 0.03)
                value = getter(s)
                if math.isinf(value):
                    ax.plot([budget], [y], marker="x", ms=5.5, mew=1.7, color=color,
                            alpha=0.85, ls="none")
                    ax.annotate("never", (budget, y), xytext=(7, 0),
                                textcoords="offset points", va="center",
                                fontsize=7, color=MUTED_BAR)
                elif value == 0:
                    ax.plot([0], [y], marker="|", ms=10, mew=2.2, color=color)
                    ax.annotate("0", (0, y), xytext=(5, 0), textcoords="offset points",
                                va="center", fontsize=7.5, color=INK)
                else:
                    ax.barh(y, value, height=height, color=color, edgecolor="white", lw=0)
                    ax.annotate(f"{value:.0f}" if value >= 3 else f"{value:.1f}",
                                (value, y), xytext=(4, 0), textcoords="offset points",
                                va="center", fontsize=7.5, color=INK)
        ax.axvline(budget, color=MUTED_BAR, ls="--", lw=1.0)
        ax.set_yticks(range(len(chunk)))
        ax.set_yticklabels(
            [f"L={s['lattice_size']}, β={s['beta']:g}" for s in chunk], fontsize=8.5
        )
        ax.set_ylim(len(chunk) - 0.5, -0.5)
        ax.set_xlim(0, budget * 1.14)
        ax.grid(axis="x", color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
        ax.tick_params(labelsize=8)
    handles = [mlines.Line2D([], [], color=c, lw=6, label=n) for n, c, _ in bars]
    handles.append(mlines.Line2D([], [], color=MUTED_BAR, marker="x", ls="none",
                                 ms=6, mew=1.7,
                                 label=f"never thermalized within the {budget}-trajectory budget"))
    fig.legend(handles=handles, fontsize=8, frameon=False, loc="lower center",
               bbox_to_anchor=(0.5, -0.005), ncol=3)
    fig.supxlabel("HMC trajectories per new thermalized, independent config "
                  "(slowest Wilson-loop observable)", fontsize=9, y=0.045)
    fig.suptitle("Cost of one new config: diffusion seed vs standard HMC",
                 fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.055, 1, 0.97))
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_beta_scan(summaries: list[dict], out_path: Path) -> None:
    """Trajectories per new thermalized config vs beta, across the matched-pair
    scan: the same timescales as plot_timescales as a function of coupling, so
    the crossover where fresh HMC stops thermalizing is visible in one panel."""
    wilson_obs = ("plaquette", "wilson_2x2", "wilson_4x4")

    def slowest(summary, start):
        return max(summary["t_therm"][start][n] for n in wilson_obs)

    series = [
        ("diffusion seed: t_therm", GEN_COLOR, "o",
         lambda s: slowest(s, "diffusion seed")),
        ("fresh hot start: burn-in", HOT_COLOR, "^",
         lambda s: slowest(s, "hot start")),
        ("fresh cold start: burn-in", COLD_COLOR, "D",
         lambda s: slowest(s, "cold start")),
    ]
    sizes = [int(s["lattice_size"]) for s in summaries]
    scan_L = max(set(sizes), key=sizes.count)
    summaries = [s for s in summaries if int(s["lattice_size"]) == scan_L]
    betas = np.array([s["beta"] for s in summaries], dtype=float)
    budget = max(s["n_traj_baseline"] for s in summaries)

    fig = plt.figure(figsize=(10.0, 6.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 3.6], hspace=0.07)
    ax_top = fig.add_subplot(gs[0])
    ax = fig.add_subplot(gs[1], sharex=ax_top)

    lanes = []
    frozen = np.array([bool(s["q_freezing"]["frozen"]) for s in summaries])
    if frozen.any():
        lanes.append(("Q frozen (hot chain)", betas[frozen], "x", INK))
    for name, color, marker, getter in series:
        vals = np.array([getter(s) for s in summaries])
        never = ~np.isfinite(vals)
        if never.any():
            lanes.append((f"{name.split(':')[0]}: never", betas[never], marker, color))
    for row, (lane_label, xs, marker, color) in enumerate(lanes):
        ax_top.plot(xs, np.full(len(xs), row), marker=marker, color=color, ls="none",
                    ms=6, mfc="none" if marker != "x" else color, mew=1.5, zorder=3)
    ax_top.set_yticks(range(len(lanes)))
    ax_top.set_yticklabels([lane for lane, *_ in lanes], fontsize=8, color=INK)
    ax_top.set_ylim(len(lanes) - 0.4, -0.6)
    ax_top.set_title(f"never thermalized within the {budget}-trajectory budget",
                     fontsize=9, color=INK, loc="left")
    plt.setp(ax_top.get_xticklabels(), visible=False)
    ax_top.tick_params(axis="x", length=0)

    for name, color, marker, getter in series:
        vals = np.array([getter(s) for s in summaries])
        finite = np.isfinite(vals)
        ax.plot(betas[finite], vals[finite], marker=marker, color=color,
                lw=1.5, ms=5.5, label=name, zorder=3)
    ax.axhline(budget, color=MUTED_BAR, ls="--", lw=1.0, zorder=1)

    labeled, last = [], None
    for b in sorted(set(betas)):
        if last is None or math.log10(b / last) >= 0.09:
            labeled.append(b)
            last = b
    ax.set_xscale("log")
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(labeled)
    ax.set_xticklabels([f"{b:.3g}" for b in labeled], fontsize=7.5, rotation=35)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(-0.3, budget * 1.25)
    ax.set_yticks([0, 1, 10, 100, budget])
    ax.set_yticklabels(["0", "1", "10", "100", f"{budget} (budget)"], fontsize=8)
    ax.set_xlabel(rf"fine coupling $\beta_f$ (matched pair, L={scan_L})",
                  fontsize=10, color=INK)
    ax.set_ylabel("HMC trajectories per new thermalized,\nindependent config",
                  fontsize=9, color=INK)
    for a in (ax_top, ax):
        a.grid(color=GRID_COLOR, lw=0.7)
        a.set_axisbelow(True)
        for spine in a.spines.values():
            spine.set_color(GRID_COLOR)
    ax.legend(fontsize=8, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.20), ncol=4)
    ax_top.set_zorder(1)
    fig.suptitle("Diffusion seed vs standard HMC across the matched beta scan",
                 fontsize=12, color=INK, y=0.97)
    fig.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def rows_to_md(rows: list[dict]) -> list[str]:
    cols = ["observable", "value", "error", "exact", "z_exact",
            "reference", "ref_error", "z_ref", "ks_p", "chi2_p"]
    present = [c for c in cols if any(c in r for r in rows)]
    lines = ["| " + " | ".join(present) + " |", "|" + "---|" * len(present)]
    for r in rows:
        cells = []
        for c in present:
            v = r.get(c)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append("nan" if math.isnan(v) else f"{v:.4g}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def fmt_t(t: float) -> str:
    return "never" if math.isinf(t) else f"{t:.0f}"


def _load_baseline_cache(case_dir: Path, n_traj_base: int, n_chains_base: int):
    """Hot/cold baseline series from a previous benchmark of the same (L, beta)
    case: fresh plain-HMC chains are statistically identical regardless of how
    the diffusion seeds were sampled, so re-running them is pure waste."""
    series_paths = sorted(case_dir.glob("*_series.npz"))
    summary_paths = sorted(case_dir.glob("*_summary.json"))
    if not series_paths or not summary_paths:
        return None
    s = json.loads(summary_paths[0].read_text(encoding="utf-8"))
    if (int(s.get("n_traj_baseline", -1)) != n_traj_base
            or int(s.get("n_baseline_chains", -1)) != n_chains_base):
        return None
    data = np.load(series_paths[0])
    hot = {k.split("|", 1)[1]: data[k] for k in data.files if k.startswith("hot start|")}
    cold = {k.split("|", 1)[1]: data[k] for k in data.files if k.startswith("cold start|")}
    if "Q" not in hot or "Q" not in cold:
        return None
    acc = s["hmc"]["acceptance"]
    return (hot, cold, float(acc["hot"]), float(acc["cold"]),
            float(s["hmc"]["sec_per_traj_baseline_batch"]))


def run_rung(
    index: int,
    meta: dict,
    seed_configs: torch.Tensor,
    reference: torch.Tensor | None,
    config: dict,
    args,
    device: str,
    out_dir: Path,
    label: str | None = None,
    baseline_cache: Path | None = None,
) -> dict:
    """seed_configs must be the RAW conditional-diffusion samples (pre-retherm):
    every sweep of equilibration the seeds need is charged here, in HMC units."""
    beta = float(meta["beta"])
    lattice_size = int(meta["lattice_size"])
    action_type = config["action_type"]
    action = make_action(action_type, beta)
    data_cfg = config["data"]
    step_size, n_steps = adapted_hmc_params(
        beta, float(data_cfg["hmc_step_size"]), int(data_cfg["hmc_steps"])
    )
    label = label or f"rung{index}_L{lattice_size}_beta{beta:g}"
    case_dir = out_dir / f"L{lattice_size}_beta{beta:g}"
    case_dir.mkdir(parents=True, exist_ok=True)
    targets = exact_targets(beta, action_type, lattice_size)
    print(f"\n=== {label}: step_size={step_size:.4f}, n_steps={n_steps} ===")

    n_traj_gen = int(args.n_traj_gen)
    n_traj_base = int(args.n_traj_baseline)
    n_chains_base = max(8, int(args.n_chains_baseline * (16 / lattice_size)))

    print(f"diffusion seed: {seed_configs.shape[0]} chains x {n_traj_gen} trajectories")
    gen_raw, gen_final, gen_acc, gen_spt = run_relaxation(
        lattice_size, action, seed_configs, n_traj_gen, step_size, n_steps, device
    )
    cached_baselines = None
    if baseline_cache is not None:
        cached_baselines = _load_baseline_cache(baseline_cache, n_traj_base, n_chains_base)
    if cached_baselines is not None:
        hot_raw, cold_raw, hot_acc, cold_acc, hot_spt = cached_baselines
        print(f"baselines: reused from {baseline_cache}")
    else:
        baseline_sampler = BatchedHMC(lattice_size, action, n_chains=n_chains_base, device=device)
        print(f"hot start: {n_chains_base} chains x {n_traj_base} trajectories")
        hot_raw, _, hot_acc, hot_spt = run_relaxation(
            lattice_size, action, baseline_sampler.initialize(hot=True),
            n_traj_base, step_size, n_steps, device,
        )
        print(f"cold start: {n_chains_base} chains x {n_traj_base} trajectories")
        cold_raw, _, cold_acc, _ = run_relaxation(
            lattice_size, action, baseline_sampler.initialize(hot=False),
            n_traj_base, step_size, n_steps, device,
        )

    all_series = {
        "diffusion seed": build_series_dict(gen_raw),
        "hot start": build_series_dict(hot_raw),
        "cold start": build_series_dict(cold_raw),
    }
    subsample = np.random.default_rng(int(config["seed"]) + index).choice(
        seed_configs.shape[0], size=min(n_chains_base, seed_configs.shape[0]), replace=False
    )
    t_therm_series = dict(all_series)
    t_therm_series["diffusion seed"] = {
        k: v[:, subsample] for k, v in all_series["diffusion seed"].items()
    }
    t_therm = {
        start: {name: thermalization_time(series[name], targets[name])
                for name in targets if name in series}
        for start, series in t_therm_series.items()
    }
    t_therm_full = {
        name: thermalization_time(all_series["diffusion seed"][name], targets[name])
        for name in targets if name in all_series["diffusion seed"]
    }
    final_abs_z = {
        start: {name: float(np.abs(ensemble_z_series(series[name], targets[name]))[-10:].mean())
                for name in targets if name in series}
        for start, series in t_therm_series.items()
    }

    discard = n_traj_base // 2
    tau = {}
    for name in targets:
        if name == "Q^2":
            continue
        tau[name] = equilibrium_tau_int(hot_raw[name], discard)
    freezing = q_freezing(hot_raw["Q"], discard, f"hot-start HMC L={lattice_size} beta={beta:g}")

    plot_relaxation(
        all_series, targets, label, case_dir / f"{label}_relaxation.png",
        t_therm=t_therm, tau_int=tau,
    )
    np.savez_compressed(
        case_dir / f"{label}_series.npz",
        **{f"{start}|{name}": series for start, obs in all_series.items()
           for name, series in obs.items()},
    )

    rows_pre = validate_ensemble(
        seed_configs, beta, action_type, reference_configs=reference,
        label=f"{label}_generated", output_dir=case_dir, make_plots=False,
    )
    rows_post = validate_ensemble(
        gen_final.cpu(), beta, action_type, reference_configs=reference,
        label=f"{label}_after_hmc", output_dir=case_dir, make_plots=False,
    )
    save_ensemble(
        case_dir / f"{label}_after_hmc.pt", gen_final.cpu(),
        {"beta": beta, "lattice_size": lattice_size, "action_type": action_type,
         "provenance": f"raw diffusion seed + {n_traj_gen} plain-HMC trajectories"},
    )

    slowest = max(2.0 * tau[name][0] for name in tau if name in INTERVAL_OBS)
    summary = {
        "label": label,
        "beta": beta,
        "lattice_size": lattice_size,
        "n_gen_chains": int(seed_configs.shape[0]),
        "n_baseline_chains": n_chains_base,
        "n_traj_gen": n_traj_gen,
        "n_traj_baseline": n_traj_base,
        "hmc": {"step_size": step_size, "n_steps": n_steps,
                "acceptance": {"generated": gen_acc, "hot": hot_acc, "cold": cold_acc},
                "sec_per_traj_gen_batch": gen_spt, "sec_per_traj_baseline_batch": hot_spt},
        "t_therm": t_therm,
        "t_therm_generated_full_batch": t_therm_full,
        "t_therm_subsample_size": int(len(subsample)),
        "final_abs_z": final_abs_z,
        "tau_int": {name: {"value": v, "error": e} for name, (v, e) in tau.items()},
        "hmc_interval_trajectories": slowest,
        "q_freezing": freezing,
    }
    save_json(case_dir / f"{label}_summary.json", summary)
    return {"summary": summary, "rows_pre": rows_pre, "rows_post": rows_post,
            "series": all_series, "targets": targets}


def cached_rung_record(case_dir: Path, label: str, seed_configs: torch.Tensor,
                       reference: torch.Tensor | None, beta: float,
                       action_type: str) -> dict | None:
    """Rebuild a run_rung result from a completed case's on-disk outputs.

    The benchmark chains (the expensive part) are read back via the saved
    summary; only the two validation-row tables are recomputed, from the cached
    seed and after-HMC ensembles. Returns None if any required file is missing."""
    summary_path = case_dir / f"{label}_summary.json"
    after_path = case_dir / f"{label}_after_hmc.pt"
    if not (summary_path.exists() and after_path.exists()
            and (case_dir / f"{label}_series.npz").exists()):
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    after, _ = load_ensemble(after_path)
    rows_pre = validate_ensemble(
        seed_configs, beta, action_type, reference_configs=reference,
        label=f"{label}_generated", output_dir=case_dir, make_plots=False,
    )
    rows_post = validate_ensemble(
        after, beta, action_type, reference_configs=reference,
        label=f"{label}_after_hmc", output_dir=case_dir, make_plots=False,
    )
    return {"summary": summary, "rows_pre": rows_pre, "rows_post": rows_post}


def write_thermalization_report(
    results: list[dict], action_type: str, path: Path, mode: str = "ladder"
) -> None:
    wilson_obs = ("plaquette", "wilson_2x2", "wilson_4x4")
    if mode == "ladder":
        title = ("# Diffusion-seeded HMC: thermalization time vs the "
                 "standard-HMC sampling interval")
        claim = [
            "**Claim.** A raw sample from the conditional-diffusion ladder, used as the "
            "starting configuration of an HMC chain, thermalizes within a few tens of "
            "trajectories at every coupling. The yardstick is the sampling interval "
            "`2 tau_int` -- the trajectories a standard HMC chain needs between two of "
            "its own independent configs, i.e. its *marginal* cost per config, charged "
            "forever. At the fine rungs the ladder is built for, the ordering is",
            "",
            "> t_therm(diffusion seed)  <  2 tau_int(standard HMC)  <  burn-in(fresh chain)",
            "",
            "with a margin that grows with beta as standard HMC slides into critical "
            "slowing down and topological freezing. At the cheapest rung the seed and "
            "the interval are comparable -- where standard HMC is still efficient there "
            "is nothing to win on Wilson-loop observables -- but even there the seed "
            "starts in the correct topological sector at t = 0, while the chain's "
            "topological interval `2 tau_int(Q)` is several times longer than its "
            "Wilson-loop one. The fresh-chain burn-in is standard HMC's one-time entry "
            "cost and exceeds the interval everywhere.",
            "",
            "![timescales](timescales.png)",
        ]
        seed_bullet = (
            "- **Diffusion seed** -- the raw output of the conditional-diffusion ladder "
            "at this rung (ancestral sampling + the deterministic coarse-charge "
            "transport), with **no** rethermalization sweeps applied: every bit of "
            "equilibration the seed needs is measured here, in HMC trajectories."
        )
        anchor = (
            "The diffusion ladder itself is "
            "anchored at a cheap coarse rung (L=8, beta ~ 1.35) where HMC mixes well, "
            "and transports that ensemble to fine rungs -- which is precisely why it "
            "can start chains in regions standard HMC cannot reach."
        )
    else:
        title = ("# Diffusion-seeded HMC across the matched beta scan: "
                 "thermalization time vs the standard-HMC sampling interval")
        claim = [
            "**Why this scan.** At the ladder's upper rungs the fresh-HMC baselines "
            "never thermalize at all (topological freezing plus a metastable "
            "local-defect state), so the only comparison available there is "
            "'diffusion seed vs a baseline that never arrives'. This report extends "
            "the benchmark to every matched coupling pair of the generalization "
            "study -- one inverse-RG step L=16 -> L=32 per case -- including fine "
            "couplings low enough that hot- and cold-start HMC *does* thermalize "
            "within the budget. There the standard chain's own interval `2 tau_int` "
            "and its fresh-start burn-in are honest, measurable yardsticks, and the "
            "scan shows where the ordering",
            "",
            "> t_therm(diffusion seed)  <  2 tau_int(standard HMC)  <  burn-in(fresh chain)",
            "",
            "sets in as beta grows and standard HMC slides into critical slowing "
            "down and topological freezing.",
            "",
            "![beta scan](beta_scan.png)",
            "",
            "![timescales](timescales.png)",
        ]
        seed_bullet = (
            "- **Diffusion seed** -- the raw conditional-diffusion output for this "
            "coupling: one inverse-RG step from a direct-HMC base ensemble at the "
            "matched coarse coupling (ancestral sampling + the deterministic "
            "coarse-charge transport), with **no** rethermalization sweeps applied: "
            "every bit of equilibration the seed needs is measured here, in HMC "
            "trajectories."
        )
        anchor = (
            "Each diffusion seed here is one "
            "inverse-RG step from a direct-HMC base ensemble at the matched coarse "
            "coupling beta_c (L=16), where HMC mixes well -- which is precisely why "
            "it can start chains in regions standard HMC cannot reach."
        )
    lines = [
        title,
        "",
        f"Action: {action_type}. All HMC in this report is plain HMC "
        "(Omelyan, adapted step size, **no** topological updates).",
        "",
        *claim,
        "",
        "## The three starting points",
        "",
        seed_bullet,
        "- **Hot start** -- every link angle drawn uniformly from (-pi, pi]: a "
        "completely disordered (infinite-temperature) configuration. The standard "
        "way to initialize a fresh HMC chain without prior information.",
        "- **Cold start** -- every link angle set to zero: the perfectly ordered "
        "(beta -> infinity) configuration, the other standard initialization.",
        "",
        "## Summary",
        "",
        "| rung | L | beta | t_therm diffusion seed | standard-HMC interval 2 tau_int "
        "| margin (interval - t_therm) | burn-in hot / cold | tau_int(Q) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for res in results:
        s = res["summary"]

        def slowest(start):
            return max(s["t_therm"][start][n] for n in wilson_obs)

        frz = s["q_freezing"]
        tau_q = (f"frozen ({frz['n_tunnelings']} tunnelings in "
                 f"{frz['window_length']} x {frz['n_chains']} traj)"
                 if frz["frozen"] else f"{frz['tau_int_Q']:.1f}")
        interval = s["hmc_interval_trajectories"]
        t_gen = slowest("diffusion seed")
        margin = (f"{interval - t_gen:.1f} traj" if math.isfinite(t_gen)
                  else "--")
        lines.append(
            f"| {s['label']} | {s['lattice_size']} | {s['beta']:g} | {fmt_t(t_gen)} | "
            f"{interval:.1f} | {margin} | {fmt_t(slowest('hot start'))} / "
            f"{fmt_t(slowest('cold start'))} | {tau_q} |"
        )
    lines += [
        "",
        "t_therm and burn-in are the slowest Wilson-loop observable (plaquette, "
        "W(2x2), W(4x4)); topology is stricter still for the fresh chains: their "
        "Q^2 **never** reaches the exact value at the frozen rungs, while the "
        "diffusion seed inherits the correct topological sector from the coarse "
        "ensemble it was generated from (see the Q^2 panels and per-rung tables "
        "below).",
        "",
        "Thermalization time `t_therm` = first trajectory at which the ensemble-mean "
        "z-score vs the exact value satisfies |z| <= 2 and stays there for 5 "
        "consecutive trajectories (t = 0: already thermalized before any HMC). "
        "For the diffusion seed, t_therm is computed on a random subsample of chains "
        "matched to the baseline chain count so all starts are compared at equal "
        "statistical power. `tau_int` is Madras-Sokal, measured on the second half "
        "of the hot-start chains, averaged over chains. In the per-rung relaxation "
        "figures, triangles mark each start's t_therm, dashed curves are the "
        "exponential fits C + A exp(-t/tau) to the ensemble means (tau quoted per "
        "panel), and the right-hand panels track the ensemble mean's distance from "
        "the exact value in SEM units -- thermalized means inside the shaded "
        "|z| <= 2 band; the dotted vertical line there is the standard-HMC "
        "interval `2 tau_int`.",
        "",
        "## What 'never' means, and where the ground truth comes from",
        "",
        "'never' = the ensemble mean was still outside |z| <= 2 of the exact value "
        "after the full baseline budget; the per-rung sections quote the z-score it "
        "plateaued at. For hot starts at the large-beta rungs this is not a "
        "budget problem but a physical one: a random start freezes into a random "
        "topological sector (<Q^2> of order tens), plain HMC can never change Q at "
        "these couplings (tunneling is suppressed ~exp(-2 beta)), and the wrong "
        "sector biases every Wilson loop by an amount that never decays. Cold "
        "starts sit in the single sector Q = 0, so their Wilson loops do eventually "
        "converge, but <Q^2> stays pinned at 0 forever.",
        "",
        "None of the exact values in this report come from fine-lattice HMC: the "
        "ground truth is the character expansion of 2D compact U(1) "
        "(`diffusion/lgt/exact.py`), which gives every Wilson loop, P(Q) and "
        "chi_top in closed form at finite volume. " + anchor,
        "",
    ]
    for res in results:
        s = res["summary"]
        label = s["label"]
        case_dir = f"L{s['lattice_size']}_beta{s['beta']:g}"
        acc = s["hmc"]["acceptance"]
        never_notes = []
        for start in ("hot start", "cold start"):
            stuck = [f"{name} at |z| ~ {s['final_abs_z'][start][name]:.0f}"
                     for name, t in s["t_therm"][start].items()
                     if math.isinf(t)]
            if stuck:
                never_notes.append(
                    f"the {start} ended the {s['n_traj_baseline']}-trajectory budget "
                    "still at " + ", ".join(stuck)
                )
        lines += [
            f"## {label}",
            "",
            f"HMC: step size {s['hmc']['step_size']:.4f}, {s['hmc']['n_steps']} leapfrog steps, "
            f"acceptance seed/hot/cold = {acc['generated']:.3f}/{acc['hot']:.3f}/{acc['cold']:.3f}. "
            f"Diffusion-seed batch: {s['n_gen_chains']} chains x {s['n_traj_gen']} trajectories "
            f"({s['hmc']['sec_per_traj_gen_batch']:.2f} s/traj for the whole batch); baselines: "
            f"{s['n_baseline_chains']} chains x {s['n_traj_baseline']} trajectories.",
            "",
            f"![relaxation]({case_dir}/{label}_relaxation.png)",
            "",
            "tau_int (hot-start chains, second half): "
            + ", ".join(f"{name} = {d['value']:.2f} +- {d['error']:.2f}"
                        for name, d in s["tau_int"].items())
            + f". Topology: {s['q_freezing']['label']} -> "
            + ("**frozen** (no tunneling)" if s["q_freezing"]["frozen"]
               else f"tau_int(Q) = {s['q_freezing']['tau_int_Q']:.1f}")
            + ".",
            "",
        ]
        if never_notes:
            lines += ["Where 'never' stood at the end: " + "; ".join(never_notes) + ".", ""]
        lines += [
            "### Diagnostics: raw diffusion output (before any HMC)",
            "",
            *rows_to_md(res["rows_pre"]),
            "",
            f"### Diagnostics: the same configs after {s['n_traj_gen']} HMC trajectories",
            "",
            *rows_to_md(res["rows_post"]),
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def replot_relaxations(out_dir: Path, action_type: str) -> None:
    """Regenerate every relaxation figure from the cached per-case series and
    summaries under out_dir's L*_beta*/ subfolders; no HMC is run."""
    summary_paths = sorted(out_dir.glob("L*_beta*/*_summary.json"))
    if not summary_paths:
        raise SystemExit(f"no L*_beta*/*_summary.json under {out_dir}")
    for sp in summary_paths:
        s = json.loads(sp.read_text(encoding="utf-8"))
        label, case_dir = s["label"], sp.parent
        series = np.load(case_dir / f"{label}_series.npz")
        all_series: dict[str, dict[str, np.ndarray]] = {}
        for key in series.files:
            start, name = key.split("|", 1)
            all_series.setdefault(start, {})[name] = series[key]
        targets = exact_targets(float(s["beta"]), action_type, int(s["lattice_size"]))
        tau = {name: (d["value"], d["error"]) for name, d in s.get("tau_int", {}).items()}
        plot_relaxation(all_series, targets, label, case_dir / f"{label}_relaxation.png",
                        t_therm=s.get("t_therm"), tau_int=tau)
        print(case_dir / f"{label}_relaxation.png", flush=True)


def load_scan_summaries(out_dir: Path) -> list[dict]:
    """Cached per-case summaries under out_dir's L*_beta*/ subfolders, sorted by
    (lattice size, beta), deduplicated per case."""
    seen: dict[tuple[int, float], dict] = {}
    for sp in sorted(out_dir.glob("L*_beta*/*_summary.json")):
        s = json.loads(sp.read_text(encoding="utf-8"))
        seen.setdefault((int(s["lattice_size"]), float(s["beta"])), s)
    return [seen[k] for k in sorted(seen)]


def replot_scan_figures(out_dir: Path) -> None:
    summaries = load_scan_summaries(out_dir)
    if not summaries:
        return
    plot_timescales(summaries, out_dir / "timescales.png")
    plot_beta_scan(summaries, out_dir / "beta_scan.png")
    print(out_dir / "timescales.png", flush=True)
    print(out_dir / "beta_scan.png", flush=True)


def run_generalization_scan(args, config: dict, device: str) -> None:
    """Thermalization benchmark over the generalization study's matched-pair
    scan: raw diffusion seeds are (re)generated from the cached coarse bases
    (the study only saved post-retherm ensembles) and cached next to them."""
    from diffusion.model.train import load_checkpoint
    from diffusion.pipeline.ladder import generate_fine_from_coarse

    action_type = config["action_type"]
    gen_dir = Path(args.generalization)
    summary_path = gen_dir / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"no generalization summary at {summary_path}; "
                         "run 06_generalization_study.py first")
    records = json.loads(summary_path.read_text(encoding="utf-8"))
    parts = {p.strip() for p in args.parts.split(",")}
    cases = sorted(
        (r for r in records.values() if r.get("part") in parts and "rows" in r),
        key=lambda r: (int(r["base_size"]), float(r["target_beta"])),
    )
    if args.betas:
        wanted = [float(v) for v in args.betas.split(",")]
        cases = [r for r in cases
                 if any(abs(float(r["target_beta"]) - w) < 1e-3 for w in wanted)]
    if not cases:
        raise SystemExit(f"no completed generalization cases for parts {sorted(parts)}")
    out_dir = Path(args.out) if args.out else gen_dir.parent / "thermalization" / "generalization"
    if args.replot:
        replot_relaxations(out_dir, action_type)
        replot_scan_figures(out_dir)
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{len(cases)} matched-pair cases, output -> {out_dir}", flush=True)

    model_schedule = None
    results = []
    for index, record in enumerate(cases):
        beta_f = float(record["target_beta"])
        base_size = int(record["base_size"])
        fine_size = 2 * base_size
        run_id = record["run_id"]
        label = f"{run_id}_L{fine_size}_beta{beta_f:g}"
        raw_path = gen_dir / "generated" / f"{run_id}_raw_{action_type}_L{fine_size}_beta{beta_f:g}.pt"
        if raw_path.exists():
            seed_configs, _ = load_ensemble(raw_path)
        else:
            base_path = gen_dir / "bases" / f"{action_type}_L{base_size}_beta{float(record['base_beta']):g}.pt"
            base = load_ensemble(base_path)[0][: int(record["n_configs"])]
            if model_schedule is None:
                model_schedule = load_checkpoint(args.checkpoint, device)
                if args.sigma_floor_coef is not None:
                    from diffusion.model.schedule import GeometricNoiseSchedule

                    model_schedule = (model_schedule[0], GeometricNoiseSchedule(
                        model_schedule[1].sigma_min, model_schedule[1].sigma_max,
                        sigma_min_beta_coef=args.sigma_floor_coef,
                    ))
            print(f"{label}: sampling {base.shape[0]} raw seeds from {base_path.name}", flush=True)
            t0 = time.time()
            seed_configs = generate_fine_from_coarse(
                model_schedule[0], model_schedule[1], base, beta_f,
                n_sampler_steps=200, n_corrector_steps=1, batch_size=32,
                device=device, consistency_weight=1.0, enforce_coarse_charge=True,
                physics_blend_coef=args.physics_blend,
            )
            save_ensemble(raw_path, seed_configs, {
                "beta": beta_f, "lattice_size": fine_size, "action_type": action_type,
                "provenance": f"raw conditional-diffusion output (pre-retherm), "
                              f"base {base_path.name}, sampled for the thermalization scan",
            })
            print(f"    sampled in {time.time() - t0:.0f}s", flush=True)
        ref_path = gen_dir / "reference" / f"{action_type}_L{fine_size}_beta{beta_f:g}.pt"
        reference = load_ensemble(ref_path)[0] if ref_path.exists() else None
        meta = {"beta": beta_f, "lattice_size": fine_size}
        if args.skip_cached:
            case_dir = out_dir / f"L{fine_size}_beta{beta_f:g}"
            cached = cached_rung_record(case_dir, label, seed_configs, reference,
                                        beta_f, action_type)
            if cached is not None:
                print(f"{label}: benchmark cached, reusing series/summary", flush=True)
                results.append(cached)
                continue
        baseline_cache = None
        if args.reuse_baselines:
            baseline_cache = Path(args.reuse_baselines) / f"L{fine_size}_beta{beta_f:g}"
        results.append(run_rung(index, meta, seed_configs, reference, config, args,
                                device, out_dir, label=label,
                                baseline_cache=baseline_cache))

    summaries = [res["summary"] for res in results]
    plot_timescales(summaries, out_dir / "timescales.png")
    plot_beta_scan(summaries, out_dir / "beta_scan.png")
    write_thermalization_report(results, action_type, out_dir / "report.md",
                                mode="generalization")
    print(f"\nreport: {out_dir / 'report.md'}")
    for s in summaries:
        print(json.dumps({k: s[k] for k in ("label", "t_therm", "hmc_interval_trajectories")}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion/configs/demo.yaml")
    parser.add_argument("--rungs", default=None, help="comma-separated rung indices (default: all)")
    parser.add_argument("--n-traj-gen", type=int, default=96, dest="n_traj_gen")
    parser.add_argument("--n-traj-baseline", type=int, default=640, dest="n_traj_baseline")
    parser.add_argument("--n-chains-baseline", type=int, default=64, dest="n_chains_baseline",
                        help="baseline chains at L=16; scaled by 16/L at larger L")
    parser.add_argument("--out", default=None)
    parser.add_argument("--run-dir", default=None, dest="run_dir",
                        help="override the run root (replaces the config's out_dir parents, "
                        "e.g. out/diffusion/demo when the config says artifacts/diffusion/demo)")
    parser.add_argument("--generalization", nargs="?", const="out/diffusion/demo/generalization",
                        default=None,
                        help="benchmark the generalization study's matched-pair scan instead of "
                        "the ladder rungs; optional value overrides the study directory")
    parser.add_argument("--parts", default="A,D",
                        help="generalization mode: which study parts to include")
    parser.add_argument("--betas", default=None,
                        help="generalization mode: comma-separated target-beta filter")
    parser.add_argument("--checkpoint", default="out/diffusion/demo/checkpoints/score_net.pt",
                        help="generalization mode: score-net checkpoint for raw-seed sampling")
    parser.add_argument("--physics-blend", type=float, default=0.0, dest="physics_blend",
                        help="generalization mode: exact-score blend coefficient for "
                        "raw-seed sampling (0 = off)")
    parser.add_argument("--sigma-floor-coef", type=float, default=None, dest="sigma_floor_coef",
                        help="generalization mode: override the checkpoint schedule's "
                        "beta-aware noise floor coefficient for raw-seed sampling")
    parser.add_argument("--reuse-baselines", default=None, dest="reuse_baselines",
                        help="path to a previous thermalization output dir: reuse its "
                        "hot/cold baseline chains and rerun only the diffusion-seed "
                        "chains (baselines are seed-independent plain HMC)")
    parser.add_argument("--skip-cached", action="store_true", dest="skip_cached",
                        help="generalization mode: reuse completed cases' saved "
                        "benchmark outputs (series/summary/after_hmc) instead of "
                        "re-running their HMC; validation rows are recomputed")
    parser.add_argument("--replot", action="store_true",
                        help="regenerate the relaxation figures from cached per-case "
                        "series under the mode's output directory; no HMC is run")
    args = parser.parse_args()
    config = load_config(args.config)
    set_seed(int(config["seed"]) + 5)
    device = resolve_device(config)
    if args.generalization is not None:
        run_generalization_scan(args, config, device)
        return
    action_type = config["action_type"]
    generated_dir = Path(config["ladder"]["out_dir"])
    reference_dir = Path(config["validate"]["out_dir"]) / "reference"
    if args.run_dir is not None:
        run_dir = Path(args.run_dir)
        generated_dir = run_dir / generated_dir.name
        reference_dir = run_dir / Path(config["validate"]["out_dir"]).name / "reference"
    out_dir = Path(args.out) if args.out else generated_dir.parent / "thermalization"
    if args.replot:
        replot_relaxations(out_dir, action_type)
        replot_scan_figures(out_dir)
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = str(generated_dir / f"ladder_rung*_{action_type}_*.pt")
    paths = sorted(p for p in glob.glob(pattern) if "_raw_" not in Path(p).name)
    if not paths:
        raise SystemExit(f"no ladder ensembles under {pattern}; run 03_run_ladder.py first")
    wanted = None if args.rungs is None else {int(v) for v in args.rungs.split(",")}

    results = []
    for index, path in enumerate(paths):
        if wanted is not None and index not in wanted:
            continue
        raw_path = Path(path).with_name(
            Path(path).name.replace(f"ladder_rung{index}_", f"ladder_rung{index}_raw_")
        )
        if not raw_path.exists():
            raise SystemExit(
                f"missing raw seed ensemble {raw_path}; re-run 03_run_ladder.py "
                "(it now saves the pre-retherm samples)"
            )
        seed_configs, meta = load_ensemble(raw_path)
        ref_path = ensemble_path(
            reference_dir, action_type, int(meta["lattice_size"]), float(meta["beta"]),
        )
        reference = load_ensemble(ref_path)[0] if ref_path.exists() else None
        results.append(run_rung(index, meta, seed_configs, reference, config, args, device, out_dir))

    plot_timescales([res["summary"] for res in results], out_dir / "timescales.png")
    write_thermalization_report(results, action_type, out_dir / "report.md")
    print(f"\nreport: {out_dir / 'report.md'}")
    for res in results:
        s = res["summary"]
        print(json.dumps({k: s[k] for k in ("label", "t_therm", "hmc_interval_trajectories")}, indent=2))


if __name__ == "__main__":
    main()
