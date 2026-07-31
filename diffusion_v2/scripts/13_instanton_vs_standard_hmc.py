"""Instanton-update HMC vs standard (plain) HMC.

Elsewhere in this project "HMC" always means plain HMC (no Q-hops) -- the
instanton move (diffusion.lgt.local_updates.topological_update) is used only
to build unbiased reference ensembles for KS tests against generated data
(see 06_generalization_study.py). This script is the one place that evaluates
the instanton move as a method in its own right.

Claim under test: the instanton move is a *global* Metropolis proposal (add a
smooth Q=+-1 configuration to the whole lattice) with delta_S ~ O(beta / V),
so its acceptance rate should stay roughly beta-independent. Standard HMC can
only change Q through its local leapfrog dynamics climbing an action barrier
that grows with beta, so its charge-tunneling rate should collapse (freeze) as
beta grows while instanton HMC's does not. (First pass found this ALSO drags
down non-topological observables for standard HMC once it freezes -- an
ergodicity failure contaminates every observable, not just Q -- see report.md.)

Matched chains: same lattice size, beta, step_size, n_steps (from
adapted_hmc_params) and same hot start, differing only in
topological_updates=True/False.

Error bars: the only rigorously independent statistical unit here is a chain
(different Markov chains = independent noise), so every mean/error in this
script is computed as (mean, sem) over the n_chains per-chain time-averages,
never by pooling all (time x chain) samples into one binned estimator -- that
would silently assume time-adjacent draws are as independent as different
chains, which is false and was previously giving overconfident (too-small)
error bars at high beta where within-chain autocorrelation is long.

    .venv/Scripts/python.exe diffusion/scripts/13_instanton_vs_standard_hmc.py
    .venv/Scripts/python.exe diffusion/scripts/13_instanton_vs_standard_hmc.py --smoke
    .venv/Scripts/python.exe diffusion/scripts/13_instanton_vs_standard_hmc.py --report-only
"""

import argparse
import json
import math
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from diffusion_v2.lgt import exact
from diffusion_v2.lgt.actions import make_action
from diffusion_v2.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion_v2.lgt.lattice import plaquette_angles, topological_charge, wilson_loop_angles
from diffusion_v2.utils import load_ensemble, save_ensemble, save_json, set_seed
from diffusion_v2.validate.observables import measure_ensemble
from diffusion_v2.validate.report import (
    _plaquette_display_window,
    _q_display_window,
    _q_histogram,
    freezing_diagnostics,
)

OUT_DIR = Path("out/diffusion_v2/demo_v6/instanton_vs_standard")
ACTION_TYPE = "wilson"

STD_COLOR = "#c0392b"
INST_COLOR = "#2a78d6"
INK = "#0b0b0b"
MUTED = "#898781"
GRID_COLOR = "#e1e0d9"

BETAS = [2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0]
LATTICE_SIZE = 32
N_CHAINS = 32
BURN_IN = 500
N_PROD = 2000
CONFIG_STRIDE = 25       # how often a full field config is snapshotted, for distribution plots
DISCARD_FRAC = 0.25      # extra safety margin discarded from the *front* of production
                        # before computing per-chain time-averages (burn_in already ran)

SMOKE_BETAS = [4.0, 64.0]
SMOKE_LATTICE_SIZE = 8
SMOKE_N_CHAINS = 4
SMOKE_BURN_IN = 20
SMOKE_N_PROD = 60
SMOKE_CONFIG_STRIDE = 5

OBS_LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4)}


