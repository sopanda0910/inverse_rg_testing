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


GEN_COLOR = "#2a78d6"
REF_COLOR = "#1baf7a"
INK = "#0b0b0b"
MUTED = "#898781"
GRID_COLOR = "#e1e0d9"


def _loop_dims(key: str) -> tuple[int, int]:
    r, t = (int(v) for v in key.split("_")[1].split("x"))
    return r, t


def _sorted_wilson_keys(meas: dict) -> list[str]:
    keys = [k for k in meas if k.startswith("wilson_")]
    return sorted(keys, key=lambda k: (_loop_dims(k)[0] * _loop_dims(k)[1], _loop_dims(k)))


def _q_histogram(charges: np.ndarray, q_values: np.ndarray) -> np.ndarray:
    counts = np.zeros(len(q_values))
    for i, q in enumerate(q_values):
        counts[i] = np.sum(np.round(charges) == q)
    return counts


def _q_display_window(
    q_values: np.ndarray, q_probs: np.ndarray, charges: np.ndarray,
    ref_charges: np.ndarray | None, mass: float = 0.995, pad: float = 1.5,
) -> tuple[float, float]:
    """P(Q) is plotted over the full numerically-conservative q_max (6 sigma) so
    the closed-form PMF integrates cleanly, but at low beta that leaves the
    visible bars stretched thin across dozens of mostly-empty integer bins with
    only O(100) samples -- a noisy comb instead of a legible histogram. Crop the
    x-axis to the smallest symmetric window holding `mass` of the exact
    probability, WIDENED to always cover the full empirical range of both
    ensembles (never crop away a populated bin, e.g. a frozen chain's spurious
    sector -- that is exactly the signal these plots exist to show)."""
    order = np.argsort(-q_probs)
    cum = np.cumsum(q_probs[order])
    keep = order[: max(3, int(np.searchsorted(cum, mass)) + 1)]
    q_lo, q_hi = q_values[keep].min(), q_values[keep].max()
    samples = [charges]
    if ref_charges is not None:
        samples.append(ref_charges)
    all_q = np.round(np.concatenate(samples))
    if all_q.size:
        q_lo = min(q_lo, all_q.min())
        q_hi = max(q_hi, all_q.max())
    half = max(abs(q_lo), abs(q_hi), 3) + pad
    return -half, half


