"""Scalability showcase figures for the generalization study.

Reads out/diffusion/demo/generalization/summary.json (built by
06_generalization_study.py) and renders three cross-case figures that
highlight how the single L=16-trained model scales:

    fig_scaling_volume.png   -- <Q^2> ~ V tracking, Wilson area-law collapse
                                across L = 32/64/128, per-config sampling cost
    fig_scaling_coupling.png -- 1 - <cos theta_p> and string tension vs beta_f
                                across the matched scan (1.49 -> 218.6)
    fig_scaling_parity.png   -- generated vs exact parity for <Q^2> and
                                -ln W(2x2) across all cases
"""

import json
import math
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.lgt.exact import plaquette_exact, string_tension_exact
from diffusion.validate.report import GEN_COLOR, REF_COLOR, INK, MUTED, GRID_COLOR

OUT = Path("out/diffusion/demo/generalization")
C_COLOR = "#8a63c9"
PART_STYLE = {
    "A": (GEN_COLOR, "o", "Part A/D: matched pairs (L=16 base)"),
    "D": (GEN_COLOR, "o", None),
    "B": (REF_COLOR, "s", "Part B: mismatched targets"),
    "C": (C_COLOR, "^", "Part C: size scan (L=32/64 base)"),
}


def load_records() -> dict:
    recs = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    return {k: v for k, v in recs.items() if "rows" in v}


def row(r: dict, name: str) -> dict:
    return next((x for x in r["rows"] if x["observable"] == name), {})


def style(ax):
    ax.grid(color=GRID_COLOR, lw=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)


def fig_volume(recs: dict) -> None:
    size_cases = [recs[k] for k in ("A_bc4", "C_L64", "C_L128")]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))

    ax = axes[0]
    vols = np.array([(2 * r["base_size"]) ** 2 for r in size_cases], dtype=float)
    q2 = [row(r, "Q^2") for r in size_cases]
    ax.plot(vols, [d["exact"] for d in q2], "--", color=INK, lw=1.2, label="exact")
    ax.errorbar(vols, [d["value"] for d in q2], yerr=[d["error"] for d in q2],
                fmt="o", ms=7, color=GEN_COLOR, capsize=3, zorder=4, label="generated")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(vols)
    ax.set_xticklabels([r"$32^2$", r"$64^2$", r"$128^2$"])
    ax.set_xlabel(r"lattice volume $V$", fontsize=9, color=INK)
    ax.set_ylabel(r"$\langle Q^2 \rangle$", fontsize=9, color=INK)
    ax.set_title(r"Topology tracks $\langle Q^2\rangle \propto V$" + "\n" +
                 r"($\beta_f = 14.15$, 16x volume span)", fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    style(ax)

    ax = axes[1]
    for r, (color, marker) in zip(size_cases, [(GEN_COLOR, "o"), (REF_COLOR, "s"), (C_COLOR, "^")]):
        areas, vals, errs = [], [], []
        for x in r["rows"]:
            if not x["observable"].startswith("wilson_"):
                continue
            w, err = x["value"], x["error"]
            if x["exact"] is None or w <= 3 * err:
                continue
            a, b = (int(v) for v in x["observable"].split("_")[1].split("x"))
            areas.append(a * b)
            vals.append(-math.log(w))
            errs.append(err / w)
        order = np.argsort(areas)
        ax.errorbar(np.array(areas)[order], np.array(vals)[order],
                    yerr=np.array(errs)[order], fmt=marker, ms=5, mfc="none",
                    color=color, capsize=2, label=f"$L={2*r['base_size']}$")
    from diffusion.lgt.exact import wilson_loop_exact
    a_grid = np.arange(1, 145)
    exact_line = [-math.log(wilson_loop_exact(14.1464, int(a), "wilson", 128)) for a in a_grid]
    ax.plot(a_grid, exact_line, "--", color=INK, lw=1.2, label="exact area law")
    ax.annotate("L=32 large-A deficit\n(trained pair; report sec. 2)",
                xy=(80, 3.4), xytext=(35, 4.3), fontsize=7, color=MUTED,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_xlabel(r"loop area $A$", fontsize=9, color=INK)
    ax.set_ylabel(r"$-\ln\langle W(A)\rangle$", fontsize=9, color=INK)
    ax.set_title("Area law collapses across sizes\n(signal-dominated loops only)",
                 fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    style(ax)

    ax = axes[2]
    per_cfg = {}
    for r in recs.values():
        if "sample_seconds" not in r:
            continue
        L = 2 * r["base_size"]
        per_cfg.setdefault(L, []).append(r["sample_seconds"] / r["n_configs"])
    Ls = np.array(sorted(per_cfg))
    med = np.array([np.median(per_cfg[L]) for L in Ls])
    vols = Ls.astype(float) ** 2
    for L in Ls:
        ax.plot([float(L) ** 2] * len(per_cfg[L]), per_cfg[L], "o", ms=4,
                mfc="none", color=GEN_COLOR, alpha=0.45,
                label="individual cases" if L == Ls[0] else None)
    ax.plot(vols, med, "o-", color=GEN_COLOR, ms=7, label="median")
    ax.plot(vols, med[0] * vols / vols[0], "--", color=INK, lw=1.2,
            label=r"$\propto V$ reference")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xticks(vols)
    ax.set_xticklabels([rf"${L}^2$" for L in Ls])
    ax.set_xlabel(r"lattice volume $V$", fontsize=9, color=INK)
    ax.set_ylabel("sampling cost per config (s, CPU)", fontsize=9, color=INK)
    ax.set_title("Cost grows no faster than volume\n(i.i.d. samples: no critical slowing down)",
                 fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    style(ax)

    fig.suptitle("Volume scalability at fixed coupling pair "
                 r"$\beta_c = 4 \to \beta_f = 14.1464$ (model trained on $L=16$ only)",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "fig_scaling_volume.png", dpi=130)
    plt.close(fig)


def fig_coupling(recs: dict) -> None:
    matched = sorted((r for r in recs.values() if r["part"] in ("A", "D")),
                     key=lambda r: r["target_beta"])
    betas = np.array([r["target_beta"] for r in matched])
    train_betas = [1.0, 2.0, 4.0, 8.0, 14.1464, 55.0237]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))

    ax = axes[0]
    grid = np.geomspace(1.2, 280, 200)
    exact_curve = [1.0 - plaquette_exact(b, "wilson", 32) for b in grid]
    plaq = [row(r, "plaquette") for r in matched]
    ax.plot(grid, exact_curve, "--", color=INK, lw=1.2, label="exact")
    ax.errorbar(betas, [1.0 - d["value"] for d in plaq], yerr=[d["error"] for d in plaq],
                fmt="o", ms=6, color=GEN_COLOR, capsize=3, zorder=4, label="generated")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"target coupling $\beta_f$", fontsize=9, color=INK)
    ax.set_ylabel(r"$1 - \langle \cos\theta_p \rangle$", fontsize=9, color=INK)
    ax.set_title("Plaquette across two decades of coupling", fontsize=10, color=INK)
    style(ax)

    ax = axes[1]
    sig_curve = [string_tension_exact(b) for b in grid]
    ax.plot(grid, sig_curve, "--", color=INK, lw=1.2, label="exact")
    pts = [(r["target_beta"], row(r, "creutz_2")) for r in matched if row(r, "creutz_2")]
    ax.errorbar([b for b, d in pts], [d["value"] for _, d in pts],
                yerr=[d["error"] for _, d in pts],
                fmt="o", ms=6, color=GEN_COLOR, capsize=3, zorder=4,
                label=r"generated Creutz $\chi(2,2)$")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"target coupling $\beta_f$", fontsize=9, color=INK)
    ax.set_ylabel(r"string tension $\sigma$", fontsize=9, color=INK)
    ax.set_title("String tension from Creutz ratios", fontsize=10, color=INK)
    style(ax)

    for ax in axes:
        ax.axvspan(min(train_betas), max(train_betas), color=GRID_COLOR, alpha=0.4, zorder=0)
        for b in train_betas:
            ax.axvline(b, color=MUTED, lw=0.5, ls=":", zorder=1)
        ax.legend(fontsize=8, frameon=False)
    axes[0].annotate("training couplings", xy=(2.3, 0.92), xycoords=("data", "axes fraction"),
                     fontsize=8, color=MUTED)
    axes[0].annotate("4x extrapolation", xy=(218.6, 0.35), xycoords=("data", "axes fraction"),
                     fontsize=8, color=MUTED, ha="right", rotation=90)

    fig.suptitle(r"Coupling scalability along the matched scan: $\beta_f = 1.49 \to 218.6$"
                 " on generated $L=32$ ensembles", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "fig_scaling_coupling.png", dpi=130)
    plt.close(fig)