def _json_clean(obj):
    if isinstance(obj, dict):
        return {k: _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_clean(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    return obj


def chain_observables(theta: torch.Tensor) -> dict[str, np.ndarray]:
    """Per-chain scalar observables. theta: [B, 2, L, L] -> each value: [B]."""
    with torch.no_grad():
        out = {
            "plaquette": torch.cos(plaquette_angles(theta)).mean(dim=(-2, -1)).cpu().numpy(),
            "Q": topological_charge(theta).cpu().numpy(),
        }
        lattice_size = theta.shape[-1]
        for name, (r, t) in OBS_LOOPS.items():
            if max(r, t) <= lattice_size // 2:
                out[name] = torch.cos(wilson_loop_angles(theta, r, t)).mean(dim=(-2, -1)).cpu().numpy()
    return out


def chain_mean_sem(series: np.ndarray, discard: int) -> tuple[float, float, np.ndarray]:
    """series: [T, n_chains]. Returns (mean, sem, chain_means) where chain_means
    are the n_chains independent per-chain time-averages -- the only rigorously
    independent statistical unit available (see module docstring)."""
    chain_means = series[discard:].mean(axis=0)
    n_chains = chain_means.shape[0]
    mean = float(chain_means.mean())
    sem = float(chain_means.std(ddof=1) / math.sqrt(n_chains)) if n_chains > 1 else float("nan")
    return mean, sem, chain_means


def freezing_stats(q_series: np.ndarray) -> dict:
    """q_series: [T, n_chains]. Per-chain tau_int_Q/frozen via freezing_diagnostics,
    plus a pooled tunneling count over the whole (T, n_chains) window."""
    n_tunnelings = int(np.sum(np.abs(np.diff(np.round(q_series), axis=0)) > 0))
    per_chain = [freezing_diagnostics(q_series[:, b]) for b in range(q_series.shape[1])]
    frozen = all(d["frozen"] for d in per_chain)
    taus = [d["tau_int_Q"] for d in per_chain if not d["frozen"]]
    return {
        "n_tunnelings": n_tunnelings,
        "window_length": int(q_series.shape[0]),
        "n_chains": int(q_series.shape[1]),
        "frozen": frozen,
        "tau_int_Q": float(np.mean(taus)) if taus else float(q_series.shape[0]),
    }


def run_chain(lattice_size, action, n_chains, step_size, n_steps, burn_in, n_prod,
              topological_updates, device, seed, config_stride):
    """Manual HMC loop (not BatchedHMC.sample()) so every step's per-chain
    observables are recorded, not just plaquette/Q -- needed for honest
    per-chain error bars on Wilson loops too."""
    set_seed(seed)
    sampler = BatchedHMC(lattice_size, action, n_chains=n_chains, n_steps=n_steps,
                         step_size=step_size, device=device, hot_start=True,
                         topological_updates=topological_updates)
    theta = sampler.initialize(hot=True)
    accepted = total = 0
    inst_accepted = inst_total = 0
    with torch.no_grad():
        for _ in range(burn_in):
            theta, accept = sampler.metropolis_step(theta)
            accepted += int(accept.sum())
            total += accept.numel()
            if sampler.last_instanton_accept is not None:
                inst_accepted += int(sampler.last_instanton_accept.sum())
                inst_total += sampler.last_instanton_accept.numel()

        # Q every step (cheap: needed for tunneling counts/traces). Wilson-loop
        # angles are the expensive part of chain_observables, so those are only
        # computed once, batched, over the periodic config snapshots below --
        # not on every one of the n_prod steps.
        q_series = [topological_charge(theta).cpu().numpy()]
        configs = [theta.clone()]
        t0 = time.time()
        for step in range(1, n_prod + 1):
            theta, accept = sampler.metropolis_step(theta)
            accepted += int(accept.sum())
            total += accept.numel()
            if sampler.last_instanton_accept is not None:
                inst_accepted += int(sampler.last_instanton_accept.sum())
                inst_total += sampler.last_instanton_accept.numel()
            q_series.append(topological_charge(theta).cpu().numpy())
            if step % config_stride == 0:
                configs.append(theta.clone())
    sec_per_traj = (time.time() - t0) / max(n_prod, 1)
    q_series = np.stack(q_series)
    configs = torch.stack(configs, dim=0)
    n_snap = configs.shape[0]
    flat_obs = chain_observables(configs.reshape(-1, 2, lattice_size, lattice_size))
    snap_series = {k: v.reshape(n_snap, n_chains) for k, v in flat_obs.items()}
    return {
        "configs": configs,
        "q_series": q_series,
        "snap_series": snap_series,
        "acceptance": accepted / max(total, 1),
        "instanton_acceptance": (inst_accepted / inst_total) if inst_total else None,
        "sec_per_traj": sec_per_traj,
    }


def compare_observables(std_run, inst_run, beta, lattice_size, discard_frac):
    """Rigorous mean/sem/z-scores for plaquette, Wilson loops, Q^2, using only
    per-chain time-averages (see module docstring). Q^2 uses the dense
    per-step q_series; plaquette/Wilson loops use the sparser snap_series
    (batched once over config snapshots in run_chain, not every step) --
    each series gets its own discard count in its own index space."""
    targets = {"plaquette": exact.plaquette_exact(beta, ACTION_TYPE, lattice_size)}
    for name, (r, t) in OBS_LOOPS.items():
        if name in std_run["snap_series"]:
            targets[name] = exact.wilson_loop_exact(beta, r * t, ACTION_TYPE, lattice_size)
    chi_exact = exact.topological_susceptibility_exact(beta, ACTION_TYPE, lattice_size)
    targets["Q^2"] = chi_exact * lattice_size**2

    rows = []
    for name, exact_value in targets.items():
        if name == "Q^2":
            std_vals, inst_vals = std_run["q_series"] ** 2, inst_run["q_series"] ** 2
        else:
            std_vals, inst_vals = std_run["snap_series"][name], inst_run["snap_series"][name]
        std_discard = int(round(std_vals.shape[0] * discard_frac))
        inst_discard = int(round(inst_vals.shape[0] * discard_frac))
        std_mean, std_sem, _ = chain_mean_sem(std_vals, std_discard)
        inst_mean, inst_sem, _ = chain_mean_sem(inst_vals, inst_discard)
        z_std = (std_mean - exact_value) / std_sem if std_sem > 0 else float("nan")
        z_inst = (inst_mean - exact_value) / inst_sem if inst_sem > 0 else float("nan")
        pooled_sem = math.sqrt(std_sem**2 + inst_sem**2)
        z_between = (std_mean - inst_mean) / pooled_sem if pooled_sem > 0 else float("nan")
        rows.append({
            "observable": name, "exact": exact_value,
            "standard_mean": std_mean, "standard_sem": std_sem, "standard_z_exact": z_std,
            "instanton_mean": inst_mean, "instanton_sem": inst_sem, "instanton_z_exact": z_inst,
            "z_standard_vs_instanton": z_between,
        })
    return rows


def plot_case_distributions(std_configs, inst_configs, beta, lattice_size, label, case_dir):
    """Standard-HMC vs. instanton-HMC distributions, both pure HMC ensembles --
    written locally (not via diffusion.validate.report.validate_ensemble) because
    that shared function hardcodes the legend word 'generated' for its primary
    ensemble (it was written for diffusion-output-vs-reference-HMC comparisons
    elsewhere in this project), which would misleadingly suggest a diffusion
    model was involved here. There is none: both ensembles come from
    diffusion.lgt.hmc.BatchedHMC with hot_start=True, differing only in
    topological_updates=True/False."""
    std_meas = measure_ensemble(std_configs)
    inst_meas = measure_ensemble(inst_configs)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))

    ax = axes[0, 0]
    grid = np.linspace(-math.pi, math.pi, 601)
    density = exact.plaquette_angle_density(grid, beta, ACTION_TYPE)
    ax.hist(std_meas["plaq_angles"], bins=80, density=True, histtype="step", lw=1.6,
           color=STD_COLOR, label="standard HMC (plain)")
    ax.hist(inst_meas["plaq_angles"], bins=80, density=True, alpha=0.55,
           color=INST_COLOR, label="instanton HMC")
    ax.plot(grid, density, "k--", lw=1.2, label="exact (inf. volume)")
    ax.set_xlim(*_plaquette_display_window(grid, density, inst_meas["plaq_angles"],
                                           std_meas["plaq_angles"]))
    ax.set_xlabel(r"plaquette angle $\theta_p$")
    ax.set_ylabel("density")
    ax.set_title("Plaquette angle distribution")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    q_values, q_probs = exact.topological_charge_distribution(beta, lattice_size, ACTION_TYPE)
    centers = q_values.astype(float)
    width = 0.42
    std_charges, inst_charges = std_meas["topological_charge"], inst_meas["topological_charge"]
    std_hist = _q_histogram(std_charges, q_values) / max(len(std_charges), 1)
    inst_hist = _q_histogram(inst_charges, q_values) / max(len(inst_charges), 1)
    ax.bar(centers - width / 2, std_hist, width=width, alpha=0.75, color=STD_COLOR,
          label="standard HMC (plain)")
    ax.bar(centers + width / 2, inst_hist, width=width, alpha=0.75, color=INST_COLOR,
          label="instanton HMC")
    ax.plot(centers, q_probs, "k.--", lw=1.2, ms=8, label="exact P(Q)")
    ax.set_xlim(*_q_display_window(q_values, q_probs, inst_charges, std_charges))
    ax.set_xlabel("Q")
    ax.set_ylabel("P(Q)")
    ax.set_title("Topological charge distribution")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    keys = sorted((k for k in std_meas if k.startswith("wilson_")),
                 key=lambda k: tuple(int(v) for v in k.split("_")[1].split("x")))
    for key in keys:
        r, t = (int(v) for v in key.split("_")[1].split("x"))
        area = r * t
        w_exact = exact.wilson_loop_exact(beta, area, ACTION_TYPE, lattice_size)
        for meas, color, mk in ((std_meas, STD_COLOR, "s"), (inst_meas, INST_COLOR, "o")):
            mean_w = float(np.mean(meas[key]))
            if mean_w > 0:
                ax.plot(area, -math.log(mean_w), mk, color=color, ms=6)
        if w_exact > 0:
            ax.plot(area, -math.log(w_exact), "k_", ms=10)
    ax.plot([], [], "s", color=STD_COLOR, label="standard HMC (plain)")
    ax.plot([], [], "o", color=INST_COLOR, label="instanton HMC")
    ax.plot([], [], "k_", label="exact")
    ax.set_xlabel("loop area A")
    ax.set_ylabel(r"$-\log\langle W(A)\rangle$")
    ax.set_title("Wilson loops / string tension")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    if "wilson_2x2" in std_meas:
        vals_s, vals_i = np.asarray(std_meas["wilson_2x2"]), np.asarray(inst_meas["wilson_2x2"])
        w_exact = exact.wilson_loop_exact(beta, 4, ACTION_TYPE, lattice_size)
        lo = min(vals_s.min(), vals_i.min(), w_exact)
        hi = max(vals_s.max(), vals_i.max(), w_exact)
        pad = 0.06 * (hi - lo) if hi > lo else 0.01
        bins = np.linspace(lo - pad, hi + pad, 37)
        ax.hist(vals_s, bins=bins, density=True, histtype="step", lw=1.6, color=STD_COLOR,
               label="standard HMC (plain)")
        ax.hist(vals_i, bins=bins, density=True, alpha=0.55, color=INST_COLOR,
               label="instanton HMC")
        ax.axvline(w_exact, color=INK, ls="--", lw=1.2, label="exact mean")
        ax.set_title(r"$W(2\times2)$ distribution")
        ax.legend(fontsize=8)
    else:
        ax.axis("off")

    fig.suptitle(f"Standard vs. instanton HMC (both pure HMC, no diffusion model): "
                f"L={lattice_size}, beta={beta:g}, {ACTION_TYPE}", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(Path(case_dir) / f"{label}_distributions.png", dpi=130)
    plt.close(fig)


def run_case(lattice_size, beta, n_chains, burn_in, n_prod, config_stride, device, seed, out_dir):
    action = make_action(ACTION_TYPE, beta)
    step_size, n_steps = adapted_hmc_params(beta)
    label = f"L{lattice_size}_beta{beta:g}"
    case_dir = out_dir / label
    case_dir.mkdir(parents=True, exist_ok=True)

    standard = run_chain(lattice_size, action, n_chains, step_size, n_steps, burn_in,
                         n_prod, False, device, seed, config_stride)
    instanton = run_chain(lattice_size, action, n_chains, step_size, n_steps, burn_in,
                          n_prod, True, device, seed + 1, config_stride)

    std_freeze = freezing_stats(standard["q_series"])
    inst_freeze = freezing_stats(instanton["q_series"])

    obs_rows = compare_observables(standard, instanton, beta, lattice_size, DISCARD_FRAC)

    std_dist = standard["configs"].reshape(-1, 2, lattice_size, lattice_size)
    inst_dist = instanton["configs"].reshape(-1, 2, lattice_size, lattice_size)
    plot_case_distributions(std_dist, inst_dist, beta, lattice_size, label, case_dir)

    save_ensemble(case_dir / f"{label}_standard_dist.pt", std_dist, {
        "beta": beta, "lattice_size": lattice_size, "action_type": ACTION_TYPE,
        "provenance": "plain HMC (no Q-hops), hot start, config snapshots every "
                      f"{config_stride} trajectories",
    })
    save_ensemble(case_dir / f"{label}_instanton_dist.pt", inst_dist, {
        "beta": beta, "lattice_size": lattice_size, "action_type": ACTION_TYPE,
        "provenance": "instanton-update HMC (Q-hop every step), hot start, config "
                      f"snapshots every {config_stride} trajectories",
    })
    np.savez_compressed(case_dir / f"{label}_q_series.npz",
                        standard=standard["q_series"], instanton=instanton["q_series"])

    result = {
        "label": label, "lattice_size": lattice_size, "beta": beta,
        "step_size": step_size, "n_steps": n_steps, "n_chains": n_chains,
        "burn_in": burn_in, "n_prod": n_prod, "discard_frac": DISCARD_FRAC,
        "standard": {"acceptance": standard["acceptance"],
                    "sec_per_traj": standard["sec_per_traj"], **std_freeze},
        "instanton": {"acceptance": instanton["acceptance"],
                     "instanton_move_acceptance": instanton["instanton_acceptance"],
                     "sec_per_traj": instanton["sec_per_traj"], **inst_freeze},
        "observables": obs_rows,
    }
    save_json(case_dir / f"{label}_summary.json", _json_clean(result))
    return result


def _obs_row(rows, name):
    return next((r for r in rows if r["observable"] == name), {})


def plot_acceptance(records, out_path, lattice_size):
    betas = sorted(r["beta"] for r in records.values())
    hmc_std = [records[f"L{lattice_size}_beta{b:g}"]["standard"]["acceptance"] for b in betas]
    hmc_inst = [records[f"L{lattice_size}_beta{b:g}"]["instanton"]["acceptance"] for b in betas]
    inst_move = [records[f"L{lattice_size}_beta{b:g}"]["instanton"]["instanton_move_acceptance"]
                for b in betas]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(betas, hmc_std, "o-", color=STD_COLOR, label="Omelyan step (standard HMC)")
    ax.plot(betas, hmc_inst, "s--", color=STD_COLOR, alpha=0.5,
           label="Omelyan step (instanton HMC)")
    ax.plot(betas, inst_move, "^-", color=INST_COLOR, lw=2, label="instanton move")
    ax.set_xscale("log")
    ax.set_xlabel(r"$\beta$")
    ax.set_ylabel("acceptance rate")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(f"HMC step acceptance vs. instanton-move acceptance (L={lattice_size})")
    ax.legend(fontsize=9, frameon=False)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_tunneling(records, out_path, lattice_size, n_prod, n_chains):
    betas = sorted(r["beta"] for r in records.values())
    std_tunnel = [records[f"L{lattice_size}_beta{b:g}"]["standard"]["n_tunnelings"] for b in betas]
    inst_tunnel = [records[f"L{lattice_size}_beta{b:g}"]["instanton"]["n_tunnelings"] for b in betas]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(betas, np.maximum(std_tunnel, 0.5), "o-", color=STD_COLOR, label="standard HMC")
    ax.plot(betas, np.maximum(inst_tunnel, 0.5), "^-", color=INST_COLOR, lw=2, label="instanton HMC")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$\beta$")
    ax.set_ylabel(f"# topological tunnelings ({n_prod} trajectories x {n_chains} chains)")
    ax.set_title("Topological-charge tunneling rate: freezing vs. beta")
    ax.legend(fontsize=9, frameon=False)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_charge_traces(out_dir, betas, lattice_size, n_prod, method_key, method_label, out_path,
                       chain_index=0):
    """Stacked Q(t) traces, one panel per beta, normalized time axis -- same
    visual language as standard freezing-demonstration plots in the literature."""
    colors = plt.cm.viridis(np.linspace(0.05, 0.9, len(betas)))
    fig, axes = plt.subplots(len(betas), 1, figsize=(9, 1.35 * len(betas) + 1.0), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, beta, color in zip(axes, betas, colors):
        label = f"L{lattice_size}_beta{beta:g}"
        npz_path = out_dir / label / f"{label}_q_series.npz"
        q_series = np.load(npz_path)[method_key][:, chain_index]
        t = np.linspace(0.0, 1.0, len(q_series))
        n_tunnelings = int(np.sum(np.abs(np.diff(np.round(q_series))) > 0))
        ax.plot(t, q_series, color=color, lw=0.6)
        ax.axhline(0, color=GRID_COLOR, lw=0.8, zorder=0)
        ax.text(0.99, 0.88, f"$\\beta = {beta:g}$", transform=ax.transAxes,
               ha="right", va="top", fontsize=10, color=INK)
        ax.text(0.01, 0.06, f"{n_tunnelings:,} tunnelings", transform=ax.transAxes,
               ha="left", va="bottom", fontsize=8.5, color=MUTED)
        ax.set_ylabel("Q", fontsize=9)
        ax.tick_params(labelsize=8, colors=MUTED)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    axes[-1].set_xlim(0.0, 1.0)
    axes[-1].set_xlabel("normalized trajectory index", fontsize=9)
    fig.suptitle(f"L={lattice_size} {method_label}: single-chain topological charge "
                f"vs. $\\beta$ ({n_prod} trajectories/chain)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def write_report(records, out_dir, lattice_size, n_chains, burn_in, n_prod, discard_frac):
    betas = sorted(r["beta"] for r in records.values())
    lines = [
        "# Instanton-update HMC vs. standard HMC",
        "",
        "**Claim under test.** The instanton move (`diffusion.lgt.local_updates."
        "topological_update`) is a *global* Metropolis proposal that adds a smooth "
        "Q = +-1 configuration to the whole lattice; its action cost is "
        "`delta_S ~ O(beta / V)`, so its acceptance rate should stay roughly "
        "beta-independent. Standard HMC can only change Q by having its local "
        "leapfrog dynamics climb an action barrier that grows with beta, so its "
        "topological-charge tunneling rate should collapse (freeze) at large beta "
        "while instanton HMC's does not.",
        "",
        f"Matched chains at each beta: same L={lattice_size}, step_size/n_steps "
        f"(`adapted_hmc_params`), hot start, {n_chains} parallel chains, "
        f"{burn_in} burn-in + {n_prod} recorded trajectories.",
        "",
        "**Error bars.** The only rigorously independent statistical unit is a chain "
        "(different Markov chains = independent noise). Every mean/error below is "
        f"computed from the {n_chains} per-chain time-averages, discarding the first "
        f"{discard_frac:.0%} of the recorded window as extra equilibration margin "
        "within production (Q^2 uses the dense per-step charge series; plaquette/"
        "Wilson loops use the periodic config snapshots) -- never by pooling all "
        "(time x chain) samples into one estimator, which would silently assume "
        "time-adjacent draws are as independent as different chains.",
        "",
        "## Charge traces",
        "",
        "![standard traces](standard_traces.png)",
        "",
        "![instanton traces](instanton_traces.png)",
        "",
        "Single representative chain per beta, full recorded window. Standard HMC's "
        "trace visibly locks onto one charge sector as beta grows; instanton HMC's "
        "keeps hopping across the same beta range.",
        "",
        "## Acceptance rates",
        "",
        "![acceptance](acceptance_vs_beta.png)",
        "",
        "| beta | HMC step (standard) | HMC step (instanton run) | instanton move |",
        "|---|---|---|---|",
    ]
    for b in betas:
        r = records[f"L{lattice_size}_beta{b:g}"]
        lines.append(
            f"| {b:g} | {r['standard']['acceptance']:.3f} | "
            f"{r['instanton']['acceptance']:.3f} | "
            f"{r['instanton']['instanton_move_acceptance']:.3f} |"
        )
    lines += [
        "",
        "The Omelyan step's acceptance is statistically the same whether or not the "
        "instanton move is enabled (it does not touch the leapfrog trajectory), which "
        "is the sanity check that adding the instanton move does not disturb the base "
        "sampler. The instanton move's own acceptance decays with beta but far more "
        "gently than standard HMC's tunneling rate, which hits exactly zero.",
        "",
        "## Topological freezing",
        "",
        "![tunneling](tunneling_vs_beta.png)",
        "",
        "| beta | standard: n_tunnelings | standard: frozen | instanton: n_tunnelings "
        "| instanton: frozen |",
        "|---|---|---|---|---|",
    ]
    for b in betas:
        r = records[f"L{lattice_size}_beta{b:g}"]
        lines.append(
            f"| {b:g} | {r['standard']['n_tunnelings']} | {r['standard']['frozen']} | "
            f"{r['instanton']['n_tunnelings']} | {r['instanton']['frozen']} |"
        )
    lines += [
        "",
        "## Observables vs. exact (per-chain mean +- sem, z-scores)",
        "",
        "| beta | obs | standard mean +- sem | z (std vs exact) | instanton mean +- "
        "sem | z (inst vs exact) | z (std vs inst) |",
        "|---|---|---|---|---|---|---|",
    ]
    for b in betas:
        r = records[f"L{lattice_size}_beta{b:g}"]
        for name in ("plaquette", "wilson_2x2", "wilson_4x4", "Q^2"):
            row = _obs_row(r["observables"], name)
            if not row:
                continue
            lines.append(
                f"| {b:g} | {name} | {row['standard_mean']:.4g} +- {row['standard_sem']:.2g} | "
                f"{row['standard_z_exact']:+.2f} | {row['instanton_mean']:.4g} +- "
                f"{row['instanton_sem']:.2g} | {row['instanton_z_exact']:+.2f} | "
                f"{row['z_standard_vs_instanton']:+.2f} |"
            )
    lines += [
        "",
        "At low beta (2, 4) standard and instanton agree closely with each other and "
        "with exact on every observable -- both samplers are ergodic there. Once "
        "standard HMC freezes (beta >= 16), its plaquette and Wilson-loop z-scores "
        "also grow large, not just Q^2: the per-case distribution plots below show "
        "standard HMC's plaquette-angle histogram visibly broader than exact and its "
        "Wilson-loop string tension systematically overestimated at the same beta "
        "where instanton HMC's ensemble still tracks exact closely. Reading: once a "
        "chain is stuck in the wrong topological sector, that failure contaminates "
        "every observable, not just Q, because the true equilibrium distribution "
        "mixes across sectors -- the instanton move's benefit is broader than 'fixes "
        "topology', it restores general ergodicity. Instanton HMC's own z-scores also "
        "grow somewhat with beta (a fixed burn-in budget likely stops being enough for "
        "either method as beta grows), but consistently far less than standard's.",
        "",
        "## Per-case distribution plots",
        "",
    ]
    for b in betas:
        label = f"L{lattice_size}_beta{b:g}"
        lines.append(f"- `{label}/{label}_distributions.png`: plaquette-angle, P(Q), and "
                     f"Wilson-loop distributions -- standard HMC vs. instanton HMC vs. exact "
                     f"(both ensembles are pure HMC; no diffusion model involved anywhere in "
                     f"this script).")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--replot", action="store_true",
                        help="regenerate per-case distribution plots from the saved "
                        "ensembles without rerunning any HMC (use after fixing plot code)")
    parser.add_argument("--betas", default=None,
                        help="comma-separated subset of betas to run (for sharding "
                        "across parallel processes); others left untouched")
    args = parser.parse_args()

    out = Path(args.out_dir) if args.out_dir else (OUT_DIR / "smoke" if args.smoke else OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    records: dict = {}
    if summary_path.exists():
        records = json.loads(summary_path.read_text(encoding="utf-8"))

    betas = SMOKE_BETAS if args.smoke else BETAS
    if args.betas:
        wanted = {float(v) for v in args.betas.split(",")}
        betas = [b for b in betas if b in wanted]
    lattice_size = SMOKE_LATTICE_SIZE if args.smoke else LATTICE_SIZE
    n_chains = SMOKE_N_CHAINS if args.smoke else N_CHAINS
    burn_in = SMOKE_BURN_IN if args.smoke else BURN_IN
    n_prod = SMOKE_N_PROD if args.smoke else N_PROD
    config_stride = SMOKE_CONFIG_STRIDE if args.smoke else CONFIG_STRIDE

    if args.replot:
        for label, r in records.items():
            case_dir = out / label
            std_path = case_dir / f"{label}_standard_dist.pt"
            inst_path = case_dir / f"{label}_instanton_dist.pt"
            if not (std_path.exists() and inst_path.exists()):
                print(f"{label}: missing saved ensembles, skipping replot", flush=True)
                continue
            std_dist, _ = load_ensemble(std_path)
            inst_dist, _ = load_ensemble(inst_path)
            plot_case_distributions(std_dist, inst_dist, r["beta"], r["lattice_size"],
                                    label, case_dir)
            print(f"{label}: replotted", flush=True)

    if not args.report_only and not args.replot:
        device = "cpu"
        for i, beta in enumerate(betas):
            label = f"L{lattice_size}_beta{beta:g}"
            if label in records:
                print(f"[{i+1}/{len(betas)}] {label}: already done, skipping", flush=True)
                continue
            print(f"[{i+1}/{len(betas)}] {label}: running matched standard/instanton chains "
                 f"({n_chains} chains, {burn_in}+{n_prod} trajectories each)", flush=True)
            result = run_case(lattice_size, beta, n_chains, burn_in, n_prod, config_stride,
                              device, args.seed, out)
            records[label] = result
            save_json(summary_path, records)
            print(f"    standard acceptance={result['standard']['acceptance']:.3f} "
                 f"tunnelings={result['standard']['n_tunnelings']}  |  "
                 f"instanton acceptance={result['instanton']['acceptance']:.3f} "
                 f"instanton_move={result['instanton']['instanton_move_acceptance']:.3f} "
                 f"tunnelings={result['instanton']['n_tunnelings']}", flush=True)

    done_betas = sorted(r["beta"] for r in records.values() if r["lattice_size"] == lattice_size)
    if done_betas:
        plot_acceptance(records, out / "acceptance_vs_beta.png", lattice_size)
        plot_tunneling(records, out / "tunneling_vs_beta.png", lattice_size, n_prod, n_chains)
        plot_charge_traces(out, done_betas, lattice_size, n_prod, "standard", "standard HMC",
                           out / "standard_traces.png")
        plot_charge_traces(out, done_betas, lattice_size, n_prod, "instanton", "instanton HMC",
                           out / "instanton_traces.png")
        write_report(records, out, lattice_size, n_chains, burn_in, n_prod, DISCARD_FRAC)
    print(f"summary: {summary_path}")
    print(f"report:  {out / 'report.md'}")


if __name__ == "__main__":
    main()
