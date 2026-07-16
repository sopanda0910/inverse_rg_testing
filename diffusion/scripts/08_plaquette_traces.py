"""Single-chain observable traces in the classic HMC-diagnostic style.

For each case of the thermalization benchmark (05_hmc_thermalization.py, ladder
rungs or the --generalization beta scan), plots one chain's history per start
and per observable (plaquette, Wilson loops, Q^2) -- blue up to the measured
t_therm (thermalization), orange after (production), red dashed exact value.
Each panel also carries an exponential fit C + A exp(-t/tau) to the
ensemble-mean relaxation (all chains, not just the traced one); the
characteristic time tau is stated in the panel title, the fitted curve is
overlaid, and all fits are saved to {label}_exp_fits.json.

Reads the per-trajectory series the benchmark saves as {label}_series.npz --
cases are discovered in per-case L{size}_beta{value}/ subfolders (and, for
backward compatibility, flat at the top level). The only HMC run here is the
cached one-chain continuation of the diffusion seed past its short benchmark
window, for visualization only.

    python diffusion/scripts/08_plaquette_traces.py --dir out/diffusion/demo/thermalization
    python diffusion/scripts/08_plaquette_traces.py --dir out/diffusion/demo/thermalization/generalization
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.lgt import exact, make_action
from diffusion.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion.lgt.lattice import plaquette_angles, topological_charge, wilson_loop_angles
from diffusion.validate.stats import fit_exponential_relaxation
from diffusion.utils import load_ensemble, save_json

THERM_COLOR = "#2440b3"
PROD_COLOR = "#f5a623"
EXACT_COLOR = "#d62728"
FIT_COLOR = "#1f8a4c"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

STARTS = ["diffusion seed", "cold start", "hot start"]
OBS_ORDER = ["plaquette", "wilson_2x2", "wilson_4x4", "Q^2"]
OBS_LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4)}
OBS_FILENAME = {"Q^2": "Q2"}


def chain_observables(theta: torch.Tensor) -> dict[str, float]:
    out = {"plaquette": float(torch.cos(plaquette_angles(theta)).mean())}
    for name, (r, t) in OBS_LOOPS.items():
        if max(r, t) <= theta.shape[-1] // 2:
            out[name] = float(torch.cos(wilson_loop_angles(theta, r, t)).mean())
    out["Q^2"] = float(topological_charge(theta).square().mean())
    return out


def exact_target(name: str, beta: float, action_type: str, lattice_size: int) -> float:
    if name == "plaquette":
        return exact.plaquette_exact(beta, action_type, lattice_size)
    if name in OBS_LOOPS:
        r, t = OBS_LOOPS[name]
        return exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)
    if name == "Q^2":
        return exact.topological_susceptibility_exact(beta, action_type, lattice_size) * lattice_size**2
    raise ValueError(f"no exact target for {name}")


def extend_seed_trace(
    case_dir: Path, label: str, traces: dict[str, np.ndarray], target_len: int,
    chain: int, beta: float, action_type: str,
) -> dict[str, np.ndarray]:
    """Continue the diffusion-seed chain from its saved post-benchmark state so
    its traces have as many points as the baseline chains (visualization only --
    the benchmark's t_therm and the exponential fits are untouched). Cached on
    disk; a plaquette-only cache from the old script is recomputed in full."""
    n_extra = target_len - len(next(iter(traces.values())))
    if n_extra <= 0:
        return traces
    cache = case_dir / f"{label}_seed_trace_ext_chain{chain}.npz"
    extra = dict(np.load(cache)) if cache.exists() else {}
    if not all(name in extra and len(extra[name]) >= n_extra for name in traces):
        state_path = case_dir / f"{label}_after_hmc.pt"
        if not state_path.exists():
            print(f"  {label}: no {state_path.name}; seed traces stay short")
            return traces
        configs, _ = load_ensemble(state_path)
        theta = configs[chain : chain + 1].clone()
        action = make_action(action_type, beta)
        step_size, n_steps = adapted_hmc_params(beta)
        sampler = BatchedHMC(theta.shape[-1], action, n_chains=1,
                             n_steps=n_steps, step_size=step_size)
        torch.manual_seed(hash((label, chain)) % 2**31)
        values: dict[str, list[float]] = {name: [] for name in traces}
        with torch.no_grad():
            for _ in range(n_extra):
                theta, _ = sampler.metropolis_step(theta)
                obs = chain_observables(theta)
                for name in values:
                    values[name].append(obs[name])
        extra = {name: np.asarray(v) for name, v in values.items()}
        np.savez_compressed(cache, **extra)
    return {name: np.concatenate([trace, extra[name][:n_extra]])
            for name, trace in traces.items()}


def plot_case_observable(
    case_dir: Path, summary: dict, series, seed_traces: dict[str, np.ndarray],
    name: str, chain: int, fits: dict, action_type: str,
) -> Path:
    beta, lattice_size = summary["beta"], summary["lattice_size"]
    target = exact_target(name, beta, action_type, lattice_size)
    label = summary["label"]
    benchmark_len = series[f"diffusion seed|{name}"].shape[0]

    fig, axes = plt.subplots(len(STARTS), 1, figsize=(10.5, 9.5))
    for ax, start in zip(axes, STARTS):
        if start == "diffusion seed":
            trace = seed_traces[name]
            extended = len(trace) > benchmark_len
        else:
            trace = series[f"{start}|{name}"][:, chain]
            extended = False
        t_therm = summary["t_therm"][start].get(name)
        x = np.arange(len(trace))
        if t_therm is None or math.isinf(t_therm):
            ax.plot(x, trace, lw=0.9, color=THERM_COLOR,
                    label="thermalization (never completes)")
            note = "never thermalizes within the budget"
        else:
            split = int(t_therm)
            ax.plot(x[: split + 1], trace[: split + 1], lw=0.9, color=THERM_COLOR,
                    label="thermalization")
            ax.plot(x[split:], trace[split:], lw=0.9, color=PROD_COLOR,
                    label="production")
            note = f"$t_{{therm}}$ = {split} trajectories"
            if extended:
                note += f" (chain continued past the {benchmark_len - 1}-trajectory benchmark)"
        fit = fits[start][name]
        if fit["tau"] is not None:
            tf = np.linspace(0, len(trace) - 1, 400)
            ax.plot(tf, fit["C"] + fit["A"] * np.exp(-tf / fit["tau"]),
                    color=FIT_COLOR, lw=1.5, ls="-.",
                    label=rf"exp fit to ensemble mean ($\tau$ = {fit['tau']:.1f})")
            tau_note = rf"$\tau_{{exp}}$ = {fit['tau']:.1f} traj"
            if "amplitude" in fit["status"]:
                tau_note += " (starts at plateau)"
        else:
            tau_note = rf"$\tau_{{exp}}$: {fit['status']}"
        ax.axhline(target, color=EXACT_COLOR, ls="--", lw=1.3, label="theoretical value")
        ax.set_title(f"{start} — {note}; {tau_note}", fontsize=10, color=INK)
        ax.set_ylabel(name, fontsize=9)
        ax.legend(fontsize=8, frameon=False,
                  loc="lower right" if start == "hot start" else "upper right")
        ax.grid(color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    axes[0].set_ylim(axes[1].get_ylim())
    axes[-1].set_xlabel("HMC trajectory", fontsize=9)
    fig.suptitle(
        f"{name} vs. trajectory, single chain (L={lattice_size}, "
        rf"$\beta$={beta:g}, exact = {target:.4g})",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = case_dir / f"{label}_{OBS_FILENAME.get(name, name)}_trace.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_case(case_dir: Path, label: str, chain: int, action_type: str) -> None:
    summary = json.loads((case_dir / f"{label}_summary.json").read_text(encoding="utf-8"))
    series = np.load(case_dir / f"{label}_series.npz")
    beta, lattice_size = summary["beta"], summary["lattice_size"]
    names = [n for n in OBS_ORDER if f"diffusion seed|{n}" in series]

    fits = {
        start: {name: fit_exponential_relaxation(
            series[f"{start}|{name}"].mean(axis=1),
            exact_target(name, beta, action_type, lattice_size))
            for name in names}
        for start in STARTS
    }
    save_json(case_dir / f"{label}_exp_fits.json", fits)

    target_len = max(series[f"{s}|plaquette"].shape[0] for s in STARTS)
    seed_traces = extend_seed_trace(
        case_dir, label,
        {name: series[f"diffusion seed|{name}"][:, chain] for name in names},
        target_len, chain, beta, action_type,
    )
    for name in names:
        print(plot_case_observable(case_dir, summary, series, seed_traces,
                                   name, chain, fits, action_type), flush=True)
    fmt = lambda f: f"{f['tau']:.1f}" if f["tau"] is not None else "n/a"
    print("  tau_exp: " + "; ".join(
        f"{name}: seed {fmt(fits['diffusion seed'][name])} / "
        f"cold {fmt(fits['cold start'][name])} / hot {fmt(fits['hot start'][name])}"
        for name in names), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="out/diffusion/demo/thermalization",
                        help="thermalization benchmark output directory")
    parser.add_argument("--chain", type=int, default=0, help="chain index to trace")
    parser.add_argument("--action-type", default="wilson", dest="action_type")
    args = parser.parse_args()
    therm_dir = Path(args.dir)
    cases = sorted(
        (p.parent, p.name[: -len("_series.npz")])
        for pattern in ("*_series.npz", "*/*_series.npz")
        for p in therm_dir.glob(pattern)
        if p.parent.name != "generalization"
    )
    if not cases:
        raise SystemExit(f"no *_series.npz under {therm_dir}; run 05_hmc_thermalization.py first")
    for case_dir, label in cases:
        plot_case(case_dir, label, args.chain, args.action_type)


if __name__ == "__main__":
    main()
