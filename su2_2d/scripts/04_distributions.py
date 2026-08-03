"""Observable distributions for the SU(2) lift: generated vs reference HMC vs
exact, mirroring the U(1) validation figures.

2D SU(2) is exactly solvable plaquette-by-plaquette, so panel (a) compares the
FULL single-plaquette density against the analytic sin^2(theta) e^{beta cos
theta} -- a sharper test than any U(1) panel (there the exact reference was
only a set of moments). Panel (d) tests the 2D factorization directly: the
exact area law W(R,T) = p^{RT} must hold, and a generated ensemble that gets
the plaquette right while missing the area law is producing spurious
plaquette-plaquette correlations.

    .venv/Scripts/python.exe su2_2d/scripts/04_distributions.py
"""

import argparse
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import torch

torch.set_num_threads(int(os.environ.get("SU2_2D_TORCH_THREADS", "8")))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml

from su2_2d.lgt import group, mean_plaquette, plaquette_exact, run_hmc_ensemble, wilson_loop_trace_half
from su2_2d.lgt.lattice import plaquette_word

GEN = "#2a78d6"      # validated pair (CVD dE 27.0 protan, 32.9 normal)
REF = "#d97706"
INK = "#111111"
MUTED = "#6b6b6b"
GRID = "#e3e2dd"

plt.rcParams.update({
    "font.size": 9.5, "axes.edgecolor": INK, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.axisbelow": True, "figure.dpi": 150, "axes.spines.top": False,
    "axes.spines.right": False,
})


def exact_plaquette_density(beta, n=600):
    th = np.linspace(1e-6, math.pi - 1e-6, n)
    w = np.sin(th) ** 2 * np.exp(beta * (np.cos(th) - 1.0))
    w /= np.trapezoid(w, th)
    # change of variables to x = cos(theta): p(x) = p(theta) / |sin theta|
    x = np.cos(th)
    return x, w / np.abs(np.sin(th))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="su2_2d/configs/su2.yaml")
    parser.add_argument("--out", default="out/su2_2d/figures/distributions.png")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    sam = config["sample"]
    fine_beta, fine_L = sam["fine_beta"], 2 * sam["coarse_L"]

    blob = torch.load(Path(sam["out_dir"]) / "lift.pt", weights_only=False)
    gen_cfg = blob["generated"]
    ref, _ = run_hmc_ensemble(fine_L, fine_beta, n_configs=gen_cfg.shape[0],
                              n_chains=config["data"]["n_chains"],
                              burn_in=config["data"]["burn_in"],
                              thin=config["data"]["thin"], seed=config["seed"] + 55)
    p1 = plaquette_exact(fine_beta)

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.4))
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # (a) full single-plaquette density vs the analytic curve
    gp = group.trace_half(plaquette_word(gen_cfg)).reshape(-1).numpy()
    rp = group.trace_half(plaquette_word(ref)).reshape(-1).numpy()
    bins = np.linspace(min(gp.min(), rp.min(), 0.0), 1.0, 70)
    ax_a.hist(rp, bins=bins, density=True, histtype="step", lw=2, color=REF,
              label="reference HMC")
    ax_a.hist(gp, bins=bins, density=True, histtype="step", lw=2, color=GEN,
              label="diffusion lift")
    x, d = exact_plaquette_density(fine_beta)
    ax_a.plot(x, d, color=INK, lw=1.6, ls="--", label="exact")
    ax_a.set_xlabel(r"$\frac{1}{2}\,\mathrm{tr}\,P$  (every plaquette)")
    ax_a.set_ylabel("density")
    ax_a.set_title("(a) single-plaquette density vs exact", loc="left", fontsize=10)
    ax_a.legend(frameon=False, fontsize=8.5)

    # (b, c) per-configuration observables
    for ax, fn, name in ((ax_b, lambda c: mean_plaquette(c), r"$\langle\frac{1}{2}\mathrm{tr}P\rangle$ per config"),
                         (ax_c, lambda c: wilson_loop_trace_half(c, 2, 2).mean(dim=(-2, -1)),
                          r"$W(2\times2)$ per config")):
        g = fn(gen_cfg).numpy()
        r = fn(ref).numpy()
        ex = p1 if ax is ax_b else p1**4
        lo = min(g.min(), r.min(), ex) - 0.004
        hi = max(g.max(), r.max(), ex) + 0.004
        bb = np.linspace(lo, hi, 32)
        ax.hist(r, bins=bb, density=True, color=REF, alpha=0.55, label="reference HMC")
        ax.hist(g, bins=bb, density=True, color=GEN, alpha=0.55, label="diffusion lift")
        ax.axvline(ex, color=INK, lw=1.6, ls="--", label="exact")
        ax.set_xlabel(name)
        ax.set_ylabel("density")
        ax.legend(frameon=False, fontsize=8.5)
    ax_b.set_title("(b) mean plaquette", loc="left", fontsize=10)
    ax_c.set_title(r"(c) $W(2\times2)$ — the coarse-plaquette scale", loc="left", fontsize=10)

    # (d) area law: in 2D, W(R,T) = p^{RT} exactly
    shapes = [(1, 1), (1, 2), (2, 2), (2, 3), (2, 4), (3, 4), (4, 4)]
    areas = [rx * ry for rx, ry in shapes]
    for cfgs, color, label, marker in ((ref, REF, "reference HMC", "s"),
                                       (gen_cfg, GEN, "diffusion lift", "o")):
        vals, errs = [], []
        for rx, ry in shapes:
            w = wilson_loop_trace_half(cfgs, rx, ry).mean(dim=(-2, -1))
            vals.append(float(w.mean()))
            errs.append(float(w.std() / max(w.numel(), 2) ** 0.5))
        ax_d.errorbar(areas, np.abs(vals), yerr=errs, color=color, lw=2, marker=marker,
                      ms=7, mew=0, capsize=2.5, label=label)
    ax_d.plot(areas, [p1**a for a in areas], color=INK, lw=1.6, ls="--",
              label=r"exact  $p^{RT}$")
    ax_d.set_yscale("log")
    ax_d.set_xlabel(r"loop area $R\times T$")
    ax_d.set_ylabel(r"$\langle W\rangle$")
    ax_d.set_title("(d) area law — tests 2D plaquette factorization", loc="left", fontsize=10)
    ax_d.legend(frameon=False, fontsize=8.5)

    fig.suptitle(f"SU(2) lift {sam['coarse_L']} -> {fine_L}, "
                 rf"$\beta_f$ = {fine_beta:g}   (n = {gen_cfg.shape[0]})",
                 fontsize=11, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
