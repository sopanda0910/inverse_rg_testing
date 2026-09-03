"""Stage 22: observable DISTRIBUTIONS, exact vs HMC vs diffusion, before and
after rethermalization.

The gap this closes. `10_paper_figures.py` draws Wilson-loop distributions
(fig08) but only for the delivered, post-rethermalization ensemble, and
`fig11_ladder_accuracy` shows the before/after split as a single scalar per rung
-- the mean plaquette. So nothing in the study shows what the MODEL produces as
opposed to what the local sweeps repair, at the level of a distribution.

That split is the whole argument of the prolongator ablation: 10 rethermalization
sweeps take a 19% plaquette error to 1e-6, so any post-retherm plot is measuring
the repair stage as much as the lift. The pre-retherm distribution is the honest
picture of the generative model.

Pre-retherm configurations are not saved anywhere -- `generate_ladder` records
`plaquette_pre_retherm` as a scalar and discards the ensemble -- so this script
regenerates them with `generate_fine_from_coarse`, which is exactly the ladder's
own lift plus conditional SU(2) sweeps and no rethermalization.

Four arms per panel:
  exact       closed form (a line for means, bars for P(Q))
  HMC         the stage-01 reference ensemble at the same (L, beta)
  pre         diffusion lift + conditional SU(2) sweeps, NO rethermalization
  post        the delivered ladder ensemble

Figures written:
  fig16_distributions_{tag}.png   Wilson loops at four areas, plus P(Q) and |Q|
  fig17_z_distribution.png        z against the closed form, all observables,
                                  pre vs post -- the u1_2d fig37 analogue
  fig18_z_vs_loop_area.png        std(z) vs loop area -- the u1_2d fig38 analogue

    python u2_2d/scripts/22_distribution_figures.py --rung -1
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, ensemble_path, load_config,
                         load_ensemble, resolve_device, save_json,
                         resolve_device, set_seed)
from u2_2d.validate.observables import exact_reference, measure_ensemble

# Okabe-Ito, consistent with the rest of the figure set.
C_HMC = "#c2571a"
C_PRE = "#8a6fbf"
C_POST = "#1b6ca8"
C_EXACT = "#000000"

PANEL_LOOPS = ["plaquette", "wilson_2x2", "wilson_4x4", "wilson_8x8"]


def _loop_area(name: str) -> int | None:
    if not name.startswith("wilson_"):
        return 1 if name == "plaquette" else None
    try:
        a, b = name.rsplit("_", 1)[1].split("x")
        return int(a) * int(b)
    except (ValueError, IndexError):
        return None


def figure_distributions(meas: dict, exact: dict, beta: float, size: int,
                         path: Path) -> None:
    """Wilson loops at four areas, plus P(Q) and |Q|, four arms each."""
    fig, axes = plt.subplots(2, 3, figsize=(6.9, 3.52))
    flat = axes.ravel()

    for ax, name in zip(flat[:4], PANEL_LOOPS):
        arrays = {k: np.asarray(v[name], dtype=float)
                  for k, v in meas.items() if name in v}
        lo = min(a.min() for a in arrays.values())
        hi = max(a.max() for a in arrays.values())
        bins = np.linspace(lo, hi, 40)
        if "pre" in arrays:
            ax.hist(arrays["pre"], bins=bins, density=True, alpha=0.45,
                    color=C_PRE, label=f"pre-retherm ({arrays['pre'].std():.1e})")
        if "post" in arrays:
            ax.hist(arrays["post"], bins=bins, density=True, alpha=0.55,
                    color=C_POST, label=f"post-retherm ({arrays['post'].std():.1e})")
        if "hmc" in arrays:
            ax.hist(arrays["hmc"], bins=bins, density=True, histtype="step",
                    color=C_HMC, lw=1.7,
                    label=f"HMC ({arrays['hmc'].std():.1e})")
        if name in exact:
            ax.axvline(exact[name], color=C_EXACT, lw=1.3, ls="--",
                       label="exact mean")
        ax.set_title(name.replace("wilson_", "W ").replace("plaquette", "W 1x1"),
                     fontsize=10)
        ax.set_xlabel(r"$\frac{1}{2}\,\mathrm{ReTr}\,W$")
        # frameon=True with an opaque-ish backing, NOT the project's usual
        # frameon=False -- unlike a line/scatter plot with a free corner,
        # these panels overlay two semi-transparent histograms plus a step
        # histogram that together cover nearly the whole panel, so there is
        # no location "best" can pick without landing on dense bars. Without
        # a background the legend text became illegible, overlapping the
        # peak bars directly (caught 2026-09-03 on fig16_distributions_
        # L64_beta416.524.png). A white, mostly-opaque box behind the text
        # fixes legibility regardless of where the data happens to peak.
        ax.legend(frameon=True, fontsize=7, facecolor="white",
                  framealpha=0.85, edgecolor="none")
        ax.grid(alpha=0.2)
        ax.xaxis.set_major_locator(plt.MaxNLocator(4))
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
    flat[0].set_ylabel("density")
    flat[3].set_ylabel("")

    # --- P(Q) --------------------------------------------------------------
    ax = flat[4]
    q_values, q_probs = det_topological_charge_distribution(beta, size)
    keep = q_probs > 1e-4
    q_values, q_probs = q_values[keep], q_probs[keep]
    width = 0.2
    ax.bar(q_values - 1.5 * width, q_probs, width, color=C_EXACT, alpha=0.75,
           label="exact")
    for off, key, col in ((-0.5, "hmc", C_HMC), (0.5, "pre", C_PRE),
                          (1.5, "post", C_POST)):
        if key not in meas:
            continue
        q = np.asarray(meas[key]["topological_charge"], dtype=float).round()
        counts = np.array([np.mean(q == v) for v in q_values])
        ax.bar(q_values + off * width, counts, width, color=col, alpha=0.8,
               label=key)
    ax.set_xlabel("$Q$")
    ax.set_ylabel("$P(Q)$")
    ax.set_title("topological charge", fontsize=10)
    ax.legend(frameon=True, fontsize=7, facecolor="white", framealpha=0.85,
              edgecolor="none")
    ax.grid(alpha=0.2, axis="y")

    # --- <Q^2> -------------------------------------------------------------
    ax = flat[5]
    labels, vals, errs, cols = [], [], [], []
    for key, col in (("hmc", C_HMC), ("pre", C_PRE), ("post", C_POST)):
        if key not in meas:
            continue
        q = np.asarray(meas[key]["topological_charge"], dtype=float)
        q2 = q**2
        labels.append(key)
        vals.append(q2.mean())
        errs.append(q2.std(ddof=1) / math.sqrt(max(len(q2), 1)))
        cols.append(col)
    ax.bar(range(len(vals)), vals, yerr=errs, color=cols, alpha=0.85, capsize=4)
    q2_exact = float((q_values.astype(float) ** 2 * q_probs).sum() / q_probs.sum())
    ax.axhline(q2_exact, color=C_EXACT, ls="--", lw=1.3,
               label=f"exact {q2_exact:.3f}")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel(r"$\langle Q^2\rangle$")
    ax.set_title("second moment", fontsize=10)
    ax.legend(frameon=True, fontsize=8, facecolor="white", framealpha=0.85,
              edgecolor="none")
    ax.grid(alpha=0.2, axis="y")

    fig.suptitle(
        f"Observable distributions: $L = {size}$, " r"$\beta$ = " f"{beta:g}"
        "  —  rethermalization repairs the lift, so `pre` is the model",
        y=1.01)
    fig.tight_layout()
    fig.savefig(path, dpi=315, bbox_inches="tight")
    plt.close(fig)


def _z_rows(meas_arm: dict, exact: dict) -> list[tuple[str, float, int]]:
    rows = []
    for key, vals in meas_arm.items():
        if not (key == "plaquette" or key.startswith("wilson_")):
            continue
        target = exact.get(key)
        if target is None:
            continue
        arr = np.asarray(vals, dtype=float)
        if arr.ndim != 1 or arr.size < 2:
            continue
        err = arr.std(ddof=1) / math.sqrt(arr.size)
        if err <= 0:
            continue
        rows.append((key, (arr.mean() - target) / err, _loop_area(key) or 1))
    return rows


def figure_z(meas: dict, exact: dict, beta: float, size: int, path_hist: Path,
             path_area: Path) -> None:
    zr = {k: _z_rows(v, exact) for k, v in meas.items()
          if k in ("hmc", "pre", "post")}

    fig, ax = plt.subplots(figsize=(6.9, 4.03))
    bins = np.linspace(-6, 6, 33)
    for key, col in (("hmc", C_HMC), ("pre", C_PRE), ("post", C_POST)):
        if not zr.get(key):
            continue
        z = np.array([r[1] for r in zr[key]])
        ax.hist(z, bins=bins, density=True, alpha=0.5, color=col,
                label=f"{key}  mean|z| {np.abs(z).mean():.2f}")
    xs = np.linspace(-6, 6, 200)
    ax.plot(xs, np.exp(-xs**2 / 2) / math.sqrt(2 * math.pi), "k--", lw=1.2,
            label="unit normal")
    ax.set_xlabel("$z$ against the closed form")
    ax.set_ylabel("density")
    ax.set_title(f"Observable $z$-distribution: $L = {size}$, "
                 r"$\beta$ = " f"{beta:g}", fontsize=11)
    # Same overlapping-histograms legibility issue as figure_distributions'
    # Wilson-loop panels above -- three semi-transparent histograms plus a
    # curve, all centered near z=0 -- so give the legend a backing here too.
    ax.legend(frameon=True, fontsize=8, facecolor="white", framealpha=0.85,
              edgecolor="none")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(path_hist, dpi=157, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.9, 4.03))
    for key, col in (("hmc", C_HMC), ("pre", C_PRE), ("post", C_POST)):
        if not zr.get(key):
            continue
        by_area: dict[int, list[float]] = {}
        for _, z, area in zr[key]:
            by_area.setdefault(area, []).append(z)
        areas = sorted(by_area)
        ax.plot(areas, [abs(np.mean(by_area[a])) for a in areas], "o-",
                color=col, label=key, ms=4)
    ax.set_xscale("log")
    ax.set_xlabel("loop area $A$")
    ax.set_ylabel("$|z|$ against the closed form")
    ax.set_title("Deviation vs loop area — where residual model error lives",
                 fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(path_area, dpi=157, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--ladder-dir", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/figures")
    parser.add_argument("--rung", type=int, default=-1)
    parser.add_argument("--n-configs", type=int, default=256)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 2222)

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]
    ladder_dir = Path(args.ladder_dir or ladder_cfg.get("out_dir", "out/u2_2d/ladder"))
    data_dir = Path(args.data_dir or config["data"].get("out_dir", "out/u2_2d/data"))

    coarse_path = (ensemble_path(data_dir, int(base["lattice_size"]),
                                 float(base["beta"])) if rung == 0
                   else ensemble_path(ladder_dir, sizes[rung - 1],
                                      schedule[rung - 1], tag="ladder"))
    fine_path = ensemble_path(ladder_dir, size, beta, tag="ladder")
    for p in (coarse_path, fine_path):
        if not p.exists():
            print(f"missing {p} -- run stage 03 first")
            return 1

    coarse, _ = load_ensemble(coarse_path)
    post, _ = load_ensemble(fine_path)
    n = min(args.n_configs, coarse.shape[0], post.shape[0])
    coarse, post = coarse[:n], post[:n]
    print(f"rung {rung}: L={size} beta={beta:g}, {n} configs per arm")

    meas = {"post": measure_ensemble(post)}

    ref_path = ensemble_path(data_dir, size, beta)
    if ref_path.exists():
        hmc, _ = load_ensemble(ref_path)
        meas["hmc"] = measure_ensemble(hmc[:n])
        print(f"  HMC reference {ref_path.name} ({min(n, hmc.shape[0])} configs)")
    else:
        print(f"  no HMC reference at {ref_path.name} -- that arm is omitted")

    ckpt = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    if Path(ckpt).exists():
        print(f"  regenerating pre-retherm ensemble from {Path(ckpt).name}")
        model, sched = load_det_model(ckpt, device=device)
        pre = generate_fine_from_coarse(
            model, sched, coarse, beta,
            n_su2_sweeps=int(ladder_cfg.get("n_su2_sweeps", 30)), device=device,
            n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
            n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
            batch_size=int(ladder_cfg.get("batch_size", 64)),
            consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
            physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
        )
        meas["pre"] = measure_ensemble(pre)
    else:
        print(f"  missing {ckpt} -- pre-retherm arm omitted")

    exact = exact_reference(beta, size)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"L{size}_beta{beta:g}"

    figure_distributions(meas, exact, beta, size,
                         out_dir / f"fig16_distributions_{tag}.png")
    figure_z(meas, exact, beta, size,
             out_dir / f"fig17_z_distribution_{tag}.png",
             out_dir / f"fig18_z_vs_loop_area_{tag}.png")
    print(f"wrote fig16/fig17/fig18 for {tag}")

    summary = {"lattice_size": size, "beta": beta, "n_configs": n, "arms": {}}
    for key in ("hmc", "pre", "post"):
        if key not in meas:
            continue
        rows = _z_rows(meas[key], exact)
        z = np.array([r[1] for r in rows])
        q = np.asarray(meas[key]["topological_charge"], dtype=float)
        summary["arms"][key] = {
            "mean_abs_z": float(np.abs(z).mean()),
            "max_abs_z": float(np.abs(z).max()),
            "q_squared": float((q**2).mean()),
            "n_observables": int(z.size),
        }
        print(f"  {key:<5} mean|z| {np.abs(z).mean():5.2f}  max {np.abs(z).max():5.2f}"
              f"  <Q^2> {(q**2).mean():.3f}")
    save_json(out_dir / f"distributions_{tag}.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
