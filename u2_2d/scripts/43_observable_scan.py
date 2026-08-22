"""Figure 29 -- observable agreement across the coupling range.

The u2 equivalent of u1's main-text figure 8 (`13_beta_scan.png`), and the last
substantive figure-parity gap: u2 has only ever reported observable agreement at
the TWO validated ladder rungs, which is a pass/fail at two points rather than a
scan.

WHAT IT MEASURES, and why it is not a repeat of the t_therm scan. Figure 21
grades the seed by how many HMC trajectories it needs, which folds the model and
the tail together. This grades the RAW LIFT directly, against the closed form,
before and after ten rethermalization sweeps -- so it separates what the model
delivers from what the tail repairs, on the axis (coupling) where the coverage
story lives.

Two things it should show, and the second is the useful one:

  * agreement of a few parts in 10^4-10^5 wherever the coupling is near a
    training rung, which is the ordinary validation claim; and
  * the degradation running with DISTANCE TO THE NEAREST TRAINING RUNG rather
    than with beta -- visible here on observables, not inferred from a
    thermalization count.

The training rungs are drawn as ticks and the region past the top rung is
hatched, exactly as in figure 21, so the two figures can be read against each
other.

    python u2_2d/scripts/43_observable_scan.py --device cuda
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

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.lattice import half_retr, plaquette, wilson_loop
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import load_det_model, model_beta
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_ensemble, resolve_device,
                         save_json, set_seed)

LOOPS = [(1, 1), (2, 2), (4, 4)]
COLOURS = {"W1x1": "#0072B2", "W2x2": "#009E73", "W4x4": "#D55E00"}
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"
TRAIN_MODEL_BETA = [0.622, 1.705, 3.560, 7.020, 12.946, 14.008, 26.417,
                    50.789, 104.132]
TOP_RUNG = 104.132


def rel_dev(links, beta, size):
    """Relative deviation AND z, because the two say different things here.

    `|generated/exact - 1|` is the model's systematic in physical units, but it
    is NOT comparable across beta: the theory's own per-configuration spread
    falls by orders of magnitude as beta rises, so an unnormalized ratio drifts
    downward on the beta axis whether or not the model improves. Reporting it
    alone reproduces exactly the error that killed the W(8x8) retherm claim
    (see out/u2_2d/retherm_reconcile/RECONCILIATION.md). z = bias / SEM says
    whether the deviation is resolved at all at this ensemble size.
    """
    out = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            v = (half_retr(plaquette(links)) if (nx, ny) == (1, 1)
                 else half_retr(wilson_loop(links, nx, ny)))
            v = v.mean(dim=(1, 2)).cpu().numpy().astype(float)
            exact = (plaquette_exact(beta, size) if (nx, ny) == (1, 1)
                     else wilson_loop_exact(beta, nx * ny))
            bias = float(v.mean() - exact)
            sigma = float(v.std(ddof=1))
            sem = sigma / math.sqrt(len(v))
            out[f"W{nx}x{ny}"] = float(abs(bias / exact))
            out[f"z_W{nx}x{ny}"] = float(bias / sem) if sem > 0 else 0.0
            out[f"sigma_W{nx}x{ny}"] = float(sigma / abs(exact))
        out["n_configs"] = int(len(v))
    return out


def gap_pct(mb):
    r = min(TRAIN_MODEL_BETA, key=lambda t: abs(t - mb))
    return 100.0 * (mb - r) / r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--checkpoint", default="out/u2_2d/checkpoints/det_score_net.pt")
    ap.add_argument("--data-dir", default="out/u2_2d/data_v2")
    ap.add_argument("--coarse-size", type=int, default=16)
    ap.add_argument("--coarse-betas",
                    default="4.0544,8.0115,14.8468,23.6203,33.4572,45.4637,"
                            "67.4077,105.244,135.861,199.229,267.858,328.665")
    ap.add_argument("--n-configs", type=int, default=64)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--n-su2", type=int, default=30)
    ap.add_argument("--retherm", type=int, default=10)
    ap.add_argument("--seed", type=int, default=808)
    ap.add_argument("--out-dir", default="out/u2_2d/observable_scan")
    ap.add_argument("--fig", default="out/u2_2d/figures/fig29_observable_scan.png")
    ap.add_argument("--replot", action="store_true",
                    help="redraw from the saved json without re-running the "
                         "lift; the measurement costs GPU minutes and the "
                         "figure should be tunable for free")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if args.replot:
        import json
        rows = json.loads((out / "observable_scan.json").read_text(encoding="utf-8"))
        print(f"replotting {len(rows)} rows from {out / 'observable_scan.json'}")
        return draw(rows, args)

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    set_seed(args.seed)
    model, sched = load_det_model(args.checkpoint, device=device)

    rows = []
    print(f"\n{'beta_f':>9s} {'model_b':>8s} {'gap%':>7s} "
          + "".join(f"{k} raw".rjust(12) for k in ("W1x1", "W2x2", "W4x4"))
          + "".join(f"{k} +10".rjust(12) for k in ("W1x1", "W2x2", "W4x4")))
    for cb in [float(b) for b in args.coarse_betas.split(",")]:
        path = Path(args.data_dir) / f"u2_L{args.coarse_size}_beta{cb:g}.pt"
        if not path.exists():
            print(f"(skip) missing {path}")
            continue
        coarse, _ = load_ensemble(path)
        coarse = coarse[:args.n_configs]
        beta = topology_matched_fine_beta(cb, args.coarse_size)
        size = args.coarse_size * 2
        t0 = time.time()
        fine = generate_fine_from_coarse(
            model, sched, coarse, beta, n_su2_sweeps=args.n_su2, device=device,
            n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
            batch_size=32, consistency_weight=1.0, physics_blend_coef=0.0)
        state = fine.to(device)
        raw = rel_dev(state, beta, size)
        post = rel_dev(retherm_sweeps(state, WilsonU2Action(beta), args.retherm),
                       beta, size)
        mb = model_beta(beta)
        rows.append({"coarse_beta": cb, "beta": beta, "model_beta": mb,
                     "lattice_size": size, "gap_pct": gap_pct(mb),
                     "raw": raw, "post": post, "seconds": time.time() - t0})
        save_json(out / "observable_scan.json", rows)
        print(f"{beta:9.2f} {mb:8.2f} {gap_pct(mb):+7.1f} "
              + "".join(f"{raw[k]:12.3e}" for k in ("W1x1", "W2x2", "W4x4"))
              + "".join(f"{post[k]:12.3e}" for k in ("W1x1", "W2x2", "W4x4")))

    if not rows:
        print("nothing measured")
        return 1

    return draw(rows, args)


def draw(rows, args) -> int:
    fig, axes = plt.subplots(2, 2, figsize=(12.4, 8.4))
    panels = ((axes[0][0], "raw", None, "(a) raw lift, before the tail"),
              (axes[0][1], "post", None,
               f"(b) after {args.retherm} rethermalization sweeps"),
              (axes[1][0], "raw", "z", "(c) raw lift, in units of the SEM"),
              (axes[1][1], "post", "z",
               f"(d) after {args.retherm} sweeps, in units of the SEM"))
    for ax, key, mode, title in panels:
        for k in ("W1x1", "W2x2", "W4x4"):
            kk = k if mode is None else f"z_{k}"
            ys = [(abs(r[key][kk]) if mode else r[key][kk]) for r in rows]
            ax.plot([r["model_beta"] for r in rows], ys,
                    "o-", color=COLOURS[k], lw=1.9, ms=6.5,
                    markeredgecolor="white", markeredgewidth=0.7, zorder=4,
                    label=k.replace("W", "W(") + ")")
        ax.axvline(TOP_RUNG, color="#5a3a8a", lw=1.2, ls=(0, (3, 2)), zorder=3)
        ax.axvspan(TOP_RUNG, max(r["model_beta"] for r in rows) * 1.5,
                   facecolor="none", edgecolor="#5a3a8a", hatch="///", lw=0.0,
                   alpha=0.45, zorder=2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        if mode == "z":
            ax.axhline(2.0, color=INK, lw=1.1, ls=(0, (4, 2)), zorder=3)
            ax.annotate("|z| = 2: below this the deviation is not "
                        "resolved at this ensemble size", xy=(0.02, 0.06),
                        xycoords="axes fraction", fontsize=7.5, color=MUTED)
            ax.set_ylabel(r"$|z| = |$bias$| \, / \,$SEM", fontsize=10, color=INK)
            ax.set_xlabel(r"model $\beta$ of the fine rung", fontsize=10,
                          color=INK)
        else:
            ax.set_ylabel(r"$|$generated / exact $- 1|$", fontsize=10, color=INK)
        for t in TRAIN_MODEL_BETA:
            ax.plot([t], [ax.get_ylim()[0]], marker="|", ms=9, color="#2e7d32",
                    mew=1.6, clip_on=False, zorder=7)
        # The two couplings that land ON a training rung are the whole point of
        # the figure and must not be left for the reader to spot: in panel (c)
        # they are the only points that break an otherwise monotone rise, by a
        # factor of ~20, and the only two with POSITIVE bias. Marking them is
        # also the honest move -- they are in-sample and cannot be quoted as
        # evidence of generalization.
        for r in rows:
            if abs(r["gap_pct"]) < 2.0:
                ax.axvline(r["model_beta"], color="#b3202b", lw=1.1,
                           ls=(0, (2, 2)), zorder=3, alpha=0.85)
                ax.annotate("IN-SAMPLE", xy=(r["model_beta"], 0.985),
                            xycoords=("data", "axes fraction"), rotation=90,
                            fontsize=6.8, color="#b3202b", ha="right",
                            va="top", weight="bold")
        ax.set_title(title, fontsize=10.5, loc="left", color=INK)
        ax.grid(alpha=0.25, which="both", color=GRID)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0][0].legend(frameon=False, fontsize=8.5, loc="lower left")
    axes[0][1].annotate("green ticks: training rungs\nhatched: past top rung",
                        xy=(0.97, 0.9), xycoords="axes fraction", fontsize=7.5,
                        color=MUTED, ha="right")
    fig.suptitle("Observable agreement: the physical systematic (top) and "
                 "whether it is resolved (bottom)",
                 fontsize=12.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    dest = Path(args.fig)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {dest}")
    print(f"wrote {Path(args.out_dir) / 'observable_scan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
