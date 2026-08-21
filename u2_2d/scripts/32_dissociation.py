"""Figures 23 and 24 -- the dissociation, and the density gap per site.

The u2 analogues of u1's `28_dissociation.png` (main text #10) and
`39_kl_per_site.png` (#11). Both carry the same single claim from two angles:

    OBSERVABLE-LEVEL AGREEMENT DOES NOT CONSTRAIN THE DENSITY.

The generated ensembles match gauge-invariant observables to a few parts in
10^4-10^5, and simultaneously carry a density error of order 1 nat PER SITE.
Those two facts are not in tension and must not be reported as if one implies
the other: matching every observable a paper measures is a projection, and a
projection can be exact while the distribution behind it is not.

fig23 (dissociation) puts the two axes on one plot -- observable |z| against the
closed form on one, KL per site on the other -- so the orders of magnitude are
visible side by side rather than in separate tables.

fig24 (KL per site) plots the density gap against coupling, and the useful part
is that it is FLAT. KL/site runs 1.1099 / 1.1172 / 1.1362 / 1.1467 nats as
beta_f goes 14 -> 28 -> 105.7 -> 416.5, a 3.3% spread over a 30x range in
coupling, drifting very slightly UPWARD.

That flatness kills a tempting argument, which is why the figure says it out
loud. It would be convenient to claim the density gap shrinks in the regime this
study targets. It does not -- if anything it is marginally worse at high beta.
The defensible position is the harder one: the gap is real, roughly
beta-independent, and does not bear on the seeding claim, because the seeding
claim is graded on observables and on topology (which is TRANSPORTED, not
modelled) rather than on the density. An earlier version of this file, and of
`docs/u2_2d/FIGURE_PARITY.md`, asserted "worst at low beta, improving as beta
rises"; the numbers say otherwise and the assertion was never checked against
them.

    python u2_2d/scripts/32_dissociation.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"


def load_density(path: Path):
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        cert = r.get("free_energy_certificate") or {}
        if "kl_per_site" not in cert:
            continue
        out.append({
            "case": r["case"],
            "fine_beta": r["fine_beta"],
            "model_beta": r.get("model_beta"),
            "fine_size": r["fine_lattice_size"],
            "kl_per_site": cert["kl_per_site"],
            "kl_sem_per_site": cert.get("kl_sem", 0.0) / (r["fine_lattice_size"] ** 2),
            "log_weight_std": cert.get("log_weight_std"),
            "ess_per_n": r.get("ess_per_n"),
        })
    return sorted(out, key=lambda r: r["fine_beta"])


def load_observables(path: Path):
    """|z| against exact for every Wilson-type observable, per validated rung."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for rec in rows:
        zs = [abs(r["z_vs_exact"]) for r in rec.get("rows", [])
              if r.get("z_vs_exact") is not None
              and math.isfinite(r["z_vs_exact"])
              and "wilson" in r["observable"] or r.get("observable") == "det_plaquette"]
        rel = [abs(r["generated"] / r["exact"] - 1.0) for r in rec.get("rows", [])
               if r.get("exact")]
        if zs:
            out.append({"beta": rec["beta"], "lattice_size": rec["lattice_size"],
                        "median_abs_z": float(np.median(zs)),
                        "max_abs_z": float(np.max(zs)),
                        "median_rel_err": float(np.median(rel)) if rel else None,
                        "n_obs": len(zs)})
    return sorted(out, key=lambda r: r["beta"])


