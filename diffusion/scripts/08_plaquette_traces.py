"""Single-chain plaquette traces in the classic HMC-diagnostic style.

For each rung of the thermalization benchmark (05_hmc_thermalization.py), plots
one chain's plaquette history per start -- blue up to the measured t_therm
(thermalization), orange after (production), red dashed exact value. Reads the
per-trajectory series the benchmark saves as {label}_series.npz; no HMC is run.

    python diffusion/scripts/08_plaquette_traces.py --dir out/diffusion/demo/thermalization
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

from diffusion.lgt import make_action
from diffusion.lgt.exact import plaquette_exact
from diffusion.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion.lgt.lattice import plaquette_angles
from diffusion.utils import load_ensemble

THERM_COLOR = "#2440b3"
PROD_COLOR = "#f5a623"
EXACT_COLOR = "#d62728"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

STARTS = ["diffusion seed", "cold start", "hot start"]


def extend_seed_trace(
    therm_dir: Path, label: str, trace: np.ndarray, target_len: int,
    chain: int, beta: float, action_type: str,
) -> np.ndarray:
    """Continue the diffusion-seed chain from its saved post-benchmark state so the
    trace has as many points as the baseline chains (visualization only -- the
    benchmark's t_therm is untouched). The continuation is cached on disk."""
    n_extra = target_len - len(trace)
    if n_extra <= 0:
        return trace
    cache = therm_dir / f"{label}_seed_trace_ext_chain{chain}.npz"
    if cache.exists():
        extra = np.load(cache)["plaquette"]
    else:
        state_path = therm_dir / f"{label}_after_hmc.pt"
        if not state_path.exists():
            print(f"  {label}: no {state_path.name}; seed trace stays at {len(trace)} points")
            return trace
        configs, _ = load_ensemble(state_path)
        theta = configs[chain : chain + 1].clone()
        action = make_action(action_type, beta)
        step_size, n_steps = adapted_hmc_params(beta)
        sampler = BatchedHMC(theta.shape[-1], action, n_chains=1,
                             n_steps=n_steps, step_size=step_size)
        torch.manual_seed(hash((label, chain)) % 2**31)
        values = []
        with torch.no_grad():
            for _ in range(n_extra):
                theta, _ = sampler.metropolis_step(theta)
                values.append(float(torch.cos(plaquette_angles(theta)).mean()))
        extra = np.asarray(values)
        np.savez_compressed(cache, plaquette=extra)
    return np.concatenate([trace, extra[: n_extra]])


def plot_rung(therm_dir: Path, label: str, chain: int, action_type: str) -> Path:
    summary = json.loads((therm_dir / f"{label}_summary.json").read_text(encoding="utf-8"))
    beta, lattice_size = summary["beta"], summary["lattice_size"]
    exact = plaquette_exact(beta, action_type, lattice_size)
    series = np.load(therm_dir / f"{label}_series.npz")
    target_len = max(series[f"{s}|plaquette"].shape[0] for s in STARTS)

    fig, axes = plt.subplots(len(STARTS), 1, figsize=(10.5, 9.5))
    for ax, start in zip(axes, STARTS):
        trace = series[f"{start}|plaquette"][:, chain]
        extended = False
        if start == "diffusion seed":
            benchmark_len = len(trace)
            trace = extend_seed_trace(
                therm_dir, label, trace, target_len, chain, beta, action_type
            )
            extended = len(trace) > benchmark_len
        t_therm = summary["t_therm"][start]["plaquette"]
        x = np.arange(len(trace))
        if t_therm is None or math.isinf(t_therm):
            ax.plot(x, trace, lw=0.9, color=THERM_COLOR,
                    label="thermalization (never completes)")
            note = "never thermalizes (frozen topological sector)"
        else:
            split = int(t_therm)
            ax.plot(x[: split + 1], trace[: split + 1], lw=0.9, color=THERM_COLOR,
                    label="thermalization")
            ax.plot(x[split:], trace[split:], lw=0.9, color=PROD_COLOR,
                    label="production")
            note = f"$t_{{therm}}$ = {split} trajectories"
            if extended:
                note += f" (chain continued past the {benchmark_len - 1}-trajectory benchmark)"
        ax.axhline(exact, color=EXACT_COLOR, ls="--", lw=1.3,
                   label="theoretical plaquette")
        ax.set_title(f"{start} — {note}", fontsize=10, color=INK)
        ax.set_ylabel("plaquette", fontsize=9)
        ax.legend(fontsize=8, frameon=False,
                  loc="lower right" if start == "hot start" else "upper right")
        ax.grid(color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    axes[0].set_ylim(axes[1].get_ylim())
    axes[-1].set_xlabel("HMC trajectory", fontsize=9)
    fig.suptitle(
        f"Plaquette vs. trajectory, single chain (L={lattice_size}, "
        rf"$\beta$={beta:g}, exact = {exact:.4f})",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    out = therm_dir / f"{label}_plaquette_trace.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="out/diffusion/demo/thermalization",
                        help="thermalization benchmark output directory")
    parser.add_argument("--chain", type=int, default=0, help="chain index to trace")
    parser.add_argument("--action-type", default="wilson", dest="action_type")
    args = parser.parse_args()
    therm_dir = Path(args.dir)
    labels = sorted(p.name[: -len("_series.npz")] for p in therm_dir.glob("*_series.npz"))
    if not labels:
        raise SystemExit(f"no *_series.npz under {therm_dir}; run 05_hmc_thermalization.py first")
    for label in labels:
        print(plot_rung(therm_dir, label, args.chain, args.action_type))


if __name__ == "__main__":
    main()
