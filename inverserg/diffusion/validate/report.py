"""Validation reports: generated vs exact and vs held-out HMC ensembles.

Single entry points:
    validate_ensemble(...) -> rows + figures for one ensemble
    validate_ladder(...)   -> per-rung reports + drift summary
    write_report(...)      -> markdown summary table
"""

import math
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scipy.stats import ks_2samp, chisquare

from ..lgt import exact
from .observables import measure_ensemble
from .stats import binned_mean_err, z_score, integrated_autocorrelation_time


def _q_histogram(charges: np.ndarray, q_values: np.ndarray) -> np.ndarray:
    counts = np.zeros(len(q_values))
    for i, q in enumerate(q_values):
        counts[i] = np.sum(np.round(charges) == q)
    return counts


def validate_ensemble(
    configs: torch.Tensor,
    beta: float,
    action_type: str = "wilson",
    reference_configs: torch.Tensor | None = None,
    label: str = "ensemble",
    output_dir: str | Path | None = None,
    make_plots: bool = True,
) -> list[dict]:
    """Compare an ensemble against exact formulas and (optionally) a reference ensemble.

    Returns a list of row dicts: observable, value, error, exact, z_exact,
    reference, ref_error, z_ref, ks_p (two-sample vs reference where defined).
    """
    lattice_size = configs.shape[-1]
    meas = measure_ensemble(configs)
    ref = measure_ensemble(reference_configs) if reference_configs is not None else None
    rows = []

    def add_row(name, values, exact_value, ref_values=None, scalar=None):
        if values is not None:
            value, err = binned_mean_err(np.asarray(values))
        else:
            value, err = scalar, float("nan")
        row = {"observable": name, "value": value, "error": err, "exact": exact_value}
        row["z_exact"] = (
            z_score(value, err, exact_value)
            if exact_value is not None and not math.isnan(err)
            else float("nan")
        )
        if ref_values is not None:
            rv, re = binned_mean_err(np.asarray(ref_values))
            row["reference"] = rv
            row["ref_error"] = re
            row["z_ref"] = z_score(value, err, rv, re)
            if values is not None and np.asarray(values).ndim == 1 and len(np.asarray(values)) > 3:
                row["ks_p"] = float(ks_2samp(np.asarray(values), np.asarray(ref_values)).pvalue)
        rows.append(row)

    add_row(
        "plaquette",
        meas["plaquette"],
        exact.plaquette_exact(beta, action_type, lattice_size),
        ref["plaquette"] if ref else None,
    )
    for key in sorted(k for k in meas if k.startswith("wilson_")):
        r, t = (int(v) for v in key.split("_")[1].split("x"))
        add_row(
            key,
            meas[key],
            exact.wilson_loop_exact(beta, r * t, action_type, lattice_size),
            ref[key] if ref and key in ref else None,
        )
    sigma_exact = exact.string_tension_exact(beta, action_type)
    for r in (2, 3):
        if f"creutz_{r}" in meas:
            add_row(
                f"creutz_{r}",
                None,
                sigma_exact,
                None,
                scalar=meas[f"creutz_{r}"],
            )

    charges = meas["topological_charge"]
    volume = lattice_size * lattice_size
    chi_exact = exact.topological_susceptibility_exact(beta, action_type, lattice_size)
    add_row(
        "chi_top*V (<Q^2>-<Q>^2)",
        (charges - charges.mean()) ** 2,
        chi_exact * volume,
        ((ref["topological_charge"] - ref["topological_charge"].mean()) ** 2) if ref else None,
    )

    q_values, q_probs = exact.topological_charge_distribution(beta, lattice_size, action_type)
    counts = _q_histogram(charges, q_values)
    expected = q_probs * len(charges)
    keep = expected > 2.0
    if keep.sum() > 1 and counts[keep].sum() > 0:
        scale = counts[keep].sum() / expected[keep].sum()
        chi2 = chisquare(counts[keep], expected[keep] * scale)
        rows.append(
            {
                "observable": "Q histogram vs exact P(Q)",
                "value": float(chi2.statistic),
                "error": float("nan"),
                "exact": float(keep.sum() - 1),
                "z_exact": float("nan"),
                "chi2_p": float(chi2.pvalue),
            }
        )

    if output_dir is not None and make_plots:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        _make_plots(meas, ref, beta, action_type, lattice_size, q_values, q_probs, label, output_dir)

    return rows


