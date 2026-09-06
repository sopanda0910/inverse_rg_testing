"""How many retherm sweeps does a bootstrapped rung actually need?

`70_bootstrap_rung_poc.py` used a fixed `--final-retherm` count (10, then 15,
then 40 by hand) inherited from unrelated earlier scripts' choices at THEIR
couplings -- not measured for this chain. That is exactly the ad hoc
threshold this project's own standing rule warns against: `28_crossover_scan.py`
already replaced a fixed/discrete `t_therm` with a validated exponential
relaxation-time fit (`fit_joint_relaxation_time`) specifically because a
hardcoded count does not generalize across couplings. Retherm sweeps are the
same class of object -- a stochastic process relaxing an observable mean
toward a stationary target -- so this script reuses that SAME machinery with
sweep count standing in for trajectory count, rather than inventing a new
convergence rule.

Rebuilds the identical bootstrap chain (same seed/start/target as
`70_bootstrap_rung_poc.py`), then instead of a single fixed retherm count,
runs retherm ONE sweep at a time and records the per-configuration plaquette,
W(2x2) and W(4x4) means after every sweep, for a long horizon. Feeds that
series to `fit_joint_relaxation_time` for an actual tau_sweep with a
chain-resampling bootstrap error and chi2/dof, exactly as `t_therm` gets one.

    python u2_2d/scripts/71_bootstrap_retherm_relaxation.py --device cuda
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from importlib import import_module
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
scan = import_module("28_crossover_scan")

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import load_det_model, model_beta
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import configure_device, resolve_device, save_json, set_seed

LOOPS = [(1, 1), (2, 2), (4, 4)]
NAMES = ("plaquette", "wilson_2x2", "wilson_4x4")


def per_config_obs(links):
    out = {}
    for (nx, ny), name in zip(LOOPS, NAMES):
        v = (half_retr(plaquette(links)) if (nx, ny) == (1, 1)
             else half_retr(wilson_loop(links, nx, ny)))
        out[name] = v.mean(dim=(1, 2)).cpu().numpy().astype(float)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--checkpoint", default="out/u2_2d/checkpoints/det_score_net_wide_dense.pt")
    ap.add_argument("--start-size", type=int, default=8)
    ap.add_argument("--start-beta", type=float, default=15.0)
    ap.add_argument("--target-size", type=int, default=128)
    ap.add_argument("--n-configs", type=int, default=32)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--n-su2", type=int, default=30)
    ap.add_argument("--intermediate-retherm", type=int, default=10)
    ap.add_argument("--therm-sweeps", type=int, default=60)
    ap.add_argument("--therm-traj", type=int, default=300)
    ap.add_argument("--max-retherm-sweeps", type=int, default=150)
    ap.add_argument("--seed", type=int, default=9001)
    ap.add_argument("--out-dir", default="out/u2_2d/bootstrap_retherm_relaxation")
    args = ap.parse_args()

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    model, sched = load_det_model(args.checkpoint, device=device)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rungs = [(args.start_size, args.start_beta)]
    while rungs[-1][0] < args.target_size:
        L, b = rungs[-1]
        rungs.append((L * 2, topology_matched_fine_beta(b, L)))
    final_size, final_beta = rungs[-1]
    print("\nchain (identical to 70_bootstrap_rung_poc.py's default):")
    for L, b in rungs:
        print(f"  L={L:3d}  beta={b:12.4f}  model beta={model_beta(b):9.2f}")

    t0 = time.time()
    set_seed(args.seed)
    action0 = WilsonU2Action(args.start_beta)
    step_size, n_steps = adapted_hmc_params(args.start_beta)
    hmc = BatchedHMCU2(args.start_size, action0, n_chains=args.n_configs,
                       n_steps=n_steps, step_size=step_size, device=device,
                       topological_updates=True, winding_charge_step=1,
                       winding_interval=5)
    links = hmc.initialize(hot=False)
    links = retherm_sweeps(links, action0, args.therm_sweeps)
    for _ in range(args.therm_traj):
        links, _ = hmc.metropolis_step(links)
    print(f"  honest base built [{time.time()-t0:.0f}s]")

    for j in range(len(rungs) - 1):
        L, b = rungs[j]
        nb = rungs[j + 1][1]
        links = generate_fine_from_coarse(
            model, sched, links.cpu(), nb, n_su2_sweeps=args.n_su2,
            device=device, n_sampler_steps=args.sampler_steps,
            n_corrector_steps=1, batch_size=32, consistency_weight=1.0,
            physics_blend_coef=0.0).to(device)
        print(f"  lifted to L={L*2:3d} beta={nb:9.3f}")
        if j < len(rungs) - 2:
            links = retherm_sweeps(links, WilsonU2Action(nb), args.intermediate_retherm)

    # ---- sweep-by-sweep retherm at the final rung, recording every step ----
    final_action = WilsonU2Action(final_beta)
    series = {name: [] for name in NAMES}
    obs0 = per_config_obs(links)
    for name in NAMES:
        series[name].append(obs0[name])
    print(f"\n  sweep-by-sweep retherm at L={final_size} beta={final_beta:.2f} "
          f"(model beta {model_beta(final_beta):.1f}), recording up to "
          f"{args.max_retherm_sweeps} sweeps...")
    for s in range(1, args.max_retherm_sweeps + 1):
        links = retherm_sweeps(links, final_action, 1)
        obs = per_config_obs(links)
        for name in NAMES:
            series[name].append(obs[name])
        if s % 25 == 0:
            print(f"    sweep {s}: plaq mean = {obs['plaquette'].mean():.5f}")

    series_arr = {name: np.stack(series[name], axis=0) for name in NAMES}
    targets = {"plaquette": plaquette_exact(final_beta, final_size),
              "wilson_2x2": wilson_loop_exact(final_beta, 4),
              "wilson_4x4": wilson_loop_exact(final_beta, 16)}

    result = scan.fit_joint_relaxation_time(series_arr, targets, record_every=1,
                                            names=NAMES, n_boot=200, seed=args.seed)
    print(f"\n{'='*74}")
    print(f"RETHERM RELAXATION at L={final_size} beta={final_beta:.2f}:")
    print(f"  tau_sweep = {result['tau']:.2f} +- {result['tau_err']:.2f} sweeps  "
          f"(chi2/dof = {result['chi2_per_dof']:.2f})")
    recommended = int(math.ceil(5 * result["tau"])) if math.isfinite(result["tau"]) else None
    if recommended is not None:
        print(f"  recommended retherm budget (5x tau): {recommended} sweeps")
    else:
        print("  tau did not resolve -- see raw series; do not pick a sweep count from this fit")

    # final z at a few candidate sweep counts, read directly off the recorded series
    print(f"\n  z at fixed sweep counts (for comparison against the earlier ad hoc choices):")
    for k in (10, 15, 40, 80, args.max_retherm_sweeps):
        if k >= series_arr["plaquette"].shape[0]:
            continue
        for name in NAMES:
            v = series_arr[name][k]
            sem = v.std(ddof=1) / math.sqrt(len(v))
            z = (v.mean() - targets[name]) / max(sem, 1e-30)
            print(f"    sweep {k:4d}  {name:12s}  z = {z:+7.2f}")

    save_json(out / "retherm_relaxation.json", {
        "chain": [{"lattice_size": L, "beta": b, "model_beta": model_beta(b)} for L, b in rungs],
        "final_size": final_size, "final_beta": final_beta,
        "tau_sweep": result["tau"], "tau_sweep_err": result["tau_err"],
        "chi2_per_dof": result["chi2_per_dof"], "n_dof": result.get("n_dof"),
        "targets": targets, "max_retherm_sweeps": args.max_retherm_sweeps,
        "n_configs": args.n_configs,
    })
    print(f"\nwrote {out / 'retherm_relaxation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
