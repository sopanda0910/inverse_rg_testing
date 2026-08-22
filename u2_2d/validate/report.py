"""Comparison of a generated U(2) ensemble against HMC reference and exact results.

Three columns are reported for every observable that has them -- generated, HMC
reference, and closed form -- because in 2D U(2) the closed form exists for
almost everything, and a disagreement between HMC and exact is a different bug
from a disagreement between the model and HMC.

Observables are split into full-U(2) and determinant-sector (`det_`) families.
That split is the diagnostic: the model only generates the determinant sector, so
a determinant-sector disagreement is model error, while a full-U(2) disagreement
with the determinant sector clean points at the conditional SU(2) sampler (too
few sweeps) or at the rethermalization.

Carried over from the U(1) study and still true here: observable-level agreement
on the plaquette does not constrain the density. Residual model error concentrates
in EXTENDED observables, so the z-score of the largest available Wilson loops is
reported alongside the plaquette and never replaced by it.
"""

import math

import numpy as np

from .observables import exact_reference, measure_ensemble
from .stats import (autocorr_aware_mean_err, effective_observable_count,
                    mean_abs_z_sigma, null_mean_abs_z)


def _stats(values: np.ndarray, n_chains: int | None = None) -> tuple[float, float]:
    """Mean and error. tau_int-AWARE when the chain count is known.

    The naive `sigma / sqrt(N)` assumes independent configurations; an ensemble
    from a handful of HMC chains is not, and a lifted ensemble inherits its
    coarse input's correlation. The naive SEM is then too small and every |z|
    built on it is too large. u1 adopted this correction as NARRATIVE 25.7 / M4;
    `docs/PARITY_U1_U2.md` section 5 item 3 is the u2 symptom. Passing
    `n_chains=None` keeps the old behaviour, so callers that genuinely have
    independent draws are unaffected.
    """
    values = np.asarray(values, dtype=float)
    n = max(len(values), 1)
    if n <= 1:
        return float(values.mean()), 0.0
    if n_chains:
        mean, err, _ = autocorr_aware_mean_err(values, n_chains)
        return mean, err
    return float(values.mean()), float(values.std(ddof=1) / math.sqrt(n))


def compare(generated, reference, beta: float, lattice_size: int,
            loops=None, n_chains: int | None = None,
            reference_n_chains: int | None = None) -> dict:
    """Generated vs reference vs exact. Both inputs are U(2) ensembles [N,2,L,L,5].

    `n_chains` / `reference_n_chains` switch on tau_int-aware error bars for the
    generated and reference ensembles respectively -- see `_stats`. Leave them
    unset only when the configurations really are independent draws.
    """
    kwargs = {} if loops is None else {"loops": loops}
    gen = measure_ensemble(generated, **kwargs)
    ref = measure_ensemble(reference, **kwargs) if reference is not None else None
    exact = exact_reference(beta, lattice_size, **({} if loops is None else {"loops": loops}))

    rows = []
    for key in sorted(k for k in gen if np.asarray(gen[k]).ndim == 1
                      and k not in ("det_plaq_angles", "plaq_correlator")):
        g_mean, g_err = _stats(gen[key], n_chains)
        row = {"observable": key, "generated": g_mean, "generated_err": g_err}
        if ref is not None and key in ref:
            r_mean, r_err = _stats(ref[key], reference_n_chains)
            row["reference"] = r_mean
            row["reference_err"] = r_err
            spread = math.hypot(g_err, r_err)
            row["z_vs_reference"] = (g_mean - r_mean) / spread if spread > 0 else float("nan")
        target = exact.get(key)
        if key == "topological_charge":
            target = 0.0
        if target is not None:
            row["exact"] = target
            if g_err > 0:
                row["z_vs_exact"] = (g_mean - target) / g_err
        rows.append(row)

    q_gen = np.asarray(gen["topological_charge"], dtype=float)
    summary = {
        "beta": beta,
        "lattice_size": lattice_size,
        "n_generated": int(len(q_gen)),
        "q_squared": float((q_gen**2).mean()),
        "q_squared_exact": exact["topological_charge_squared"],
        "rows": rows,
    }
    if ref is not None:
        q_ref = np.asarray(ref["topological_charge"], dtype=float)
        summary["q_squared_reference"] = float((q_ref**2).mean())
    summary["sector_histogram"] = _sector_table(q_gen, beta, lattice_size)

    extended = [r for r in rows if r["observable"].startswith("wilson_")]
    if extended and ref is not None:
        zs = [abs(r.get("z_vs_reference", float("nan"))) for r in extended]
        zs = [z for z in zs if not math.isnan(z)]
        if zs:
            summary["max_wilson_z"] = max(zs)
            summary["mean_wilson_z"] = float(np.mean(zs))

    # HOW MANY INDEPENDENT OBSERVABLES THIS SCORECARD ACTUALLY CONTAINS.
    # Every `mean |z|` computed from these rows gets read against the half-normal
    # null of sqrt(2/pi) = 0.798, and the standard error of that mean is
    # sqrt(1 - 2/pi) / sqrt(N). Using the ROW COUNT for N assumes the rows are
    # independent draws, and in 2D they are emphatically not: Wilson loops of
    # different sizes are near-deterministic functions of one another, and the
    # measured participation ratio is 3.77 at L = 32 against 41 rows. Three
    # claims in this project were overstated by that factor of 3.3 before it was
    # measured, so the count travels WITH the scorecard rather than being
    # recomputed (or forgotten) by each consumer.
    summary["n_effective"] = effective_observable_count(gen)
    summary["n_effective_extended"] = effective_observable_count(
        {k: v for k, v in gen.items() if _extended_wilson(k)})
    return summary


