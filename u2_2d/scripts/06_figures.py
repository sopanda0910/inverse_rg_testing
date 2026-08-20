"""Stage 06: figures.

Everything plotted here has a closed form to plot against, which is the reason
2D U(2) was chosen as the successor theory:

  fig 1  determinant-sector plaquette-angle density, generated vs exact w_det,
         with the r_1-matched U(1) Wilson density overlaid -- the visual form of
         "the determinant sector is not U(1) Wilson at beta/4"
  fig 2  P(Q), generated vs exact, with the reference ensemble
  fig 3  Wilson-loop area law, generated vs exact r_fund^A, both families
  fig 4  matched U(1) coupling and its residuals against beta/4 across the range
  fig 5  the ladder: plaquette and <Q^2> per rung against exact

Figures 4 and 5 need no ensembles; 1-3 are skipped when the ladder output is
missing, so this runs usefully straight after `09_verify_identities.py`.
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.exact import plaquette_angle_density
from u2_2d.lgt.exact import (
    det_matching_residuals,
    det_plaquette_angle_density,
    det_topological_charge_distribution,
    matched_u1_beta,
    plaquette_exact,
    wilson_loop_exact,
)
from u2_2d.utils import ensemble_path, load_config, load_ensemble
from u2_2d.validate.observables import measure_ensemble


def figure_density(measured, beta, size, path):
    grid = np.linspace(-np.pi, np.pi, 601)
    matched = matched_u1_beta(beta)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.hist(measured["det_plaq_angles"], bins=120, density=True, alpha=0.35,
            color="tab:blue", label="generated")
    ax.plot(grid, det_plaquette_angle_density(grid, beta), "k-", lw=2,
            label=r"exact $w_{\rm det}$")
    ax.plot(grid, plaquette_angle_density(grid, matched, "wilson"), "r--", lw=1.6,
            label=fr"U(1) Wilson, $\beta_1={matched:.3g}$ ($\beta/4={beta/4:.3g}$)")
    ax.set_xlabel(r"determinant plaquette angle $\alpha_p$")
    ax.set_ylabel("density")
    ax.set_title(fr"determinant sector, $\beta={beta:g}$, $L={size}$")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_sectors(measured, reference, beta, size, path):
    q_values, probs = det_topological_charge_distribution(beta, size)
    keep = probs > 1e-4
    q_values, probs = q_values[keep], probs[keep]
    width = 0.35
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    counts = np.array([np.mean(measured["topological_charge"] == q) for q in q_values])
    ax.bar(q_values - width / 2, counts, width, label="generated", color="tab:blue", alpha=0.8)
    if reference is not None:
        ref_counts = np.array([np.mean(reference["topological_charge"] == q) for q in q_values])
        ax.bar(q_values + width / 2, ref_counts, width, label="HMC reference",
               color="tab:orange", alpha=0.8)
    ax.plot(q_values, probs, "ko-", lw=1.4, ms=5, label="exact")
    ax.set_xlabel("topological charge Q")
    ax.set_ylabel("P(Q)")
    ax.set_title(fr"$\beta={beta:g}$, $L={size}$")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_area_law(measured, beta, size, path):
    areas, full, det = [], [], []
    for key in measured:
        if not key.startswith("wilson_"):
            continue
        r, t = (int(v) for v in key.split("_")[1].split("x"))
        areas.append(r * t)
        full.append(float(np.mean(measured[key])))
        det.append(float(np.mean(measured[f"det_{key}"])))
    order = np.argsort(areas)
    areas = np.array(areas)[order]
    grid = np.arange(1, areas.max() + 1)
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    ax.semilogy(areas, np.array(full)[order], "o", color="tab:blue",
                label=r"generated $\frac{1}{2}\mathrm{ReTr}\,W$")
    ax.semilogy(areas, np.array(det)[order], "s", color="tab:green",
                label=r"generated $\cos(\arg\det W)$")
    ax.semilogy(grid, [wilson_loop_exact(beta, int(a)) for a in grid], "k-", lw=1.6,
                label=r"exact $r_{\rm fund}^A$")
    ax.set_xlabel("loop area A (plaquettes)")
    ax.set_ylabel("Wilson loop")
    ax.set_title(fr"area law, $\beta={beta:g}$, $L={size}$")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_matching(path):
    betas = np.geomspace(1.0, 400.0, 60)
    matched = np.array([matched_u1_beta(float(b)) for b in betas])
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    axes[0].loglog(betas, matched, "k-", lw=1.8, label=r"$\beta_1$ (min-KL projection)")
    axes[0].loglog(betas, betas / 4, "r--", lw=1.4, label=r"$\beta/4$ (tree level)")
    axes[0].set_xlabel(r"$\beta_{U(2)}$")
    axes[0].set_ylabel(r"$\beta_{U(1)}$")
    axes[0].legend(fontsize=8)
    coarse = np.geomspace(2.0, 400.0, 24)
    residuals = [det_matching_residuals(float(b)) for b in coarse]
    axes[1].loglog(coarse, [abs(r["tree_level_ratio"] - 1.0) for r in residuals], "o-",
                   label=r"$|\beta_1/(\beta/4) - 1|$")
    axes[1].loglog(coarse, [abs(r["chi_t_residual"]) for r in residuals], "s-",
                   label=r"$|\chi_t$ residual$|$")
    axes[1].loglog(coarse, [abs(r["character_residuals"][2]) for r in residuals], "^-",
                   label=r"$|r_2$ residual$|$")
    axes[1].set_xlabel(r"$\beta_{U(2)}$")
    axes[1].set_ylabel("residual")
    axes[1].set_title("what one U(1) coupling cannot reproduce")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_ladder(summary, path):
    betas = [row["beta"] for row in summary]
    sizes = [row["lattice_size"] for row in summary]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    axes[0].plot(sizes, [row["plaquette"] for row in summary], "o-", label="generated")
    axes[0].plot(sizes, [row["plaquette_exact"] for row in summary], "k--", label="exact")
    axes[0].set_xlabel("L"), axes[0].set_ylabel(r"$\frac{1}{2}\mathrm{ReTr}\,P$")
    axes[0].set_xscale("log", base=2)
    axes[0].legend(fontsize=8)
    axes[1].plot(sizes, [row["q_squared"] for row in summary], "o-", label="generated")
    if "q_squared_pre_retherm" in summary[0]:
        axes[1].plot(sizes, [row["q_squared_pre_retherm"] for row in summary], "^--",
                     label="pre-rethermalization")
    axes[1].plot(sizes, [row["q_squared_exact"] for row in summary], "k--", label="exact")
    axes[1].set_xlabel("L"), axes[1].set_ylabel(r"$\langle Q^2\rangle$")
    axes[1].set_xscale("log", base=2)
    axes[1].legend(fontsize=8)
    for ax, beta_list in zip(axes, (betas, betas)):
        ax.set_title(r"$\beta$: " + ", ".join(f"{b:g}" for b in beta_list), fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/smoke.yaml")
    parser.add_argument("--out-dir", default="out/u2_2d/figures")
    args = parser.parse_args()

    config = load_config(args.config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    figure_matching(out_dir / "fig4_beta_matching.png")
    print(f"wrote {out_dir / 'fig4_beta_matching.png'}")

    ladder_dir = Path(config["ladder"].get("out_dir", "out/u2_2d/ladder"))
    data_dir = Path(config["data"].get("out_dir", "out/u2_2d/data"))
    summary_path = ladder_dir / "summary.json"
    if not summary_path.exists():
        print(f"no ladder summary at {summary_path}; skipping figures 1-3 and 5")
        return 0

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    figure_ladder(summary, out_dir / "fig5_ladder.png")
    print(f"wrote {out_dir / 'fig5_ladder.png'}")

    for row in summary:
        beta, size = float(row["beta"]), int(row["lattice_size"])
        path = ensemble_path(ladder_dir, size, beta, tag="ladder")
        if not path.exists():
            continue
        generated, _ = load_ensemble(path)
        measured = measure_ensemble(generated)
        reference_path = ensemble_path(data_dir, size, beta)
        reference = None
        if reference_path.exists():
            reference = measure_ensemble(load_ensemble(reference_path)[0])
        tag = f"L{size}_beta{beta:g}"
        figure_density(measured, beta, size, out_dir / f"fig1_det_density_{tag}.png")
        figure_sectors(measured, reference, beta, size, out_dir / f"fig2_sectors_{tag}.png")
        figure_area_law(measured, beta, size, out_dir / f"fig3_area_law_{tag}.png")
        print(f"wrote figures 1-3 for {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