def validate_ensemble(
    configs: torch.Tensor,
    beta: float,
    action_type: str = "wilson",
    reference_configs: torch.Tensor | None = None,
    label: str = "ensemble",
    output_dir: str | Path | None = None,
    make_plots: bool = True,
    reference_label: str = "reference HMC",
) -> list[dict]:
    """Compare an ensemble against exact formulas and (optionally) a reference ensemble.

    reference_label: legend text for reference_configs in the plots -- defaults
    to the Q-hop-enabled unbiased reference used throughout the project, but
    should be overridden (e.g. "plain HMC (hot start)") when reference_configs
    is a biased/frozen ensemble used deliberately to illustrate that bias.

    Returns a list of row dicts: observable, value, error, exact, z_exact,
    reference, ref_error, z_ref, ks_p (two-sample vs reference where defined).
    """
    lattice_size = configs.shape[-1]
    meas = measure_ensemble(configs)
    ref = measure_ensemble(reference_configs) if reference_configs is not None else None
    rows = []

    def add_row(name, values, exact_value, ref_values=None, scalar=None, scalar_err=None):
        if values is not None:
            value, err = binned_mean_err(np.asarray(values))
        else:
            value = scalar
            err = float("nan") if scalar_err is None else scalar_err
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
    for key in _sorted_wilson_keys(meas):
        r, t = _loop_dims(key)
        add_row(
            key,
            meas[key],
            exact.wilson_loop_exact(beta, r * t, action_type, lattice_size),
            ref[key] if ref and key in ref else None,
        )
    creutz_rs = sorted(
        int(k.split("_")[1]) for k in meas if k.startswith("creutz_") and not k.endswith("_err")
    )
    for r in creutz_rs:
        w_rr = exact.wilson_loop_exact(beta, r * r, action_type, lattice_size)
        w_ss = exact.wilson_loop_exact(beta, (r - 1) * (r - 1), action_type, lattice_size)
        w_rs = exact.wilson_loop_exact(beta, r * (r - 1), action_type, lattice_size)
        creutz_exact = -math.log(w_rr * w_ss / w_rs**2)
        add_row(
            f"creutz_{r}",
            None,
            creutz_exact,
            None,
            scalar=meas[f"creutz_{r}"],
            scalar_err=meas.get(f"creutz_{r}_err"),
        )

    charges = meas["topological_charge"]
    ref_charges = ref["topological_charge"] if ref else None
    volume = lattice_size * lattice_size
    chi_exact = exact.topological_susceptibility_exact(beta, action_type, lattice_size)
    add_row("Q", charges, 0.0, ref_charges)
    add_row(
        "Q^2",
        charges**2,
        chi_exact * volume,
        ref_charges**2 if ref is not None else None,
    )
    add_row(
        "chi_top ((<Q^2>-<Q>^2)/V)",
        (charges - charges.mean()) ** 2 / volume,
        chi_exact,
        ((ref_charges - ref_charges.mean()) ** 2 / volume) if ref is not None else None,
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
        _make_plots(meas, ref, beta, action_type, lattice_size, q_values, q_probs, label,
                   output_dir, reference_label)
        _plot_wilson_distributions(meas, ref, beta, action_type, lattice_size, label,
                                   output_dir, reference_label)

    return rows


def _plot_wilson_distributions(meas, ref, beta, action_type, lattice_size, label, output_dir,
                               reference_label="reference HMC"):
    """One histogram panel per loop size: per-config loop averages, generated vs
    reference HMC, with the exact expectation marked."""
    keys = _sorted_wilson_keys(meas)
    if not keys:
        return
    ncols = 4
    nrows = math.ceil(len(keys) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 2.7 * nrows))
    axes = np.atleast_1d(axes).reshape(nrows, ncols)
    for ax, key in zip(axes.flat, keys):
        r, t = _loop_dims(key)
        vals = np.asarray(meas[key])
        lo, hi = vals.min(), vals.max()
        if ref is not None and key in ref:
            rvals = np.asarray(ref[key])
            lo, hi = min(lo, rvals.min()), max(hi, rvals.max())
        w_exact = exact.wilson_loop_exact(beta, r * t, action_type, lattice_size)
        lo, hi = min(lo, w_exact), max(hi, w_exact)
        pad = 0.06 * (hi - lo) if hi > lo else 0.01
        bins = np.linspace(lo - pad, hi + pad, 37)
        ax.hist(vals, bins=bins, density=True, color=GEN_COLOR, alpha=0.55, label="generated")
        if ref is not None and key in ref:
            ax.hist(rvals, bins=bins, density=True, histtype="step", lw=1.6,
                    color=REF_COLOR, label=reference_label)
        ax.axvline(w_exact, color=INK, ls="--", lw=1.2, label="exact mean")
        ax.set_title(f"$W({r}\\times{t})$  (area {r * t})", fontsize=9, color=INK)
        ax.set_yticks([])
        ax.tick_params(labelsize=7, colors=MUTED)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    for ax in axes.flat[len(keys):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=8, frameon=False)
    fig.suptitle(
        f"{label}: per-config Wilson loop distributions (L={lattice_size}, beta={beta:g}, {action_type})",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(Path(output_dir) / f"{label}_wilson_dists.png", dpi=130)
    plt.close(fig)


def _make_plots(meas, ref, beta, action_type, lattice_size, q_values, q_probs, label, output_dir,
                reference_label="reference HMC"):
    grid = np.linspace(-math.pi, math.pi, 601)
    density = exact.plaquette_angle_density(grid, beta, action_type)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))

    ax = axes[0, 0]
    ax.hist(meas["plaq_angles"], bins=80, density=True, alpha=0.55, label="generated")
    if ref is not None:
        ax.hist(
            ref["plaq_angles"], bins=80, density=True, histtype="step", lw=1.6, label=reference_label
        )
    ax.plot(grid, density, "k--", lw=1.2, label="exact (inf. volume)")
    ax.set_xlabel(r"plaquette angle $\theta_p$")
    ax.set_ylabel("density")
    ax.set_title(f"Plaquette angle distribution ({label})")
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    charges = meas["topological_charge"]
    centers = q_values.astype(float)
    width = 0.42
    gen_hist = _q_histogram(charges, q_values) / max(len(charges), 1)
    ax.bar(centers - width / 2, gen_hist, width=width, alpha=0.7, label="generated")
    if ref is not None:
        ref_hist = _q_histogram(ref["topological_charge"], q_values) / max(
            len(ref["topological_charge"]), 1
        )
        ax.bar(centers + width / 2, ref_hist, width=width, alpha=0.7, label=reference_label)
    ax.plot(centers, q_probs, "k.--", lw=1.2, ms=8, label="exact P(Q)")
    ax.set_xlim(*_q_display_window(q_values, q_probs, charges,
                                   ref["topological_charge"] if ref is not None else None))
    ax.set_xlabel("Q")
    ax.set_ylabel("P(Q)")
    ax.set_title("Topological charge distribution")
    ax.legend(fontsize=8)

    ax = axes[1, 0]

    def loop_stats(source):
        out = []
        for key in _sorted_wilson_keys(source):
            r, t = _loop_dims(key)
            mean_w, err = binned_mean_err(np.asarray(source[key]))
            out.append((r * t, mean_w, err))
        return out

    # -log<W(A)> is only meaningful where the exact signal e^{-sigma A} clears the
    # ensemble's statistical noise; past that area every estimate (generated and
    # HMC alike) is noise around zero and would plot as a spurious plateau at
    # -log(noise), far off the area law. Show only resolvable loops and mark the
    # noise floor explicitly.
    gen_stats = loop_stats(meas)
    exact_w = {a: exact.wilson_loop_exact(beta, a, action_type, lattice_size)
               for a, _, _ in gen_stats}
    n_noise = sum(1 for a, _, e in gen_stats if exact_w[a] <= 3.0 * e)
    gen_pts = [(a, m, e) for a, m, e in gen_stats if exact_w[a] > 3.0 * e and m > 0]
    if gen_pts:
        ax.errorbar([p[0] for p in gen_pts], [-math.log(p[1]) for p in gen_pts],
                    yerr=[p[2] / p[1] for p in gen_pts], fmt="o", ms=5,
                    color=GEN_COLOR, capsize=2, label="generated", zorder=4)
    if ref is not None:
        ref_pts = [(a, m, e) for a, m, e in loop_stats(ref)
                   if a in exact_w and exact_w[a] > 3.0 * e and m > 0]
        if ref_pts:
            ax.errorbar([p[0] for p in ref_pts], [-math.log(p[1]) for p in ref_pts],
                        yerr=[p[2] / p[1] for p in ref_pts], fmt="s", ms=5, mfc="none",
                        color=REF_COLOR, capsize=2, label=reference_label, zorder=3)
    line_areas = sorted(p[0] for p in gen_pts) or sorted(exact_w)
    ax.plot(line_areas, [-math.log(exact_w[a]) for a in line_areas], "--", color=INK,
            lw=1.2, label="exact area law", zorder=2)
    if n_noise and gen_pts:
        floor = -math.log(3.0 * float(np.median([e for _, _, e in gen_stats])))
        if floor < 1.6 * max(-math.log(p[1]) for p in gen_pts):
            ax.axhline(floor, color=MUTED, lw=1.0, ls=":", zorder=1)
            ax.annotate(r"$3\sigma$ noise floor", xy=(0.03, floor),
                        xycoords=("axes fraction", "data"), fontsize=8, color=MUTED,
                        va="bottom")
    title = "Wilson loops / string tension"
    if n_noise:
        title += (f"\n({n_noise} noise-dominated loops omitted: "
                  r"exact $W(A) < 3\sigma_{\rm stat}$)")
    ax.set_xlabel("loop area A")
    ax.set_ylabel(r"$-\log \langle W(A) \rangle$")
    ax.set_title(title)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    corr = meas["plaq_correlator"]
    dists = np.arange(1, len(corr) + 1)
    ax.plot(dists, np.abs(corr), "o-", label="generated |C(d)|")
    if ref is not None:
        rcorr = ref["plaq_correlator"]
        ax.plot(np.arange(1, len(rcorr) + 1), np.abs(rcorr), "s--", mfc="none",
                label=f"{reference_label} |C(d)|")
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

    _plot_ladder_topology(rung_results, all_rows, output_dir)

    return {"rows": all_rows, "drift": drift}


