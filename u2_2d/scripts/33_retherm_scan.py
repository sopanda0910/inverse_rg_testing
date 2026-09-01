"""Figure 25 -- how many rethermalization sweeps, decided by measurement.

`n_retherm` is 10 in `configs/default.yaml`. It was chosen to make the plaquette
agree and validated on the plaquette, and the plaquette is the one observable the
tail repairs best -- so the setting was tuned on the axis where every setting
looks good.

WHAT THIS SCRIPT MEASURES, and why the criterion is not "does the plaquette
agree". Local rethermalization is a LOW-PASS repair: `59_pre_post_retherm.py`
finds the repair factor (|bias before| / |bias after|) falling monotonically with
loop size in u1 -- 64x at W(1x1), 3.9x at W(4x4), 0.99x at W(8x8) -- and in u2 at
beta = 416.5 it goes BELOW one at W(8x8), i.e. the tail actively damages the
largest loop. Topology is at repair factor exactly zero by construction, since
retherm runs with `topological_updates=False`.

So the right question is not "is the plaquette right" but "where does the repair
factor cross one", and the right objective is the WORST scale rather than the
best:

    n* = argmin over n of   max over scales of   |bias(n)| / sigma_1config

`bias / sigma_1config` is used rather than z because it does not depend on how
many configurations this scan happens to generate, and because it is the
quantity that sets N* = (sigma/bias)^2 -- the number of configurations a user
may take before the model's systematic exceeds their own statistical error.

Expect a TRADE, not a free optimum. At zero sweeps the ultraviolet is bad; at
many sweeps the infrared drifts. There may be no setting that puts every scale
under the floor, in which case the honest output is an operating point plus the
N* ceiling it implies -- which is what the summary prints.

    python u2_2d/scripts/33_retherm_scan.py --device cuda
"""
from __future__ import annotations

import argparse
import json
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
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_config, load_ensemble,
                         resolve_device, save_json, set_seed)

LOOPS = [(1, 1), (2, 2), (4, 4), (6, 6), (8, 8)]
INK, MUTED, GRID = "#1a1a1a", "#5c5c5c", "#d8d8d8"


