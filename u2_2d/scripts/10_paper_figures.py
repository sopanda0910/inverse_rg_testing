"""Stage 10: the result figures.

Six figures carrying the study's claims, in the order the argument runs:

    fig06  seed quality       -- HMC started from a generated configuration is
                                 already at equilibrium; cold and hot starts are
                                 not. The controls supply the dynamic range.
    fig07  topological reach  -- the same four arms, by sector coverage. This is
                                 the half that cannot be matched rather than
                                 merely won: a plain chain never leaves its
                                 starting sector at these couplings.
    fig08  Wilson spread      -- per-configuration DISTRIBUTIONS, not means. Two
                                 ensembles can agree on <W> to 1e-6 and disagree
                                 on its width, and the width is what a density
                                 claim rests on.
    fig09  sampling regimes   -- where P(Q) can be sampled rather than seeded,
                                 in the (beta/V, beta L) plane that separates the
                                 two U(2) freezing mechanisms.
    fig10  winding economics  -- the Z_2 obstruction as a cost curve: even charge
                                 free, odd charge O(beta L), and what the exact
                                 conditional SU(2) sampler recovers.
    fig12  area law        -- W(A)/W(1)^A for generated AND reference. Exact only
                                 in infinite volume, so it must be read against a
                                 same-size control, never against 1 alone.
    fig11  ladder accuracy    -- observables against the closed form at every
                                 rung, with the pre-rethermalization value shown
                                 so model error and sweep repair stay separable.

Everything reads from JSON written by earlier stages; nothing is recomputed, so
a figure can never disagree with the number it is drawn from.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ARM_STYLE = {
    "A_diffusion_seed": ("diffusion seed", "#1b6ca8", "-", 2.2),
    "B_cold_start": ("cold start", "#c2571a", "--", 1.6),
    "C_hot_start": ("hot start", "#7a1fa2", "-.", 1.6),
    "D_cold_plus_winding": ("cold + winding", "#2e7d32", ":", 1.8),
}


def _load(path: Path):
    if not path.exists():
        print(f"  (skip) missing {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def figure_seed_quality(bench: dict, path: Path) -> None:
    """Plaquette relative error vs trajectory, per arm, log-scaled."""
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    exact = bench["plaquette_exact"]
    for arm in bench["arms"]:
        label, colour, ls, lw = ARM_STYLE[arm["arm"]]
        traj = [h["trajectory"] for h in arm["history"]]
        rel = [abs(h["plaquette"] / exact - 1.0) + 1e-12 for h in arm["history"]]
        ax.semilogy(traj, rel, ls, color=colour, lw=lw, label=label)
    interval = bench.get("independent_interval_trajectories")
    if interval and np.isfinite(interval):
        ax.axvline(interval, color="0.35", lw=1.0, ls=(0, (1, 2)))
        ax.text(interval, ax.get_ylim()[1], r"  $2\tau_{\rm int}$", va="top",
                fontsize=8, color="0.35")
    ax.set_xlabel("HMC trajectory")
    ax.set_ylabel(r"$|\langle \frac{1}{2}{\rm ReTr}P\rangle / {\rm exact} - 1|$")
    ax.set_title(f"Seed quality: L = {bench['lattice_size']}, "
                 r"$\beta$ = " + f"{bench['beta']:g}")
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_topological_reach(bench: dict, path: Path) -> None:
    """Sector coverage and <Q^2> vs trajectory -- the half that cannot be matched."""
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.0))
    for arm in bench["arms"]:
        label, colour, ls, lw = ARM_STYLE[arm["arm"]]
        traj = [h["trajectory"] for h in arm["history"]]
        axes[0].plot(traj, [h["n_sectors"] for h in arm["history"]], ls,
                     color=colour, lw=lw, label=label)
        axes[1].plot(traj, [h["q_squared"] for h in arm["history"]], ls,
                     color=colour, lw=lw, label=label, zorder=3)
    q2_exact = bench["arms"][0]["topology"]["q_squared_exact"]
    axes[1].axhline(q2_exact, color="k", lw=1.0, ls=(0, (6, 3)), zorder=1,
                    label="exact")
    # The hot arm sits two orders above everything else and flattens the panel on a
    # linear axis, hiding the comparison that matters (0.86 vs 0.92 vs exact 1.00).
    # symlog rather than log because the cold arm is identically zero.
    axes[1].set_yscale("symlog", linthresh=0.1)
    # No arm is negative, so the symlog mirror below zero is dead space.
    axes[1].set_ylim(bottom=0.0)
    axes[0].set_ylabel("distinct sectors occupied")
    axes[1].set_ylabel(r"$\langle Q^2 \rangle$")
    for ax in axes:
        ax.set_xlabel("HMC trajectory")
        ax.grid(alpha=0.25)
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle(f"Topological reach: L = {bench['lattice_size']}, "
                 r"$\beta$ = " + f"{bench['beta']:g}", y=1.0)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_wilson_spread(dists: dict, path: Path) -> None:
    """Per-configuration Wilson-loop distributions, generated vs reference."""
    names = dists["loops"]
    fig, axes = plt.subplots(1, len(names), figsize=(3.3 * len(names), 3.6))
    axes = np.atleast_1d(axes)
    for ax, name in zip(axes, names):
        gen = np.asarray(dists["generated"][name])
        ref = dists["reference"].get(name) if dists.get("reference") else None
        lo = min(gen.min(), np.min(ref) if ref is not None else gen.min())
        hi = max(gen.max(), np.max(ref) if ref is not None else gen.max())
        bins = np.linspace(lo, hi, 34)
        ax.hist(gen, bins=bins, density=True, alpha=0.55, color="#1b6ca8",
                label=f"generated  ({gen.std():.2e})")
        if ref is not None:
            ax.hist(np.asarray(ref), bins=bins, density=True, histtype="step",
                    color="#c2571a", lw=1.6,
                    label=f"HMC  ({np.std(ref):.2e})")
        ax.axvline(dists["exact"][name], color="k", lw=1.2, label="exact mean")
        ax.set_title(name.replace("wilson_", "W "), fontsize=10)
        ax.set_xlabel(r"$\frac{1}{2}{\rm ReTr}\,W$")
        ax.legend(frameon=False, fontsize=7)
        ax.grid(alpha=0.2)
        # Small loops span a range narrow enough that default ticks collide.
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.tick_params(axis="x", labelrotation=30, labelsize=8)
    axes[0].set_ylabel("density")
    fig.suptitle(f"Wilson-loop distributions (std in legend): L = "
                 f"{dists['lattice_size']}, " r"$\beta$ = " + f"{dists['beta']:g}",
                 y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)



def figure_area_law(validation, path: Path) -> None:
    """W(A) / W(1)^A against area, generated AND reference.

    In infinite volume the 2D plaquettes inside a loop are independent, so this
    ratio is identically 1 and any departure is plaquette correlation. That makes
    it tempting to read as a pure model-error probe. It is NOT, and the reference
    curve is here to stop that reading: at L = 32 the HMC reference departs from 1
    by MORE than the generated ensemble does (0.978 vs 1.000 at area 120), because
    a 12x12 loop covers 14% of a 32^2 torus and the exact form used here is the
    infinite-volume one, while large loops also carry the largest variance.

    So the honest use is comparative, at fixed A/V, against a reference of the
    same size -- not "generated deviates from 1, therefore model error". At
    L = 64 the generated curve rises smoothly to 1.005 at area 144 with A/V only
    0.035, which is about 2 sigma on the largest loop and currently uncontrolled,
    since no same-size HMC reference exists at that coupling.
    """
    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    colours = ["#1b6ca8", "#c2571a", "#2e7d32"]
    for k, rec in enumerate(validation):
        rows = {x["observable"]: x for x in rec.get("rows", [])}
        if "wilson_1x1" not in rows:
            continue
        pts = []
        for name, row in rows.items():
            if not name.startswith("wilson_"):
                continue
            a, b = name.replace("wilson_", "").split("x")
            pts.append((int(a) * int(b), row))
        pts.sort()
        areas = [a for a, _ in pts]
        colour = colours[k % len(colours)]
        g1 = rows["wilson_1x1"]["generated"]
        ax.plot(areas, [row["generated"] / g1 ** a for a, row in pts], "o-",
                color=colour, lw=1.8, label=f"generated  L={rec['lattice_size']}")
        r1 = rows["wilson_1x1"].get("reference")
        if r1:
            ax.plot(areas, [row["reference"] / r1 ** a for a, row in pts], "s--",
                    color=colour, lw=1.3, alpha=0.75, ms=4,
                    label=f"HMC reference  L={rec['lattice_size']}")
    ax.axhline(1.0, color="k", lw=1.0, label="infinite-volume area law")
    ax.set_xlabel("loop area $A$")
    ax.set_ylabel("W(A) / W(1)$^{A}$")
    ax.set_title("Area-law ratio (compare like sizes; the reference is the control)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_sampling_regimes(scans: list, path: Path) -> None:
    """Where P(Q) can be sampled, in the plane of the two freezing mechanisms."""
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    marks = {"SAMPLED": ("o", "#2e7d32", "sampled"),
             "PARITY-STUCK": ("s", "#c2571a", "parity-stuck"),
             "FROZEN": ("v", "#7a1fa2", "frozen"),
             "DISAGREES": ("X", "#b00020", "disagrees")}
    seen = set()
    for r in scans:
        v = r.get("verdict", "SAMPLED")
        m, c, lab = marks.get(v, ("o", "0.4", v))
        ax.scatter(r["beta"] * r["lattice_size"],
                   r.get("beta_over_volume", r["beta"] / r["lattice_size"] ** 2),
                   marker=m, color=c, s=64, zorder=3,
                   label=lab if lab not in seen else None)
        seen.add(lab)
        ax.annotate(f"  {r['lattice_size']}/{r['beta']:g}",
                    (r["beta"] * r["lattice_size"],
                     r.get("beta_over_volume", r["beta"] / r["lattice_size"] ** 2)),
                    fontsize=6.5, color="0.3")
    ax.axvspan(450, 830, color="0.85", zorder=0)
    ax.text(610, ax.get_ylim()[1] * 0.92, "parity\nboundary", fontsize=7.5,
            ha="center", color="0.4")
    ax.set_xscale("log")
    ax.set_xlabel(r"$\beta L$  (odd-charge barrier)")
    ax.set_ylabel(r"$\beta / V$  (even-charge / central instanton cost)")
    ax.set_title("Where P(Q) can be sampled rather than seeded")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_winding_economics(topo: dict, path: Path) -> None:
    """The Z_2 obstruction as a cost curve."""
    rows = topo.get("winding", [])
    if not rows:
        return
    labels = [f"{r['lattice_size']}/{r['beta']:g}" for r in rows]
    x = np.arange(len(rows))
    even = [r["charge_step_2"]["forced_cost"] for r in rows]
    expect = [r["expected_central_cost"] for r in rows]
    odd = [r["charge_step_1"]["forced_cost"] for r in rows]
    after = [r["ladder_route"]["cost_after_conditional_su2"] for r in rows]

    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    w = 0.26
    groups = [
        (x - w, even, "#2e7d32", r"$\Delta Q = 2$ (central, free)"),
        (x, odd, "#c2571a", r"$\Delta Q = 1$ (crosses $Z_2$)"),
        (x + w, after, "#1b6ca8", r"$\Delta Q = 1$, after exact SU(2) sweeps"),
    ]
    for pos, vals, colour, label in groups:
        ax.bar(pos, vals, w, color=colour, label=label)
        # The free and recovered bars sit two orders below the blocked one, so the
        # linear axis that makes the contrast the message also makes them
        # unreadable. Label them rather than rescale and lose the contrast.
        for xi, v in zip(pos, vals):
            ax.annotate(f"{v:.1f}", (xi, max(v, 0.0)), textcoords="offset points",
                        xytext=(0, 3), ha="center", fontsize=7.5, color=colour)
    ax.plot(x - w, expect, "k_", ms=16, label=r"predicted $2\pi^2\beta/V$")
    ax.axhline(0, color="0.5", lw=0.8)
    ax.set_ylim(min(0.0, min(after) * 1.8), max(odd) * 1.18)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel(r"lattice size $L$  /  coupling $\beta$")
    ax.set_ylabel(r"$\Delta S$ of the forced move")
    ax.set_title(r"Winding economics: even charge is the U(1) instanton, odd is not")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_ladder_accuracy(summary: list, path: Path) -> None:
    """Observables against the closed form at every rung."""
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.9))
    sizes = [r["lattice_size"] for r in summary]
    x = np.arange(len(summary))
    post = [abs(r["plaquette"] / r["plaquette_exact"] - 1) for r in summary]
    pre = [abs(r["plaquette_pre_retherm"] / r["plaquette_exact"] - 1) for r in summary]
    axes[0].semilogy(x, pre, "s--", color="#c2571a", label="before retherm")
    axes[0].semilogy(x, post, "o-", color="#1b6ca8", label="after retherm")
    axes[0].set_ylabel(r"$|\langle P\rangle/\rm exact - 1|$")
    axes[0].legend(frameon=False, fontsize=9)

    axes[1].plot(x, [r["q_squared"] for r in summary], "o-", color="#1b6ca8",
                 label="generated")
    axes[1].plot(x, [r["q_squared_exact"] for r in summary], "k--", label="exact")
    axes[1].set_ylabel(r"$\langle Q^2 \rangle$")
    axes[1].legend(frameon=False, fontsize=9)
    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([f"L={s}\n" r"$\beta$=" f"{r['beta']:g}"
                            for s, r in zip(sizes, summary)], fontsize=8)
        ax.grid(alpha=0.25)
    fig.suptitle("Ladder accuracy against the closed form", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="out/u2_2d/figures")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    bench = _load(Path("out/u2_2d/seed_benchmark/seed_benchmark.json"))
    if bench:
        figure_seed_quality(bench, out_dir / "fig06_seed_quality.png")
        figure_topological_reach(bench, out_dir / "fig07_topological_reach.png")
        print("wrote fig06, fig07")

    dists = _load(Path("out/u2_2d/validation/wilson_distributions.json"))
    if dists:
        figure_wilson_spread(dists, out_dir / "fig08_wilson_spread.png")
        print("wrote fig08")

    scans = []
    for name in ("pq_sampling", "pq_sampling_L16", "pq_sampling_L32"):
        rows = _load(Path("out/u2_2d") / name / "pq_sampling.json")
        if rows:
            scans.extend(rows)
    if scans:
        figure_sampling_regimes(scans, out_dir / "fig09_sampling_regimes.png")
        print("wrote fig09")

    topo = _load(Path("out/u2_2d/topology/topology_study.json"))
    if topo:
        figure_winding_economics(topo, out_dir / "fig10_winding_economics.png")
        print("wrote fig10")

    validation = _load(Path("out/u2_2d/validation/summary.json"))
    if validation:
        figure_area_law(validation, out_dir / "fig12_area_law.png")
        print("wrote fig12")

    summary = _load(Path("out/u2_2d/ladder/summary.json"))
    if summary:
        figure_ladder_accuracy(summary, out_dir / "fig11_ladder_accuracy.png")
        print("wrote fig11")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