def _plot_ladder_topology(rung_results, all_rows, output_dir):
    """Generated vs exact vs reference-HMC topology observables along the ladder."""
    names = ["Q", "Q^2", "chi_top ((<Q^2>-<Q>^2)/V)"]
    titles = [
        r"$\langle Q \rangle$",
        r"$\langle Q^2 \rangle$",
        r"$\chi_{\rm top} = (\langle Q^2\rangle - \langle Q\rangle^2)/V$",
    ]
    per_rung = []
    for label, rows in all_rows.items():
        by_name = {r["observable"]: r for r in rows}
        if all(n in by_name for n in names):
            per_rung.append(by_name)
    if len(per_rung) != len(rung_results):
        return

    x = np.arange(len(rung_results))
    tick_labels = [f"L={r.lattice_size}\n" + rf"$\beta$={r.beta:g}" for r in rung_results]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))
    for ax, name, title in zip(axes, names, titles):
        vals = np.array([r[name]["value"] for r in per_rung], dtype=float)
        errs = np.array([r[name]["error"] for r in per_rung], dtype=float)
        exacts = np.array([r[name]["exact"] for r in per_rung], dtype=float)
        ax.plot(x, exacts, "_", color=INK, ms=22, mew=1.8, ls="none", label="exact", zorder=3)
        ax.errorbar(x - 0.08, vals, yerr=errs, fmt="o", ms=6, color=GEN_COLOR,
                    capsize=3, label="generated", zorder=4)
        refs = [r[name].get("reference") for r in per_rung]
        if all(v is not None for v in refs):
            ref_errs = [r[name].get("ref_error", float("nan")) for r in per_rung]
            ax.errorbar(x + 0.08, refs, yerr=ref_errs, fmt="s", ms=6, mfc="none",
                        color=REF_COLOR, capsize=3, label="reference HMC", zorder=4)
            positive = min(v for v in refs) > 0
        else:
            positive = True
        if name == "Q":
            ax.axhline(0.0, color=GRID_COLOR, lw=0.8, zorder=1)
        elif vals.min() > 0 and exacts.min() > 0 and positive:
            ax.set_yscale("log")
        ax.set_xticks(x)
        ax.set_xticklabels(tick_labels, fontsize=8)
        ax.set_title(title, fontsize=11, color=INK)
        ax.tick_params(labelsize=8, colors=MUTED)
        ax.grid(axis="y", color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle("Topological observables along the ladder", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(Path(output_dir) / "ladder_topology.png", dpi=130)
    plt.close(fig)


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
