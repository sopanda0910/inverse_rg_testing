"""Figure 20 -- observable distributions against the CLASSICAL arms that actually run.

The distribution figures this replaces (`fig2_sectors`, `fig16`) compare the
generated ensemble against `out/u2_2d/data/`, whose sectors are INSTALLED by
`seed_exact_sectors` rather than sampled. Above the parity boundary that ensemble
cannot show freezing, so agreeing with its P(Q) demonstrates nothing -- the
config comment at the L = 64 rung says exactly that, and `06_figures.py` now
hatches the bar. This figure uses `26_freezing_arms.py`'s output instead: cold
start, unseeded, three sampler strengths, measured rather than installed.

Five arms, and the two diffusion arms are labelled apart because the difference
between them IS the argument:

    HMC (plain)          frozen. <Q^2> = 0.000, zero sector changes in 400
                         trajectories at L = 64, beta = 416.5.
    HMC + winding dQ=2   <Q^2> = 0.656. Mobile in charge, cannot change parity.
    HMC + winding dQ=1   <Q^2> = 1.062. The best classical sampler that exists
                         for this theory -- the honest baseline.
    diffusion PRE        the lift plus conditional SU(2) sweeps, NO
                         rethermalization. This is the MODEL, unaided.
    diffusion POST       after 10 rethermalization sweeps. This is what the
                         pipeline delivers, and it is a fair seed only if the
                         repair is cheap -- which is why both are drawn.

Reporting only POST would credit the model with the repair stage; reporting only
PRE would understate what the method delivers. Both, always.

    python u2_2d/scripts/29_honest_distributions.py --device cuda
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import (det_topological_charge_distribution, plaquette_exact,
                             wilson_loop_exact)
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, ensemble_path, load_config,
                         load_ensemble, resolve_device, save_json, set_seed)

LOOPS = [("wilson_1x1", 1, 1), ("wilson_2x2", 2, 2),
         ("wilson_4x4", 4, 4), ("wilson_8x8", 8, 8)]

ARMS = [
    ("hmc_frozen", "HMC (plain) -- FROZEN", "#D55E00", "-"),
    ("hmc_winding", r"HMC + winding $\Delta Q=2$", "#0072B2", "-"),
    ("hmc_winding_odd", r"HMC + winding $\Delta Q=1$", "#009E73", "-"),
    ("pre", "diffusion seed, PRE-retherm", "#E69F00", "--"),
    ("post", "diffusion seed, POST-retherm", "#CC79A7", "-"),
]


def measure(links: torch.Tensor) -> dict:
    with torch.no_grad():
        out = {name: half_retr(wilson_loop(links, nx, ny)).mean(dim=(1, 2)).cpu().numpy()
               for name, nx, ny in LOOPS}
        out["charge"] = topological_charge(links).round().cpu().numpy()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--arms-dir", default="out/u2_2d/freezing_arms")
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--ladder-dir", default=None)
    parser.add_argument("--n-configs", type=int, default=256)
    parser.add_argument("--out-dir", default="out/u2_2d/figures")
    args = parser.parse_args()

    config = load_config(args.config)
    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(99)

    ladder_cfg = config["ladder"]
    beta = float(ladder_cfg["beta_schedule"][-1])
    size = int(ladder_cfg["base"]["lattice_size"]) * 2 ** len(ladder_cfg["beta_schedule"])
    data_dir = Path(args.data_dir or config["data"]["out_dir"])
    ladder_dir = Path(args.ladder_dir or ladder_cfg["out_dir"])

    ens = {}
    for key, *_ in ARMS[:3]:
        tag = key.replace("hmc_", "")
        path = Path(args.arms_dir) / f"u2_L{size}_beta{beta:g}_{tag}.pt"
        if not path.exists():
            print(f"  missing {path} -- run 26_freezing_arms.py first")
            return 1
        ens[key] = load_ensemble(path)[0][:args.n_configs]

    # POST is the delivered ladder ensemble. PRE has to be regenerated: the
    # ladder records `plaquette_pre_retherm` as a scalar and discards the
    # configurations, so there is nothing on disk to load.
    ens["post"] = load_ensemble(ensemble_path(ladder_dir, size, beta, tag="ladder"))[0][:args.n_configs]

    ckpt = args.checkpoint or config["train"]["checkpoint_path"]
    model, sched = load_det_model(ckpt, device=device)
    coarse_size, coarse_beta = size // 2, float(ladder_cfg["beta_schedule"][-2]) \
        if len(ladder_cfg["beta_schedule"]) > 1 else float(ladder_cfg["base"]["beta"])
    coarse = load_ensemble(ensemble_path(ladder_dir, coarse_size, coarse_beta,
                                         tag="ladder"))[0][:args.n_configs]
    print(f"regenerating PRE-retherm from {ckpt}")
    ens["pre"] = generate_fine_from_coarse(
        model, sched, coarse, beta,
        n_su2_sweeps=int(ladder_cfg.get("n_su2_sweeps", 30)), device=device,
        n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
        n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
        batch_size=int(ladder_cfg.get("batch_size", 64)),
        consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
        physics_blend_coef=0.0).cpu()

    stats = {k: measure(v.to(device)) for k, v in ens.items()}
    qs, ps = det_topological_charge_distribution(beta, size)
    qs, ps = np.asarray(qs), np.asarray(ps)
    q2_exact = float((qs ** 2 * ps).sum())
    exact_loop = {name: (plaquette_exact(beta, size) if nx * ny == 1
                         else wilson_loop_exact(beta, nx * ny))
                  for name, nx, ny in LOOPS}

    fig, axes = plt.subplots(2, 3, figsize=(16.5, 8.4))
    flat = axes.ravel()

    for ax, (name, nx, ny) in zip(flat, LOOPS):
        lo = min(stats[k][name].min() for k, *_ in ARMS)
        hi = max(stats[k][name].max() for k, *_ in ARMS)
        bins = np.linspace(lo, hi, 34)
        for key, label, colour, ls in ARMS:
            ax.hist(stats[key][name], bins=bins, density=True, histtype="step",
                    lw=2.0, ls=ls, color=colour, label=label)
        ax.axvline(exact_loop[name], color="k", lw=1.6, ls=(0, (5, 2)), label="exact")
        ax.set_title(f"$W({nx}\\times{ny})$", fontsize=10)
        ax.set_xlabel(r"$\frac{1}{2}\mathrm{ReTr}\,W$")

    # P(Q)
    ax = flat[4]
    keep = ps > 1e-4
    qk, pk = qs[keep], ps[keep]
    w = 0.15
    for i, (key, label, colour, _) in enumerate(ARMS):
        counts = np.array([np.mean(stats[key]["charge"] == q) for q in qk])
        ax.bar(qk + (i - 2) * w, counts, w, color=colour, alpha=0.85, label=label)
    ax.plot(qk, pk, "ko-", lw=1.5, ms=5, label="exact")
    ax.set_xlabel("topological charge $Q$")
    ax.set_ylabel("$P(Q)$")
    ax.set_title("$P(Q)$ -- plain HMC never leaves $Q=0$", fontsize=10)

    # <Q^2> with across-configuration error bars.
    ax = flat[5]
    names, vals, errs, cols = [], [], [], []
    for key, label, colour, _ in ARMS:
        q = stats[key]["charge"]
        names.append(label.replace("HMC + winding ", "+wind\n").replace(
            "HMC (plain) -- FROZEN", "plain\nHMC").replace(
            "diffusion seed, ", "diff\n").replace("$\\Delta Q=2$", "dQ=2").replace(
            "$\\Delta Q=1$", "dQ=1"))
        vals.append(float((q ** 2).mean()))
        errs.append(float((q ** 2).std(ddof=1) / np.sqrt(len(q))))
        cols.append(colour)
    x = np.arange(len(names))
    ax.bar(x, vals, 0.62, yerr=errs, color=cols, alpha=0.9, capsize=3)
    ax.axhline(q2_exact, color="k", lw=1.5, ls=(0, (5, 2)), label="exact")
    for xi, (v, e) in enumerate(zip(vals, errs)):
        # A frozen arm has every Q equal to zero, so e == 0 and the z-score is
        # formally infinite. Printing a clamped 1e12 sigma looks like a bug and
        # buries the actual point, which is that the arm has NO spread at all.
        note = "frozen\n(no spread)" if e == 0.0 else f"({(v - q2_exact) / e:+.1f}$\\sigma$)"
        ax.annotate(f"{v:.3f}\n{note}", (xi, v + e), textcoords="offset points",
                    xytext=(0, 3), ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=7.5)
    ax.set_ylabel(r"$\langle Q^2 \rangle$")
    ax.set_title(r"$\langle Q^2\rangle$ against exact", fontsize=10)
    ax.legend(frameon=False, fontsize=8)

    flat[0].legend(frameon=False, fontsize=8)
    for ax in flat:
        ax.grid(alpha=0.22)
    fig.suptitle(f"$L={size}$, $\\beta={beta:g}$ -- generated vs the classical arms "
                 "that actually run (unseeded, cold start)", y=1.0, fontsize=12)
    fig.tight_layout()
    dest = Path(args.out_dir) / f"fig20_honest_distributions_L{size}_beta{beta:g}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {dest}")

    # z of every arm against the closed form, which is the table the figure
    # summarises. Wilson z uses the across-configuration SEM.
    report = {"beta": beta, "lattice_size": size, "n_configs": args.n_configs,
              "q_squared_exact": q2_exact, "arms": {}}
    print(f"\n{'arm':30s} " + " ".join(f"{n:>12s}" for n, _, _ in LOOPS) + f"{'<Q^2>':>12s}")
    for key, label, _, _ in ARMS:
        # z ALONE CANNOT SETTLE THE UV/IR QUESTION and must not be reported
        # alone. z = (mean - exact) / SEM, so a noisier observable passes a
        # |z| <= 2 test at a LARGER relative bias. Large Wilson loops are much
        # noisier per configuration than the plaquette, so any arm whatever
        # shows z falling with loop area for purely statistical reasons -- the
        # frozen classical arm does, and it has no model in it at all. The
        # relative deviation and the relative SEM are therefore recorded beside
        # z, so the physics can be separated from the error bar.
        zs, rel, rel_sem = {}, {}, {}
        for name, nx, ny in LOOPS:
            v = stats[key][name]
            sem = v.std(ddof=1) / np.sqrt(len(v))
            zs[name] = float((v.mean() - exact_loop[name]) / max(sem, 1e-12))
            rel[name] = float(v.mean() / exact_loop[name] - 1.0)
            rel_sem[name] = float(sem / abs(exact_loop[name]))
        q = stats[key]["charge"]
        sem_q = float((q ** 2).std(ddof=1) / np.sqrt(len(q)))
        # A completely frozen arm has EVERY Q equal to zero, so the across-
        # configuration variance is identically zero and z is formally -inf.
        # Clamping the denominator turns that into a meaningless -1e12; the
        # honest report is that the arm has no spread at all to compare with.
        if sem_q == 0.0:
            zq = float("-inf") if (q ** 2).mean() < q2_exact else float("inf")
        else:
            zq = float(((q ** 2).mean() - q2_exact) / sem_q)
        report["arms"][key] = {"z": zs, "z_q_squared": zq,
                               "relative_deviation": rel,
                               "relative_sem": rel_sem,
                               "q_squared": float((q ** 2).mean()),
                               "mean_abs_z": float(np.mean([abs(v) for v in zs.values()]))}
        print(f"{label:30s} " + " ".join(f"{zs[n]:+12.2f}" for n, _, _ in LOOPS)
              + f"{zq:+12.2f}")
    save_json(Path(args.out_dir) / f"honest_distributions_L{size}_beta{beta:g}.json", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
