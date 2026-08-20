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


def _stats(values: np.ndarray) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    n = max(len(values), 1)
    return float(values.mean()), float(values.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0


def compare(generated, reference, beta: float, lattice_size: int,
            loops=None) -> dict:
    """Generated vs reference vs exact. Both inputs are U(2) ensembles [N,2,L,L,5]."""
    kwargs = {} if loops is None else {"loops": loops}
    gen = measure_ensemble(generated, **kwargs)
    ref = measure_ensemble(reference, **kwargs) if reference is not None else None
    exact = exact_reference(beta, lattice_size, **({} if loops is None else {"loops": loops}))

    rows = []
    for key in sorted(k for k in gen if np.asarray(gen[k]).ndim == 1
                      and k not in ("det_plaq_angles", "plaq_correlator")):
        g_mean, g_err = _stats(gen[key])
        row = {"observable": key, "generated": g_mean, "generated_err": g_err}
        if ref is not None and key in ref:
            r_mean, r_err = _stats(ref[key])
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
    return summary


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
    return "\n".join(lines) + "\n"