def fig_dissociation(dens, obs, dest: Path):
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    ax2 = ax.twinx()

    b_o = [r["beta"] for r in obs]
    rel = [r["median_rel_err"] for r in obs]
    ax.semilogy(b_o, rel, "o-", color="#0072B2", lw=2.2, ms=8,
                markeredgecolor="white", markeredgewidth=0.8, zorder=4,
                label="observables: median |generated/exact - 1|")

    b_d = [r["fine_beta"] for r in dens]
    kl = [r["kl_per_site"] for r in dens]
    ax2.semilogy(b_d, kl, "s--", color="#D55E00", lw=2.0, ms=7,
                 markeredgecolor="white", markeredgewidth=0.8, zorder=4,
                 label="density: KL per site (nats)")

    ax.set_xscale("log")
    ax.set_xlabel(r"fine coupling  $\beta_f$", fontsize=10, color=INK)
    ax.set_ylabel("relative error on observables", fontsize=10, color="#0072B2")
    ax2.set_ylabel("KL per site (nats)", fontsize=10, color="#D55E00")
    ax.tick_params(axis="y", colors="#0072B2")
    ax2.tick_params(axis="y", colors="#D55E00")

    ax.annotate("agreement to a few parts in $10^4$-$10^5$ ...",
                xy=(0.03, 0.10), xycoords="axes fraction", fontsize=8.5,
                color="#0072B2", ha="left")
    ax.annotate("... while the density is off by ~1 nat per site",
                xy=(0.97, 0.90), xycoords="axes fraction", fontsize=8.5,
                color="#D55E00", ha="right")

    ax.set_title("Matching every observable you measure does not constrain the "
                 "density", fontsize=11.5, color=INK, loc="left", pad=12)
    ax.grid(alpha=0.25, which="both", color=GRID)
    ax.set_axisbelow(True)
    for a in (ax, ax2):
        a.spines["top"].set_visible(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, loc="center left")
    fig.text(0.5, -0.01,
             "The two axes differ by many orders of magnitude and are measuring "
             "different things. A projection can be exact while the distribution "
             "behind it is not.",
             fontsize=7, color=MUTED, ha="center")
    fig.tight_layout()
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")


def fig_kl_per_site(dens, dest: Path):
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    b = [r["fine_beta"] for r in dens]
    kl = [r["kl_per_site"] for r in dens]
    err = [r["kl_sem_per_site"] for r in dens]
    ax.errorbar(b, kl, yerr=err, fmt="o-", color="#D55E00", lw=2.2, ms=8,
                capsize=3, markeredgecolor="white", markeredgewidth=0.8, zorder=4)
    for r in dens:
        ax.annotate(r["case"], (r["fine_beta"], r["kl_per_site"]), fontsize=7.5,
                    color=MUTED, textcoords="offset points", xytext=(0, 10),
                    ha="center")
    ax.set_xscale("log")
    ax.set_xlabel(r"fine coupling  $\beta_f$", fontsize=10, color=INK)
    ax.set_ylabel("KL per site (nats)", fontsize=10, color=INK)
    ax.set_title("The density gap is flat in beta -- it does not shrink where "
                 "the method is used", fontsize=11.5, color=INK, loc="left",
                 pad=12)
    lo, hi = kl[0], kl[-1]
    ax.annotate(f"{lo:.4f} -> {hi:.4f} nats/site across a 30x range in "
                r"$\beta$" + chr(10)
                + "-- a 3% spread, drifting slightly UPWARD, not downward",
                xy=(0.5, 0.14), xycoords="axes fraction", fontsize=8,
                color=MUTED, ha="center", style="italic")
    # Keep the y-range honest: on an auto log scale a 3% spread looks like a
    # trend. Pad it so the reader sees a flat line, which is what it is.
    ax.set_ylim(min(kl) * 0.5, max(kl) * 2.0)
    ax.grid(alpha=0.25, which="both", color=GRID)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--density", default="out/u2_2d/density_gap/density_gap.json")
    parser.add_argument("--validation", default="out/u2_2d/validation/summary.json")
    parser.add_argument("--out-dir", default="out/u2_2d/figures")
    args = parser.parse_args()

    dens = load_density(Path(args.density))
    obs = load_observables(Path(args.validation))
    if not dens:
        print(f"no density records in {args.density}")
        return 1
    out = Path(args.out_dir)
    if obs:
        fig_dissociation(dens, obs, out / "fig23_dissociation.png")
    else:
        print(f"(skip fig23) no validated rungs in {args.validation}")
    fig_kl_per_site(dens, out / "fig24_kl_per_site.png")

    print("\ndensity gap by case:")
    for r in dens:
        print(f"  {r['case']:>14s}  beta_f={r['fine_beta']:9.3f}  "
              f"KL/site={r['kl_per_site']:7.4f}  ESS/n={r['ess_per_n']:.4f}")
    print("\nobservable agreement by rung:")
    for r in obs:
        print(f"  L={r['lattice_size']:3d} beta={r['beta']:9.3f}  "
              f"median |rel err|={r['median_rel_err']:.2e}  "
              f"median |z|={r['median_abs_z']:.2f}  max |z|={r['max_abs_z']:.2f}  "
              f"({r['n_obs']} observables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