def _extended_wilson(name: str) -> bool:
    """Full-U(2) Wilson loops of area >= 16 -- the subset the challenger report's
    guard (c) averages over, and hence the subset its N_eff must describe."""
    if not name.startswith("wilson_"):
        return False
    try:
        a, b = name.split("wilson_")[1].split("x")
        return int(a) * int(b) >= 16
    except ValueError:
        return False


def _sector_table(charges: np.ndarray, beta: float, lattice_size: int) -> list[dict]:
    from ..lgt.exact import det_topological_charge_distribution

    q_values, probs = det_topological_charge_distribution(beta, lattice_size)
    n = max(len(charges), 1)
    table = []
    for q, p in zip(q_values, probs):
        measured = float(np.mean(charges == q))
        # Binomial error under the null p, not under the observed frequency: an
        # empty sector has zero observed variance but a perfectly well defined
        # expected one, and using the observed value turns "we saw none of a rare
        # sector" into a spurious huge z.
        err = math.sqrt(max(p * (1.0 - p), 1e-12) / n)
        if p < 1e-4 and measured == 0.0:
            continue
        table.append({"Q": int(q), "measured": measured, "exact": float(p),
                      "expected_count": p * n,
                      "z": (measured - p) / err})
    return table


def render_markdown(summary: dict, title: str = "U(2) validation") -> str:
    lines = [f"# {title}", "",
             f"beta = {summary['beta']:g}, L = {summary['lattice_size']}, "
             f"N = {summary['n_generated']}", ""]
    header = ["observable", "generated", "reference", "exact", "z vs ref", "z vs exact"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for row in summary["rows"]:
        lines.append("| {} | {:.6g} +- {:.2g} | {} | {} | {} | {} |".format(
            row["observable"], row["generated"], row["generated_err"],
            f"{row['reference']:.6g}" if "reference" in row else "-",
            f"{row['exact']:.6g}" if "exact" in row else "-",
            f"{row['z_vs_reference']:+.2f}" if "z_vs_reference" in row else "-",
            f"{row['z_vs_exact']:+.2f}" if "z_vs_exact" in row else "-",
        ))
    lines += ["", "## topological sectors", "",
              "| Q | measured | exact | z |", "|---|---|---|---|"]
    for entry in summary["sector_histogram"]:
        lines.append(f"| {entry['Q']:+d} | {entry['measured']:.4f} | "
                     f"{entry['exact']:.4f} | {entry['z']:+.2f} |")
    lines += ["", f"<Q^2> generated {summary['q_squared']:.4f}, "
                  f"exact {summary['q_squared_exact']:.4f}"]
    if "max_wilson_z" in summary:
        lines.append(f"Wilson-loop z vs reference: max {summary['max_wilson_z']:.2f}, "
                     f"mean {summary['mean_wilson_z']:.2f}")
        n_eff = summary.get("n_effective")
        if n_eff:
            # A mean |z| means nothing without the value it would take if the
            # model were exactly right, and that value is NOT zero -- |z| is
            # half-normal, so the null is sqrt(2/pi) = 0.798. Scoring far BELOW
            # it is evidence of overestimated errors, not of a good model.
            sig = mean_abs_z_sigma(summary["mean_wilson_z"], n_eff)
            lines.append(
                f"  null for an exact model: {null_mean_abs_z():.3f}; "
                f"N_eff = {n_eff:.2f} of {len(summary['rows'])} rows, so this "
                f"sits {abs(sig):.1f} sigma "
                f"{'BELOW' if sig > 0 else 'above'} the null.")
    return "\n".join(lines) + "\n"
