"""Observable agreement across the coupling range, in ppm AND in z.

The u1 counterpart of `u2_2d/scripts/43_observable_scan.py` (fig29), closing the
last measurement gap in `docs/PARITY_U1_U2.md` section 2. u1 has beta scans
inside the generalization study, but no single figure of |z| against coupling
with the training range marked -- and the u2 version of this figure is the one
that showed why that matters.

WHY BOTH STATISTICS. `|generated/exact - 1|` is the model's systematic in
physical units, but it is NOT comparable across beta: the theory's own
per-configuration spread falls by orders of magnitude as beta rises, so an
unnormalized ratio drifts downward whether or not the model improves. In u2 that
artefact was large enough to reverse the conclusion -- Spearman(model beta,
post-tail relative deviation) = -0.82, which becomes +0.80 in z. This script
records and plots both, and the two panels below the fold are the honest ones.

COVERAGE. u1's deployed `v3_scale` config trains on 4 fixed rungs plus 102
randomly sampled ones, all with `beta_max = 60`. So beta is densely covered up
to 60 and not at all above it, and the region past 60 is hatched -- the analogue
of u2's "past the top rung", but a cleaner one, because u1's coverage is dense
rather than a set of isolated rungs.

Errors are tau_int-aware (NARRATIVE 25.7 / M4), so the z here is directly
comparable with `59_pre_post_retherm.py` and `60_multi_lift_compounding.py`.

    python u1_2d/scripts/62_observable_scan.py --device cuda
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_fine_beta
from u1_2d.lgt.exact import wilson_loop_exact
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, wilson_loop_angles
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import generate_fine_from_coarse
from u1_2d.utils import save_json, set_seed
from u1_2d.validate.stats import autocorr_aware_mean_err

LOOPS = [(1, 1), (2, 2), (4, 4)]
COLOURS = {"W1x1": "#0072B2", "W2x2": "#009E73", "W4x4": "#D55E00"}
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
TRAIN_BETA_MAX = 60.0
FIXED_RUNGS = [14.1464, 25.0, 40.0, 55.0237]


def measure(field, beta, size, n_chains):
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            ang = (plaquette_angles(field) if (nx, ny) == (1, 1)
                   else wilson_loop_angles(field, nx, ny))
            v = torch.cos(ang).mean(dim=(-2, -1)).cpu().numpy().astype(float)
            exact = wilson_loop_exact(beta, nx * ny, "wilson", size)
            mean, err, tau = autocorr_aware_mean_err(v, n_chains)
            bias = mean - exact
            out[f"W{nx}x{ny}"] = float(abs(bias / exact))
            out[f"z_W{nx}x{ny}"] = float(bias / max(err, 1e-15))
            out[f"tau_W{nx}x{ny}"] = float(tau)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", default="out/u1_2d/checkpoints/score_net.pt")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--coarse-size", type=int, default=16)
    ap.add_argument("--coarse-betas",
                    default="2.0,3.5,5.5,8.0,11.0,14.1464,18.0,25.0,32.0,40.0,"
                            "55.0237,72.0,95.0,130.0")
    ap.add_argument("--n-configs", type=int, default=128)
    ap.add_argument("--n-chains", type=int, default=16)
    ap.add_argument("--burn-in", type=int, default=600)
    ap.add_argument("--thin", type=int, default=5)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--retherm", type=int, default=10)
    ap.add_argument("--seed", type=int, default=909)
    ap.add_argument("--out-dir", default="out/u1_2d/observable_scan")
    ap.add_argument("--fig",
                    default="out/u1_2d/paper_appendix/figures/46_observable_scan.png")
    ap.add_argument("--replot", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if args.replot:
        import json
        rows = json.loads((out / "observable_scan.json").read_text(encoding="utf-8"))
        return draw(rows, args)

    set_seed(args.seed)
    model, schedule = load_checkpoint(args.checkpoint, args.device)
    rows = []
    print(f"\n{'beta_f':>9s} {'cover':>7s} "
          + "".join(f"{k} raw".rjust(12) for k in ("W1x1", "W2x2", "W4x4"))
          + "".join(f"z {k} raw".rjust(12) for k in ("W1x1", "W2x2", "W4x4")))
    for cb in [float(b) for b in args.coarse_betas.split(",")]:
        beta = approx_matched_fine_beta(cb, "wilson")
        size = args.coarse_size * 2
        t0 = time.time()
        action_c = make_action("wilson", cb)
        step_c, nst_c = adapted_hmc_params(cb)
        coarse, _ = run_hmc_ensemble(
            args.coarse_size, action_c, n_configs=args.n_configs,
            n_chains=args.n_chains, burn_in=args.burn_in, thin=args.thin,
            step_size=step_c, n_steps=nst_c, device=args.device,
            topological_updates=True)
        fine = generate_fine_from_coarse(
            model, schedule, coarse.cpu(), beta, device=args.device,
            n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
            batch_size=64, consistency_weight=1.0)
        raw = measure(fine, beta, size, args.n_chains)
        post = measure(retherm_sweeps(fine, make_action("wilson", beta),
                                      args.retherm), beta, size, args.n_chains)
        rows.append({"coarse_beta": cb, "beta": beta, "lattice_size": size,
                     "in_coverage": bool(beta <= TRAIN_BETA_MAX),
                     "raw": raw, "post": post, "seconds": time.time() - t0})
        save_json(out / "observable_scan.json", rows)
        print(f"{beta:9.2f} {'in' if beta <= TRAIN_BETA_MAX else 'PAST':>7s} "
              + "".join(f"{raw[k]:12.3e}" for k in ("W1x1", "W2x2", "W4x4"))
              + "".join(f"{raw['z_' + k]:12.2f}" for k in ("W1x1", "W2x2", "W4x4")))

    if not rows:
        print("nothing measured")
        return 1
    return draw(rows, args)


def draw(rows, args) -> int:
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.4))
    top = max(r["beta"] for r in rows) * 1.5
    panels = ((axes[0][0], "raw", None, "(a) raw lift, before the tail"),
              (axes[0][1], "post", None,
               f"(b) after {args.retherm} rethermalization sweeps"),
              (axes[1][0], "raw", "z", "(c) raw lift, in units of the SEM"),
              (axes[1][1], "post", "z",
               f"(d) after {args.retherm} sweeps, in units of the SEM"))
    for ax, key, mode, title in panels:
        for k in ("W1x1", "W2x2", "W4x4"):
            kk = k if mode is None else f"z_{k}"
            ys = [abs(r[key][kk]) for r in rows]
            ax.plot([r["beta"] for r in rows], ys, "o-", color=COLOURS[k],
                    lw=1.9, ms=6.5, markeredgecolor="white",
                    markeredgewidth=0.7, zorder=4,
                    label=k.replace("W", "W(") + ")")
        ax.axvline(TRAIN_BETA_MAX, color="#5a3a8a", lw=1.2, ls=(0, (3, 2)),
                   zorder=3)
        ax.axvspan(TRAIN_BETA_MAX, top, facecolor="none", edgecolor="#5a3a8a",
                   hatch="///", lw=0.0, alpha=0.45, zorder=2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(min(r["beta"] for r in rows) * 0.8, top / 1.25)
        if mode == "z":
            ax.axhline(2.0, color=INK, lw=1.1, ls=(0, (4, 2)), zorder=3)
            ax.set_ylabel(r"$|z| = |$bias$|\,/\,$SEM", fontsize=10, color=INK)
            ax.set_xlabel(r"fine $\beta$", fontsize=10, color=INK)
            ax.annotate(r"$|z|=2$: below this the deviation is not resolved",
                        xy=(0.02, 0.05), xycoords="axes fraction",
                        fontsize=7.5, color=MUTED)
        else:
            ax.set_ylabel(r"$|$generated / exact $-1|$", fontsize=10, color=INK)
        for t in FIXED_RUNGS:
            ax.plot([t], [ax.get_ylim()[0]], marker="|", ms=9, color="#2e7d32",
                    mew=1.6, clip_on=False, zorder=7)
        ax.set_title(title, fontsize=10.5, loc="left", color=INK)
        ax.grid(alpha=0.25, which="both", color=GRID)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0][0].legend(frameon=False, fontsize=8.5, loc="upper left")
    axes[0][1].annotate("green ticks: the 4 fixed rungs\n"
                        r"hatched: past $\beta_{max}=60$," "\nthe ceiling of "
                        "the 102 random rungs",
                        xy=(0.03, 0.04), xycoords="axes fraction", fontsize=7.5,
                        color=MUTED, ha="left")
    fig.suptitle("u1 observable agreement: the physical systematic (top) and "
                 "whether it is resolved (bottom)",
                 fontsize=12.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    dest = Path(args.fig)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