def measure(links: torch.Tensor, beta: float, size: int) -> dict:
    rec = {}
    with torch.no_grad():
        for nx, ny in LOOPS:
            v = (half_retr(plaquette(links)) if (nx, ny) == (1, 1)
                 else half_retr(wilson_loop(links, nx, ny)))
            v = v.mean(dim=(1, 2)).cpu().numpy().astype(float)
            exact = (plaquette_exact(beta, size) if (nx, ny) == (1, 1)
                     else wilson_loop_exact(beta, nx * ny, lattice_size=size))
            sigma = v.std(ddof=1)
            bias = v.mean() - exact
            key = f"wilson_{nx}x{ny}"
            rec[key] = {
                "relative_deviation": float(bias / exact),
                "bias_over_sigma": float(abs(bias) / max(sigma, 1e-18)),
                # N* is the practitioner's number: configurations usable before
                # the systematic exceeds the user's own statistical error.
                "n_star": (float((sigma / bias) ** 2) if bias != 0
                           else float("inf")),
                "z": float(bias / max(sigma / math.sqrt(len(v)), 1e-18)),
            }
        q = topological_charge(links).round()
        rec["q_squared"] = float((q ** 2).mean())
    return rec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--data-dir", default="out/u2_2d/data_v2")
    parser.add_argument("--cases", default="16:105.244,32:105.244",
                        help="coarse_L:coarse_beta pairs")
    parser.add_argument("--n-configs", type=int, default=256)
    parser.add_argument("--sampler-steps", type=int, default=200)
    parser.add_argument("--n-su2", type=int, default=30)
    parser.add_argument("--sweeps", default="0,2,5,10,20,40,80")
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--out-dir", default="out/u2_2d/retherm_scan")
    args = parser.parse_args()

    config = load_config(args.config)
    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)
    ckpt = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    model, sched = load_det_model(ckpt, device=device)
    print(f"checkpoint {ckpt}")

    sweeps = [int(s) for s in args.sweeps.split(",")]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []

    for case in args.cases.split(","):
        cl, cb = case.split(":")
        coarse_size, coarse_beta = int(cl), float(cb)
        from u2_2d.lgt.blocking import topology_matched_fine_beta
        beta = topology_matched_fine_beta(coarse_beta, coarse_size)
        size = coarse_size * 2
        t0 = time.time()
        path = Path(args.data_dir) / f"u2_L{coarse_size}_beta{coarse_beta:g}.pt"
        if not path.exists():
            print(f"  (skip) missing {path}")
            continue
        coarse, _ = load_ensemble(path)
        coarse = coarse[:args.n_configs]
        fine = generate_fine_from_coarse(
            model, sched, coarse, beta, n_su2_sweeps=args.n_su2, device=device,
            n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
            batch_size=64, consistency_weight=1.0, physics_blend_coef=0.0)
        action = WilsonU2Action(beta)
        print(f"\nL={size}, beta={beta:.3f}, {fine.shape[0]} configs "
              f"[lift {time.time() - t0:.0f}s]")

        rec = {"coarse_size": coarse_size, "coarse_beta": coarse_beta,
               "lattice_size": size, "beta": beta,
               "n_configs": int(fine.shape[0]), "by_sweeps": {}}
        # CUMULATIVE, so every row is the same configurations carried further
        # and the rows are paired rather than independent draws.
        state = fine.to(device)
        done = 0
        for n in sweeps:
            if n > done:
                state = retherm_sweeps(state, action, n - done)
                done = n
            m = measure(state, beta, size)
            rec["by_sweeps"][str(n)] = m
            worst = max(m[f"wilson_{a}x{b}"]["bias_over_sigma"] for a, b in LOOPS)
            print(f"  {n:3d} sweeps  bias/sigma: "
                  + " ".join(f"{m[f'wilson_{a}x{b}']['bias_over_sigma']:7.4f}"
                             for a, b in LOOPS)
                  + f"   worst {worst:.4f}  <Q^2> {m['q_squared']:.3f}")
        # The objective: minimise the WORST scale, not the best one.
        rec["worst_by_sweeps"] = {
            str(n): max(rec["by_sweeps"][str(n)][f"wilson_{a}x{b}"]["bias_over_sigma"]
                        for a, b in LOOPS) for n in sweeps}
        best = min(sweeps, key=lambda n: rec["worst_by_sweeps"][str(n)])
        rec["best_n_retherm"] = best
        rec["n_star_at_best"] = min(
            rec["by_sweeps"][str(best)][f"wilson_{a}x{b}"]["n_star"]
            for a, b in LOOPS)
        print(f"  -> best n_retherm = {best} "
              f"(worst-scale bias/sigma {rec['worst_by_sweeps'][str(best)]:.4f}, "
              f"N* ceiling {rec['n_star_at_best']:.0f} configurations)")
        records.append(rec)
        save_json(out / "retherm_scan.json", records)

    if not records:
        print("no cases ran")
        return 1

    # Figure: repair by scale against sweep count, one panel per case. The
    # case count is set by --cases and can in principle exceed a single row,
    # so wrap into a grid capped at 4 columns and rescale to full text width.
    n_cases = len(records)
    cols = min(n_cases, 4)
    rows = math.ceil(n_cases / cols)
    _per_panel_w = 6.9 / cols
    _scale = _per_panel_w / 6.4
    _per_panel_h = round(4.8 * _scale, 2)
    fig, axes = plt.subplots(rows, cols,
                             figsize=(round(cols * _per_panel_w, 2),
                                      round(rows * _per_panel_h, 2)),
                             squeeze=False)
    axes_flat = axes.ravel()
    for ax, rec in zip(axes_flat, records):
        for (a, b), colour in zip(LOOPS, ["#0072B2", "#009E73", "#E69F00",
                                          "#D55E00", "#CC79A7"]):
            key = f"wilson_{a}x{b}"
            ys = [rec["by_sweeps"][str(n)][key]["bias_over_sigma"] for n in sweeps]
            ax.plot(sweeps, ys, "o-", color=colour, lw=1.8, ms=5,
                    markeredgecolor="white", markeredgewidth=0.6,
                    label=f"W({a}x{b})")
        ax.axvline(rec["best_n_retherm"], color="k", lw=1.2, ls=(0, (4, 3)))
        ax.annotate(f"best = {rec['best_n_retherm']}",
                    xy=(rec["best_n_retherm"], 0.92), xycoords=("data", "axes fraction"),
                    fontsize=8, ha="left", color=INK)
        ax.axvline(10, color="#c2571a", lw=1.0, ls=(0, (1, 2)))
        ax.annotate("deployed = 10", xy=(10, 0.06),
                    xycoords=("data", "axes fraction"), fontsize=7.5,
                    ha="right", color="#c2571a", rotation=90)
        ax.set_yscale("log")
        ax.set_xscale("symlog", linthresh=1.0)
        ax.set_xlabel("rethermalization sweeps", fontsize=10, color=INK)
        ax.set_title(f"L = {rec['lattice_size']}, " + r"$\beta$ = "
                     + f"{rec['beta']:.1f}", fontsize=10.5, loc="left")
        ax.grid(alpha=0.25, which="both", color=GRID)
        ax.legend(frameon=False, fontsize=8)
    for ax in axes_flat[len(records):]:
        ax.set_visible(False)
    axes_flat[0].set_ylabel(r"|bias| / $\sigma$ of one configuration", fontsize=10,
                            color=INK)
    fig.suptitle("Choosing n_retherm on the WORST scale, not the plaquette",
                 fontsize=12, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    dest = Path("out/u2_2d/figures/fig25_retherm_scan.png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _dpi = max(150, min(450, round(200 / _scale)))
    fig.savefig(dest, dpi=_dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {dest}")
    print(f"wrote {out / 'retherm_scan.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