def _make_plots(meas, ref, beta, action_type, lattice_size, q_values, q_probs, label, output_dir):
    grid = np.linspace(-math.pi, math.pi, 601)
    density = exact.plaquette_angle_density(grid, beta, action_type)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))

    ax = axes[0, 0]
    ax.hist(meas["plaq_angles"], bins=80, density=True, alpha=0.55, label="generated")
    if ref is not None:
        ax.hist(
            ref["plaq_angles"], bins=80, density=True, histtype="step", lw=1.6, label="reference HMC"
        )
    ax.plot(grid, density, "k--", lw=1.2, label="exact (inf. volume)")
    ax.set_xlabel(r"plaquette angle $\theta_p$")
    ax.set_ylabel("density")
    ax.set_title(f"Plaquette angle distribution ({label})")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    charges = meas["topological_charge"]
    centers = q_values.astype(float)
    width = 0.38
    gen_hist = _q_histogram(charges, q_values) / max(len(charges), 1)
    ax.bar(centers - width / 2, gen_hist, width=width, alpha=0.7, label="generated")
    if ref is not None:
        ref_hist = _q_histogram(ref["topological_charge"], q_values) / max(
            len(ref["topological_charge"]), 1
        )
        ax.bar(centers + width / 2, ref_hist, width=width, alpha=0.7, label="reference HMC")
    ax.plot(centers, q_probs, "k.--", lw=1.2, ms=8, label="exact P(Q)")
    ax.set_xlabel("Q")
    ax.set_ylabel("P(Q)")
    ax.set_title("Topological charge distribution")
    ax.legend(fontsize=8)

    ax = axes[1, 0]
    areas, neg_log_w, exact_line = [], [], []
    for key in sorted(k for k in meas if k.startswith("wilson_")):
        r, t = (int(v) for v in key.split("_")[1].split("x"))
        mean_w = meas[key].mean()
        if mean_w > 0:
            areas.append(r * t)
            neg_log_w.append(-math.log(mean_w))
            exact_line.append(-math.log(exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)))
    ax.plot(areas, neg_log_w, "o", label="generated")
    if ref is not None:
        ref_pts = [
            (-math.log(ref[k].mean()), int(k.split("_")[1].split("x")[0]) * int(k.split("_")[1].split("x")[1]))
            for k in sorted(ref)
            if k.startswith("wilson_") and ref[k].mean() > 0
        ]
        ax.plot([a for _, a in ref_pts], [v for v, _ in ref_pts], "s", mfc="none", label="reference HMC")
    ax.plot(areas, exact_line, "k--", label="exact area law")
    ax.set_xlabel("loop area A")
    ax.set_ylabel(r"$-\log \langle W(A) \rangle$")
    ax.set_title("Wilson loops / string tension")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    corr = meas["plaq_correlator"]
    dists = np.arange(1, len(corr) + 1)
    ax.plot(dists, np.abs(corr), "o-", label="generated |C(d)|")
    if ref is not None:
        rcorr = ref["plaq_correlator"]
        ax.plot(np.arange(1, len(rcorr) + 1), np.abs(rcorr), "s--", mfc="none", label="reference |C(d)|")
    ax.set_yscale("log")
    ax.set_xlabel("distance d")
    ax.set_ylabel(r"$|\langle \cos\theta_p(0) \cos\theta_p(d) \rangle_c|$")
    ax.set_title("Connected plaquette correlator")
    ax.legend(fontsize=8)

    fig.suptitle(f"{label}: L={lattice_size}, beta={beta}, {action_type}")
    fig.tight_layout()
    fig.savefig(Path(output_dir) / f"{label}.png", dpi=130)
    plt.close(fig)


def validate_ladder(
    rung_results,
    action_type: str = "wilson",
    reference_map: dict | None = None,
    output_dir: str | Path = "artifacts/diffusion/validation",
) -> dict:
    """Validate every rung of a generated ladder. reference_map: {(L, beta): configs}."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_rows = {}
    drift = []
    for i, rung in enumerate(rung_results):
        key = (rung.lattice_size, rung.beta)
        reference = reference_map.get(key) if reference_map else None
        label = f"rung{i}_L{rung.lattice_size}_beta{rung.beta:g}"
        rows = validate_ensemble(
            rung.configs,
            rung.beta,
            action_type,
            reference_configs=reference,
            label=label,
            output_dir=output_dir,
        )
        all_rows[label] = rows
        plaq_row = next(r for r in rows if r["observable"] == "plaquette")
        drift.append(
            {
                "rung": i,
                "L": rung.lattice_size,
                "beta": rung.beta,
                "plaq_deviation": plaq_row["value"] - plaq_row["exact"],
                "plaq_z": plaq_row["z_exact"],
            }
        )

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.axhline(0.0, color="k", lw=0.8)
    ax.plot([d["rung"] for d in drift], [d["plaq_z"] for d in drift], "o-")
    ax.set_xlabel("rung")
    ax.set_ylabel("plaquette z-score vs exact")
    ax.set_title("Bias drift along the ladder")
    fig.tight_layout()
    fig.savefig(output_dir / "ladder_drift.png", dpi=130)
    plt.close(fig)

    return {"rows": all_rows, "drift": drift}


def freezing_diagnostics(charge_series: np.ndarray, label: str = "") -> dict:
    """tau_int of the topological charge time series (demonstrates HMC freezing).

    A series that never (or almost never) tunnels has tau_int bounded below by the
    series length; report it as such rather than the meaningless windowed estimate.
    """
    series = np.asarray(charge_series, dtype=float)
    n_jumps = int(np.sum(np.abs(np.diff(np.round(series))) > 0))
    if series.var() == 0 or n_jumps < 3:
        return {
            "label": label,
            "tau_int_Q": float(len(series)),
            "tau_int_Q_err": float("nan"),
            "n_tunnelings": n_jumps,
            "frozen": True,
        }
    tau, tau_err = integrated_autocorrelation_time(series)
    return {
        "label": label,
        "tau_int_Q": tau,
        "tau_int_Q_err": tau_err,
        "n_tunnelings": n_jumps,
        "frozen": False,
    }


def write_report(all_rows: dict, path: str | Path, header: str = "") -> None:
    """Write a markdown summary: one table per ensemble label."""
    lines = [f"# Validation report", ""]
    if header:
        lines += [header, ""]
    for label, rows in all_rows.items():
        lines += [f"## {label}", ""]
        cols = ["observable", "value", "error", "exact", "z_exact", "reference", "ref_error", "z_ref", "ks_p", "chi2_p"]
        present = [c for c in cols if any(c in r for r in rows)]
        lines.append("| " + " | ".join(present) + " |")
        lines.append("|" + "---|" * len(present))
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
        lines.append("")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
