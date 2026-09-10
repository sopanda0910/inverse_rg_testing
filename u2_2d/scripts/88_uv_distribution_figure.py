"""Figure 62 -- per-configuration Wilson-loop distributions, both theories, at
the hardest coupling each study benchmarks.

Every other seed-quality figure in the paper scores a MEAN against the closed
form. A mean can be right for the wrong reason, and it says nothing about the
shape of the distribution it came from, which is what a claim about ultraviolet
structure actually rests on. This draws the distribution itself: one value per
configuration, pooled over the settled half of every chain, for the diffusion
seed and for cold- and hot-started HMC under the same plain sampler.

Three distinct failure modes are visible at once, and that is the point of
drawing them together:

    diffusion seed   centred on exact at every loop size, with the equilibrium
                     width.
    cold start       correct width, displaced centre, and displaced MOST in the
                     ultraviolet -- the plaquette and W(2x2) -- which is the
                     opposite of the naive guess that small loops equilibrate
                     first. It is also given far more trajectories than the seed
                     (640 vs 96 in u1), so the comparison is not budget-limited.
    hot start        wrong centre AND grossly wrong width: 3x too broad on the
                     u1 plaquette, 25x on the u2 plaquette. It has not built a
                     gauge field at all, so no amount of centring would fix it.

The x axis is normalised by the SEED arm's own per-configuration spread, so the
figure tests the seed's CENTRE against exact and the other arms' WIDTHS against
the seed's. The seed's own width is not free either, and the annotation is what
tests it: the cold arm is an independent equilibrium ensemble, so a width ratio
near 1 says the seed's spread is the theory's.

    python u2_2d/scripts/88_uv_distribution_figure.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from u1_2d.lgt.exact import wilson_loop_exact as u1_exact  # noqa: E402
from u2_2d.lgt.exact import wilson_loop_exact as u2_exact  # noqa: E402

INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
SEED_C, COLD_C, HOT_C = "#0072B2", "#D55E00", "#7a3fa0"

U1_SERIES = ROOT / ("out/u1_2d/thermalization/L32_beta218.58/"
                    "D_bc55.0237_L32_beta218.58_series.npz")
U1_BETA = 218.5802136261687
U2_BENCH = ROOT / "out/u2_2d/seed_benchmark"
U2_BETA, U2_L = 416.524, 64

# Topology is scored at a DIFFERENT u1 coupling from the Wilson loops, and the
# reason is physics rather than convenience: at beta = 218.58 the exact
# finite-volume <Q^2> is 0.029, so every arm including a totally frozen one sits
# at Q = 0 and a P(Q) panel there discriminates nothing. beta = 14.1464 has
# exact <Q^2> = 1.904, comparable to u2's 1.001 at its own benchmarked coupling,
# so the two rows test the same thing. It is also the sharper statement: at
# beta = 14.1464 a cold start's LOCAL observables are fully thermalised after
# 640 trajectories (+0.06 sigma on the plaquette) while its topology has not
# moved once.
U1_TOPO_SERIES = ROOT / ("out/u1_2d/thermalization/L32_beta14.1464/"
                         "A_bc4_L32_beta14.1464_series.npz")
U1_TOPO_BETA, U1_L = 14.1464, 32

# (npz key / json key, loop area, display label)
U1_LOOPS = [("plaquette", 1, r"$W(1{\times}1)$"),
            ("wilson_2x2", 4, r"$W(2{\times}2)$"),
            ("wilson_4x4", 16, r"$W(4{\times}4)$"),
            ("wilson_6x6", 36, r"$W(6{\times}6)$")]
U2_LOOPS = [("wilson_1x1", 1, r"$W(1{\times}1)$"),
            ("wilson_2x2", 4, r"$W(2{\times}2)$"),
            ("wilson_4x4", 16, r"$W(4{\times}4)$"),
            ("wilson_8x8", 64, r"$W(8{\times}8)$")]

# The paper draws three columns, not four: a figure* spans 6.5 in, and at
# 6.9 in native nothing is downscaled. All four are still computed and printed.
# Two ultraviolet loops, where the cold start's displacement lives, plus the
# largest available loop so the infrared is not silently dropped.
U1_PLOT = ("plaquette", "wilson_2x2", "wilson_6x6")
U2_PLOT = ("wilson_1x1", "wilson_2x2", "wilson_8x8")


def tail(a: np.ndarray) -> np.ndarray:
    """Settled half of a [records, chains] series, flattened."""
    return np.asarray(a)[np.asarray(a).shape[0] // 2:].ravel()


def load_u1():
    z = np.load(U1_SERIES)
    arms = {}
    for arm, key in (("lift", "diffusion seed"), ("cold", "cold start"),
                     ("hot", "hot start")):
        arms[arm] = {k: tail(z[f"{key}|{k}"]) for k, _, _ in U1_LOOPS}
    exact = {k: u1_exact(218.5802136261687, a, lattice_size=32)
             for k, a, _ in U1_LOOPS}
    return arms, exact


def load_u2():
    files = {"lift": "arm_A_diffusion_seed", "cold": "arm_B_cold_start",
             "hot": "arm_C_hot_start"}
    arms = {}
    for arm, stem in files.items():
        h = json.loads((U2_BENCH / f"{stem}.json").read_text())["history"]
        h = h[len(h) // 2:]
        arms[arm] = {k: np.array([r[k + "_chain"] for r in h]).ravel()
                     for k, _, _ in U2_LOOPS}
    exact = {k: u2_exact(416.524, a, lattice_size=64) for k, a, _ in U2_LOOPS}
    return arms, exact


def panel(ax, arms, exact, key, label, xlim=6.0):
    ref = arms["lift"][key].std()
    ex = exact[key]
    bins = np.linspace(-xlim, xlim, 61)

    for arm, colour, style in (("lift", SEED_C, "fill"), ("cold", COLD_C, "step"),
                               ("hot", HOT_C, "step")):
        v = (arms[arm][key] - ex) / ref
        inside = v[(v > -xlim) & (v < xlim)]
        # density=True divides by the in-window count, so an arm with nothing in
        # the window must not be handed to hist() at all.
        if inside.size:
            if style == "fill":
                ax.hist(v, bins=bins, density=True, color=colour, alpha=0.45,
                        zorder=2)
                ax.hist(v, bins=bins, density=True, histtype="step",
                        color=colour, lw=1.6, zorder=3)
            else:
                ax.hist(v, bins=bins, density=True, histtype="step",
                        color=colour, lw=1.5, zorder=3)
        # an arm whose mass is off-window gets its centre reported at the edge
        if inside.size < 0.5 * v.size:
            side = -1 if v.mean() < 0 else 1
            y = 0.93
            ax.annotate("", xy=(side * xlim * 0.98, y),
                        xytext=(side * xlim * 0.62, y),
                        xycoords=("data", "axes fraction"),
                        textcoords=("data", "axes fraction"),
                        arrowprops=dict(arrowstyle="-|>", color=colour, lw=1.5))
            ax.text(side * xlim * 0.59, y, f"{v.mean():+.0f}",
                    transform=ax.get_xaxis_transform(),
                    ha="right" if side > 0 else "left", va="center",
                    fontsize=8.5, color=colour, weight="bold")

    ax.axvline(0.0, color=INK, ls="--", lw=1.2, zorder=4)
    ax.set_xlim(-xlim, xlim)
    ax.set_xticks([-4, -2, 0, 2, 4])
    ax.set_title(label, fontsize=9, color=INK, pad=3)
    ax.grid(True, color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_yticks([])
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)

    # One block, top right, so the whole top left stays free for the
    # off-window arrows.
    w_cold = arms["cold"][key].std() / ref
    w_hot = arms["hot"][key].std() / ref
    ax.text(0.985, 0.88,
            r"$\sigma_{\rm cfg}=$" + f"{ref:.1e}"
            + f"\nwidth/lift\ncold {w_cold:.2f}\nhot {w_hot:.1f}",
            transform=ax.transAxes, ha="right", va="top", fontsize=7.5,
            color=MUTED, linespacing=1.4)


def load_charges():
    """Per-configuration topological charge for each arm, plus exact P(Q)."""
    from u1_2d.lgt.exact import topological_charge_distribution as u1_pq
    from u2_2d.lgt.exact import det_topological_charge_distribution as u2_pq

    z = np.load(U1_TOPO_SERIES)
    u1 = {a: tail(z[f"{k}|Q"]) for a, k in (("lift", "diffusion seed"),
                                            ("cold", "cold start"),
                                            ("hot", "hot start"))}
    u1_chains = {a: np.asarray(z[f"{k}|Q"])[np.asarray(z[f"{k}|Q"]).shape[0] // 2:]
                 for a, k in (("lift", "diffusion seed"), ("cold", "cold start"),
                              ("hot", "hot start"))}
    qv1, pq1 = u1_pq(U1_TOPO_BETA, U1_L, "wilson")

    files = {"lift": "arm_A_diffusion_seed", "cold": "arm_B_cold_start",
             "hot": "arm_C_hot_start"}
    u2, u2_chains = {}, {}
    for arm, stem in files.items():
        h = json.loads((U2_BENCH / f"{stem}.json").read_text())["history"]
        h = h[len(h) // 2:]
        a = np.array([r["charge"] for r in h])
        u2_chains[arm] = a
        u2[arm] = a.ravel()
    qv2, pq2 = u2_pq(U2_BETA, U2_L)
    return (u1, u1_chains, qv1, pq1), (u2, u2_chains, qv2, pq2)


def topo_panel(ax, arms, chains, qv, pq, title, volume, qmax=5, rng=None):
    """P(Q) against exact, with each arm's <Q^2> reported as a ratio to exact.

    chi_t = <Q^2>/V at fixed volume, so the chi_t ratios are these same numbers
    and a separate panel for it would repeat this one exactly.
    """
    qs = np.arange(-qmax, qmax + 1)
    ex = np.zeros_like(qs, dtype=float)
    for q, p in zip(qv, pq):
        if abs(q) <= qmax:
            ex[int(round(q)) + qmax] = p
    exact_q2 = float((qv ** 2 * pq).sum())

    width = 0.26
    for k, (arm, colour) in enumerate((("lift", SEED_C), ("cold", COLD_C),
                                       ("hot", HOT_C))):
        v = np.rint(arms[arm]).astype(int)
        frac = np.array([(v == q).mean() for q in qs])
        ax.bar(qs + (k - 1) * width, frac, width=width, color=colour,
               alpha=0.85, zorder=3, label=arm)
        out = float((np.abs(v) > qmax).mean())
        if out > 0.02:
            ax.text(qmax + 0.4, 0.90 - 0.09 * k, f"{out:.0%} beyond",
                    ha="right", va="center", fontsize=7.5, color=colour,
                    transform=ax.get_xaxis_transform())

    ax.plot(qs, ex, "o-", color=INK, ms=4.0, lw=1.4, zorder=5, label="exact")

    ax.set_xlim(-qmax - 0.6, qmax + 0.6)
    ax.set_ylim(0, 1.04)
    ax.set_xticks(qs[::2])
    ax.set_xlabel(r"topological charge $Q$", fontsize=9.5, color=INK)
    ax.set_title(title, fontsize=10, color=INK)
    ax.grid(True, axis="y", color=GRID, lw=0.5, alpha=0.7)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8.5)

    lines = [r"$\langle Q^2\rangle$ / exact", f"exact  {exact_q2:.3f}"]
    for arm, colour in (("lift", SEED_C), ("cold", COLD_C), ("hot", HOT_C)):
        per_chain = (chains[arm] ** 2).mean(axis=0)
        m = float(per_chain.mean())
        idx = rng.integers(0, per_chain.size, size=(4000, per_chain.size))
        err = float(per_chain[idx].mean(axis=1).std())
        zs = (m - exact_q2) / err if err > 0 else np.inf
        lines.append(f"{arm}  {m / exact_q2:.2f}"
                     if np.isfinite(zs) else f"{arm}  0.00   (frozen)")
    ax.text(0.03, 0.97, "\n".join(lines), transform=ax.transAxes, ha="left",
            va="top", fontsize=8.0, color=MUTED, linespacing=1.5)


def figure_topology(out_path):
    rng = np.random.default_rng(0)
    (u1, u1c, qv1, pq1), (u2, u2c, qv2, pq2) = load_charges()

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.9))
    topo_panel(axes[0], u1, u1c, qv1, pq1,
               r"2D U(1),  $L=32,\ \beta=14.15$", U1_L ** 2, rng=rng)
    topo_panel(axes[1], u2, u2c, qv2, pq2,
               r"2D U(2),  $L=64,\ \beta=416.52$", U2_L ** 2, rng=rng)
    axes[0].set_ylabel(r"$P(Q)$", fontsize=9.5, color=INK)

    handles = [plt.Line2D([], [], color=SEED_C, lw=6, alpha=0.85, label="preconditioned"),
               plt.Line2D([], [], color=COLD_C, lw=6, alpha=0.85, label="cold start"),
               plt.Line2D([], [], color=HOT_C, lw=6, alpha=0.85, label="hot start"),
               plt.Line2D([], [], color=INK, lw=1.4, marker="o", ms=4, label="exact")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("Only the transported charge reproduces the exact sector distribution",
                 fontsize=10.5, color=INK, y=1.0)
    fig.tight_layout()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "out/u2_2d/figures/fig62_uv_distributions.png"))
    ap.add_argument("--out-topology",
                    default=str(ROOT / "out/u2_2d/figures/fig63_topology_distributions.png"))
    args = ap.parse_args()

    u1_arms, u1_ex = load_u1()
    u2_arms, u2_ex = load_u2()

    fig, axes = plt.subplots(2, 3, figsize=(6.9, 4.0))

    labels1 = {k: lab for k, _, lab in U1_LOOPS}
    labels2 = {k: lab for k, _, lab in U2_LOOPS}
    for j, key in enumerate(U1_PLOT):
        panel(axes[0, j], u1_arms, u1_ex, key, labels1[key])
    for j, key in enumerate(U2_PLOT):
        panel(axes[1, j], u2_arms, u2_ex, key, labels2[key])

    axes[0, 0].set_ylabel("2D U(1)\n" r"$L=32,\ \beta=218.58$",
                          fontsize=8.5, color=INK, labelpad=6)
    axes[1, 0].set_ylabel("2D U(2)\n" r"$L=64,\ \beta=416.52$",
                          fontsize=8.5, color=INK, labelpad=6)
    for ax in axes[1]:
        ax.set_xlabel(r"$(W - W_{\rm exact})\,/\,\sigma_{\rm cfg}$",
                      fontsize=8.5, color=INK)

    handles = [plt.Line2D([], [], color=SEED_C, lw=3, alpha=0.7, label="preconditioned"),
               plt.Line2D([], [], color=COLD_C, lw=2, label="cold start"),
               plt.Line2D([], [], color=HOT_C, lw=2, label="hot start"),
               plt.Line2D([], [], color=INK, lw=1.2, ls="--", label="exact")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False,
               fontsize=8.5, bbox_to_anchor=(0.5, -0.035))

    fig.suptitle("The preconditioned configuration reproduces the equilibrium "
                 "distribution, not just its mean",
                 fontsize=10.5, color=INK, y=1.0)
    fig.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")

    figure_topology(args.out_topology)

    for name, arms, ex, loops in (("u1", u1_arms, u1_ex, U1_LOOPS),
                                  ("u2", u2_arms, u2_ex, U2_LOOPS)):
        for key, _, label in loops:
            ref = arms["lift"][key].std()
            row = [f"{name} {key:12s}"]
            for arm in ("lift", "cold", "hot"):
                v = arms[arm][key]
                row.append(f"{arm}: c={(v.mean() - ex[key]) / ref:+7.2f} "
                           f"w={v.std() / ref:6.2f}")
            print("  ".join(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