def fig_parity(recs: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6))

    ax = axes[0]
    seen = set()
    for r in sorted(recs.values(), key=lambda r: r["run_id"]):
        d = row(r, "Q^2")
        if not d or d["exact"] < 0.02 or d["value"] <= 0:
            continue
        color, marker, label = PART_STYLE[r["part"]]
        if label in seen:
            label = None
        seen.add(PART_STYLE[r["part"]][2])
        ax.errorbar(d["exact"], d["value"], yerr=d["error"], fmt=marker, ms=6,
                    mfc="none", color=color, capsize=2, label=label, zorder=4)
    lims = (0.02, 60)
    ax.plot(lims, lims, "--", color=INK, lw=1.2, zorder=2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel(r"exact $\langle Q^2 \rangle$", fontsize=9, color=INK)
    ax.set_ylabel(r"generated $\langle Q^2 \rangle$", fontsize=9, color=INK)
    ax.set_title(r"$\langle Q^2 \rangle$ parity: ~3 decades, all 20 cases",
                 fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    style(ax)

    ax = axes[1]
    seen = set()
    for r in sorted(recs.values(), key=lambda r: r["run_id"]):
        d = row(r, "wilson_2x2")
        if not d or d["value"] <= 0:
            continue
        color, marker, label = PART_STYLE[r["part"]]
        if label in seen:
            label = None
        seen.add(PART_STYLE[r["part"]][2])
        ax.errorbar(-math.log(d["exact"]), -math.log(d["value"]),
                    yerr=d["error"] / d["value"], fmt=marker, ms=6, mfc="none",
                    color=color, capsize=2, label=label, zorder=4)
    lims = (0.006, 4)
    ax.plot(lims, lims, "--", color=INK, lw=1.2, zorder=2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel(r"exact $-\ln\langle W(2\times2)\rangle$", fontsize=9, color=INK)
    ax.set_ylabel(r"generated $-\ln\langle W(2\times2)\rangle$", fontsize=9, color=INK)
    ax.set_title(r"$-\ln W(2\times2)$ parity: ~2.5 decades", fontsize=10, color=INK)
    style(ax)

    fig.suptitle("Generated vs exact across every case (couplings 1.49-218.6, volumes to $128^2$)",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(OUT / "fig_scaling_parity.png", dpi=130)
    plt.close(fig)


def main() -> None:
    recs = load_records()
    fig_volume(recs)
    fig_coupling(recs)
    fig_parity(recs)
    for name in ("fig_scaling_volume.png", "fig_scaling_coupling.png", "fig_scaling_parity.png"):
        print(OUT / name)


if __name__ == "__main__":
    main()
