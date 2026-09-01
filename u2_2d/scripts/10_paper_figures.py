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
    fig09  parity mobility    -- parity FLIPS per chain-trajectory against beta,
                                 for BOTH winding moves, beside the ordinary
                                 sector-change count over the same range. The
                                 joint proposal falls off a cliff at beta ~ 20
                                 while the marginal move is flat through it, and
                                 the right-hand panel sees neither -- so the two
                                 lessons are that the cliff belongs to a
                                 PROPOSAL, not to the theory, and that a
                                 sector-change count cannot tell you either way.
                                 Supersedes two earlier versions: the (beta L,
                                 beta/V) plane off stage-07 verdicts, and the
                                 single-move "mobility dies at beta = 14-20".
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
    "D_cold_plus_winding": ("cold start", "#c2571a", "--", 1.6),
    "E_diffusion_plus_winding": ("diffusion seed", "#1b6ca8", "-", 2.2),
    "F_hot_plus_winding": ("hot start", "#7a1fa2", "-.", 1.6),
    "G_cold_plus_odd_winding": ("cold start", "#c2571a", "--", 1.6),
    "H_diffusion_plus_odd_winding": ("diffusion seed", "#1b6ca8", "-", 2.2),
}

# One column per SAMPLER, three seeds inside each. The grid is only meaningful
# read along a row -- same sampler, different seed. Comparing a diffusion seed
# under one sampler against a cold start under a weaker one measures the sampler.
SAMPLER_COLUMNS = [
    ("plain HMC", ["A_diffusion_seed", "B_cold_start", "C_hot_start"]),
    ("+ winding ($\\Delta Q = 2$)",
     ["E_diffusion_plus_winding", "D_cold_plus_winding", "F_hot_plus_winding"]),
    # No hot arm here by design: a hot start is two orders from equilibrium in
    # <Q^2>, so giving it a parity move answers no question stage 08 is asking.
    ("+ winding ($\\Delta Q = 1$, marginal)",
     ["H_diffusion_plus_odd_winding", "G_cold_plus_odd_winding"]),
]


def _columns(bench):
    """(title, [arm dicts]) per sampler, skipping arms this run did not produce."""
    by_name = {a["arm"]: a for a in bench["arms"]}
    out = []
    for title, names in SAMPLER_COLUMNS:
        arms = [by_name[n] for n in names if n in by_name]
        if arms:
            out.append((title, arms))
    return out


def _load(path: Path):
    if not path.exists():
        print(f"  (skip) missing {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def figure_seed_quality(bench: dict, path: Path) -> None:
    """Plaquette relative error vs trajectory: one panel per sampler.

    The claim this figure carries is that a generated configuration is already at
    equilibrium while a cold start is three orders away, and that this is true
    whatever sampler is wrapped around it. One panel per sampler is what makes
    that a claim about the SEED rather than about the move.
    """
    columns = _columns(bench)
    exact = bench["plaquette_exact"]
    n = len(columns)
    orig_w, orig_h = 4.6 * n, 4.2
    target_w = 3.3 if (n == 1 and orig_w / orig_h < 1.5) else 6.9
    scale = target_w / orig_w
    fig, axes = plt.subplots(1, n, figsize=(round(orig_w * scale, 2), round(orig_h * scale, 2)),
                             sharey=True, squeeze=False)
    interval = bench.get("independent_interval_trajectories")
    for ax, (title, arms) in zip(axes[0], columns):
        for arm in arms:
            label, colour, ls, lw = ARM_STYLE[arm["arm"]]
            traj = [h["trajectory"] for h in arm["history"]]
            rel = [abs(h["plaquette"] / exact - 1.0) + 1e-12 for h in arm["history"]]
            ax.semilogy(traj, rel, ls, color=colour, lw=lw, label=label)
        if interval and np.isfinite(interval):
            ax.axvline(interval, color="0.35", lw=1.0, ls=(0, (1, 2)))
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("HMC trajectory")
        ax.grid(alpha=0.25, which="both")
        ax.legend(frameon=False, fontsize=8)
    axes[0][0].set_ylabel(
        r"$|\langle \frac{1}{2}{\rm ReTr}P\rangle / {\rm exact} - 1|$")
    fig.suptitle(f"Seed quality, read ACROSS each panel: L = {bench['lattice_size']}, "
                 r"$\beta$ = " + f"{bench['beta']:g}", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=max(150, min(450, round(150 / scale))), bbox_inches="tight")
    plt.close(fig)


def figure_topological_reach(bench: dict, path: Path) -> None:
    """Sectors occupied and <Q^2> vs trajectory, one column per sampler.

    THIS FIGURE USED TO CARRY THE REACHABILITY CLAIM AND NO LONGER DOES. With the
    marginal odd move the classical arm reaches full P(Q) coverage from a cold
    start, so "the classical arm cannot get here" is withdrawn. What the columns
    now show is the COST of arriving: the cold arm needs the expensive odd move
    (right column) to reach coverage the diffusion seed already has in the left
    column, having made no winding move at all.
    """
    columns = _columns(bench)
    q2_exact = bench["arms"][0]["topology"]["q_squared_exact"]
    n = len(columns)
    orig_w, orig_h = 4.6 * n, 7.2
    scale = 6.9 / orig_w
    fig, axes = plt.subplots(2, n, figsize=(round(orig_w * scale, 2), round(orig_h * scale, 2)),
                             sharey="row", squeeze=False)
    for col, (title, arms) in enumerate(columns):
        top, bot = axes[0][col], axes[1][col]
        for arm in arms:
            label, colour, ls, lw = ARM_STYLE[arm["arm"]]
            traj = [h["trajectory"] for h in arm["history"]]
            top.plot(traj, [h["n_sectors"] for h in arm["history"]], ls,
                     color=colour, lw=lw, label=label)
            bot.plot(traj, [h["q_squared"] for h in arm["history"]], ls,
                     color=colour, lw=lw, label=label, zorder=3)
        bot.axhline(q2_exact, color="k", lw=1.0, ls=(0, (6, 3)), zorder=1,
                    label="exact")
        top.set_title(title, fontsize=10)
        for ax in (top, bot):
            ax.grid(alpha=0.25)
            ax.legend(frameon=False, fontsize=8)
        bot.set_xlabel("HMC trajectory")
        # The hot arm sits two orders above everything else and flattens the panel
        # on a linear axis, hiding the comparison that matters. symlog rather than
        # log because the cold arm is identically zero.
        bot.set_yscale("symlog", linthresh=0.1)
        bot.set_ylim(bottom=0.0)
    axes[0][0].set_ylabel("distinct sectors occupied")
    axes[1][0].set_ylabel(r"$\langle Q^2 \rangle$")
    fig.suptitle(f"Topological reach: L = {bench['lattice_size']}, "
                 r"$\beta$ = " + f"{bench['beta']:g}"
                 + "  --  compare WITHIN a panel, not across", y=1.0)
    fig.tight_layout()
    fig.savefig(path, dpi=max(150, min(450, round(150 / scale))), bbox_inches="tight")
    plt.close(fig)

def figure_wilson_spread(dists: dict, path: Path) -> None:
    """Per-configuration Wilson-loop distributions, generated vs reference."""
    names = dists["loops"]
    n = len(names)
    cols = min(n, 4)
    rows = -(-n // cols)  # ceil
    per_w = 6.9 / cols
    scale = per_w / 3.3
    per_h = 3.6 * scale
    fig, axes = plt.subplots(rows, cols, figsize=(round(cols * per_w, 2), round(rows * per_h, 2)))
    axes = np.atleast_2d(axes)
    for ax, name in zip(axes.flat, names):
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
    axes.flat[0].set_ylabel("density")
    fig.suptitle(f"Wilson-loop distributions (std in legend): L = "
                 f"{dists['lattice_size']}, " r"$\beta$ = " + f"{dists['beta']:g}",
                 y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=max(150, min(450, round(150 / scale))), bbox_inches="tight")
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
    fig, ax = plt.subplots(figsize=(6.9, 4.44))
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
    fig.savefig(path, dpi=152)
    plt.close(fig)


def figure_sampling_regimes(records: list, path: Path) -> None:
    """Parity mobility against beta, for BOTH winding moves.

    This figure has now been wrong twice, and the second time is the instructive
    one.

    Version 1 drew the (beta L, beta / V) plane with stage-07 verdicts as
    markers. Both choices were wrong: the verdict is a hypothesis test on one
    binomial draw of the odd weight and passes on luck, and beta L does not
    organise the data.

    Version 2 counted parity FLIPS against beta and concluded "odd mobility dies
    between beta = 14 and beta = 20 at every volume tested". The measurement was
    right and the conclusion was not, because every flip in it came from the
    JOINT winding proposal -- propose on (phi, q) together, accept on the full
    U(2) action. What died at beta = 20 was that proposal's acceptance, not the
    theory's odd charge.

    The MARGINAL move (docs/INSTANTON.md) proposes on psi alone and accepts on
    the exact SU(2)-integrated marginal, then resamples SU(2) conditionally. At
    L = 16 it flips parity 61403 times at beta = 28, where the joint proposal
    flips ZERO. There is no mobility edge in this range at all.

    So the figure draws both moves, and the honest reading of the left panel is
    that the cliff is a property of a PROPOSAL. Keeping the joint series in it is
    the point -- it is what a plausible-looking global move does when it is
    priced wrong, and it is why the right-hand panel exists.
    """
    hot = [r for r in records if r.get("start") in (None, "hot")]
    if not hot:
        return
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(6.9, 3.03), sharex=True)
    colour = {8: "#2e7d32", 16: "#1f4e9c"}
    marker = {8: "o", 16: "s"}
    # Solid = the marginal move, dashed = the joint proposal. Line style carries
    # the move and hue carries the volume, so neither rests on the other.
    dash = {1: "-", 2: "--"}
    move_name = {1: r"marginal $\Delta Q=1$", 2: r"joint $\Delta Q=2$ proposal"}
    floor = 3e-7

    for step in (2, 1):
        for size in sorted({r["lattice_size"] for r in hot}):
            rows = sorted((r for r in hot
                           if r["lattice_size"] == size
                           and int(r.get("winding_charge_step") or 2) == step),
                          key=lambda r: r["beta"])
            if not rows:
                continue
            c, m = colour.get(size, "0.4"), marker.get(size, "^")
            norm = [r["n_chains"] * r["n_trajectories"] for r in rows]
            beta = [r["beta"] for r in rows]
            lab = f"$L={size}$, " + move_name[step]
            rate = [r["parity_flips"] / n for r, n in zip(rows, norm)]
            ax.plot(beta, [max(x, floor) for x in rate], marker=m, ls=dash[step],
                    color=c, label=lab, markersize=6, linewidth=1.4,
                    markerfacecolor=(c if step == 1 else "white"),
                    markeredgecolor=c, markeredgewidth=1.3)
            # Zero flips cannot be drawn on a log axis; plot at a visible floor
            # and ring it, so "none observed" never reads as a small rate.
            for b, x in zip(beta, rate):
                if x == 0:
                    ax.plot([b], [floor], m, color=c, markersize=10,
                            markerfacecolor="white", markeredgewidth=1.6, zorder=4)
            ax2.plot(beta, [r["q_sector_changes"] / n for r, n in zip(rows, norm)],
                     marker=m, ls=dash[step], color=c, label=lab, markersize=6,
                     linewidth=1.4, markerfacecolor=(c if step == 1 else "white"),
                     markeredgecolor=c, markeredgewidth=1.3)

    ax.axhline(floor, color="0.7", linewidth=0.8, linestyle=":")
    ax.text(ax.get_xlim()[1], floor * 1.3, "none observed", fontsize=6.5,
            color="0.45", ha="right")
    ax.set_yscale("log")
    ax.set_ylabel("parity flips per chain-trajectory")
    ax.set_title("The cliff belongs to the PROPOSAL, not the theory", fontsize=10)
    ax.annotate("joint proposal:" + chr(10) + "acceptance collapses",
                xy=(0.97, 0.42), xycoords="axes fraction", fontsize=7.5,
                ha="right", color="#8a3d10")
    ax.annotate("marginal move: flat", xy=(0.97, 0.84), xycoords="axes fraction",
                fontsize=7.5, ha="right", color="#1f4e9c")

    ax2.set_yscale("log")
    ax2.set_ylabel("$Q$ changes per chain-trajectory")
    ax2.set_title("The usual diagnostic sees none of it", fontsize=10)
    for a in (ax, ax2):
        a.set_xlabel(r"$\beta$")
        a.grid(alpha=0.25, which="both")
    ax.legend(frameon=False, fontsize=7)
    ax2.set_ylim(ax2.get_ylim()[0] * 0.5, ax2.get_ylim()[1] * 2)
    fig.suptitle("Do not read odd-charge mobility off a sector-change count",
                 fontsize=10.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=213)
    plt.close(fig)


def figure_winding_economics(topo: dict, path: Path) -> None:
    """The Z_2 obstruction as a cost curve, beside what it costs in ACCEPTANCE.

    Panel (a) is the forced-route cost and is the obstruction itself: crossing
    Z_2 with the SU(2) sector held fixed drives one plaquette's cos(phi_p) to -1
    and the joint action pays 2 beta there.

    Panel (b) is why that is not the end of the story. Accepting on the exact
    psi-marginal instead of the joint action -- and resampling SU(2), which is
    what absorbs the flipped plaquette -- takes odd acceptance from 0.000 to
    0.28-0.66 at the same couplings. Panel (a) without panel (b) reads as "odd
    charge is unreachable", which is what this study believed until 2026-08-20
    and is not true. See `docs/INSTANTON.md`.
    """
    rows = topo.get("winding", [])
    if not rows:
        return
    labels = [f"{r['lattice_size']}/{r['beta']:g}" for r in rows]
    x = np.arange(len(rows))
    even = [r["charge_step_2"]["forced_cost"] for r in rows]
    expect = [r["expected_central_cost"] for r in rows]
    odd = [r["charge_step_1"]["forced_cost"] for r in rows]
    after = [r["ladder_route"]["cost_after_conditional_su2"] for r in rows]

    acc_even = [r["charge_step_2"].get("acceptance", float("nan")) for r in rows]
    acc_odd = [r["charge_step_1"].get("acceptance", float("nan")) for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.50))
    ax = axes[0]
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
    ax.set_ylabel(r"$\Delta S$ of the FORCED move")
    ax.set_title("(a) the $Z_2$ obstruction, with SU(2) held fixed", fontsize=10)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1]
    ax.bar(x - w / 2, acc_even, w, color="#2e7d32",
           label=r"$\Delta Q = 2$ (central)")
    ax.bar(x + w / 2, acc_odd, w, color="#8a6fbf",
           label=r"$\Delta Q = 1$ (marginal acceptance)")
    for pos, vals in ((x - w / 2, acc_even), (x + w / 2, acc_odd)):
        for xi, v in zip(pos, vals):
            ax.annotate(f"{v:.3f}", (xi, v), textcoords="offset points",
                        xytext=(0, 3), ha="center", fontsize=7.5)
    ax.axhline(0, color="0.5", lw=0.8)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Metropolis acceptance")
    ax.set_title("(b) accepted on the exact $\\psi$-marginal instead", fontsize=10)
    ax.legend(frameon=False, fontsize=8)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_xlabel(r"lattice size $L$  /  coupling $\beta$")
        ax.grid(alpha=0.25, axis="y")
    fig.suptitle(r"Winding economics: the obstruction is in the PROPOSAL, "
                 r"not in the theory", y=1.02)
    fig.tight_layout()
    fig.savefig(path, dpi=270, bbox_inches="tight")
    plt.close(fig)


def figure_ladder_accuracy(summary: list, path: Path) -> None:
    """Observables against the closed form at every rung."""
    fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.69))
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
    fig.savefig(path, dpi=217, bbox_inches="tight")
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

    # Four runs, two winding moves. Older records predate `winding_charge_step`
    # and are all from the JOINT (charge_step 2) proposal, so they default to 2 --
    # the directory name is the fallback, never the primary source.
    parity = []
    for name, default_step in (("base_parity_L8", 2), ("base_parity", 2),
                               ("base_parity_v2", 2),
                               ("base_parity_L8_marginal", 1),
                               ("base_parity_v2_marginal", 1)):
        rows = _load(Path("out/u2_2d") / name / "base_parity.json")
        if not rows:
            continue
        for r in (rows if isinstance(rows, list) else [rows]):
            r.setdefault("winding_charge_step", default_step)
            if r.get("winding_charge_step") is None:
                r["winding_charge_step"] = default_step
            parity.append(r)
    if parity:
        figure_sampling_regimes(parity, out_dir / "fig09_parity_mobility.png")
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
