"""Proof of concept: can training-rung coverage itself be extended WITHOUT
running classical HMC at the target coupling at all?

Every high-beta training rung generated so far in this project -- including
the ones `sector_augment`/`seed_exact_sectors` repair -- still starts from a
classical HMC chain run AT the target beta (then patched). That HMC run is
where the earlier frozen-rung bug came from (honest sampling at beta=536.6
came back stuck at Q=0), and it is also the part of the pipeline whose cost
does not shrink as beta grows -- adapted_hmc_params gives it smaller step
sizes and thermalize_sweeps/burn_in stay fixed, so it is strictly harder to
even LAUNCH a classical chain as beta increases, freezing risk aside.

This script tests the alternative: build the coarse-to-fine training PAIR
the same way `45_multi_lift_compounding.py` already builds an inference
seed -- chain diffusion lifts from an HONEST, unfrozen low-beta base via
`topology_matched_fine_beta` (Q transported exactly, never touching a
classical sampler anywhere near the target coupling), rethermalize locally
(cheap, exact, local -- no topological barrier), and write the result in
EXACTLY the ensemble format `01_generate_data.py` produces, so it can be
appended to a training config's `rungs:` list like any other.

This is the untested half of the reach argument: exact transport + a
translation-equivariant net gets volume generalization essentially for
free once coupling is covered (already measured); this script asks whether
coupling coverage ITSELF can be extended past what classical simulation can
reach at all, using nothing but the model + exact local machinery. If the
bootstrapped rung's own local structure is trustworthy (z-scores near the
closed form after retherm, like every other tested endpoint), coverage is
not fundamentally bounded by what classical HMC can sample -- only by
compute spent on cheap low-beta chains and diffusion sampling, both of
which stay easy at any target coupling.

    python u2_2d/scripts/70_bootstrap_rung_poc.py --device cuda \
        --checkpoint out/u2_2d/checkpoints/det_score_net_wide_dense.pt \
        --target-size 16 --target-beta 3000 --out-dir out/u2_2d/data_bootstrap_poc
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import (det_topological_susceptibility, plaquette_exact,
                             wilson_loop_exact)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import load_det_model, model_beta
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, resolve_device, save_ensemble,
                         save_json, set_seed)


def score(links, beta, size):
    out = {}
    with torch.no_grad():
        for nx, ny in [(1, 1), (2, 2), (4, 4)]:
            v = (half_retr(plaquette(links)) if (nx, ny) == (1, 1)
                 else half_retr(wilson_loop(links, nx, ny)))
            v = v.mean(dim=(1, 2)).cpu().numpy().astype(float)
            exact = (plaquette_exact(beta, size) if (nx, ny) == (1, 1)
                     else wilson_loop_exact(beta, nx * ny))
            sem = v.std(ddof=1) / math.sqrt(len(v))
            out[f"z_W{nx}x{ny}"] = float((v.mean() - exact) / max(sem, 1e-30))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--checkpoint", default="out/u2_2d/checkpoints/det_score_net_wide_dense.pt")
    ap.add_argument("--start-size", type=int, default=8)
    ap.add_argument("--start-beta", type=float, default=6.4002)
    ap.add_argument("--target-size", type=int, default=16)
    ap.add_argument("--n-configs", type=int, default=256)
    ap.add_argument("--sampler-steps", type=int, default=200)
    ap.add_argument("--n-su2", type=int, default=30)
    ap.add_argument("--intermediate-retherm", type=int, default=10)
    ap.add_argument("--final-retherm", type=int, default=15)
    ap.add_argument("--therm-sweeps", type=int, default=60)
    ap.add_argument("--therm-traj", type=int, default=300)
    ap.add_argument("--seed", type=int, default=9001)
    ap.add_argument("--out-dir", default="out/u2_2d/data_bootstrap_poc")
    args = ap.parse_args()

    device = resolve_device({"device": args.device})
    print(configure_device(device))
    model, sched = load_det_model(args.checkpoint, device=device)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # ---- build the chain up to target_size via the SAME exact ladder
    # relation the deployed ladder uses, starting from an honestly-sampled,
    # genuinely unfrozen low-beta base -- no classical HMC anywhere near the
    # target coupling. ---------------------------------------------------
    rungs = [(args.start_size, args.start_beta)]
    while rungs[-1][0] < args.target_size:
        L, b = rungs[-1]
        rungs.append((L * 2, topology_matched_fine_beta(b, L)))
    final_size, final_beta = rungs[-1]
    print("\nbootstrap chain (no classical HMC past the base):")
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
    q_start = topological_charge(links).round().cpu().numpy()
    print(f"  honest base built [{time.time()-t0:.0f}s], <Q^2> at base = "
          f"{float((q_start**2).mean()):.4f}")

    for j in range(len(rungs) - 1):
        L, b = rungs[j]
        nb = rungs[j + 1][1]
        ns = L * 2
        links = generate_fine_from_coarse(
            model, sched, links.cpu(), nb, n_su2_sweeps=args.n_su2,
            device=device, n_sampler_steps=args.sampler_steps,
            n_corrector_steps=1, batch_size=32, consistency_weight=1.0,
            physics_blend_coef=0.0).to(device)
        raw = score(links, nb, ns)
        print(f"  lifted to L={ns:3d} beta={nb:9.3f}  raw z(plaq)={raw['z_W1x1']:+7.2f}")
        if j < len(rungs) - 2:
            links = retherm_sweeps(links, WilsonU2Action(nb), args.intermediate_retherm)

    # final rung: this IS the training data being manufactured
    final_action = WilsonU2Action(final_beta)
    raw_score = score(links, final_beta, final_size)
    links = retherm_sweeps(links, final_action, args.final_retherm)
    post_score = score(links, final_beta, final_size)
    q_end = topological_charge(links).round().cpu().numpy()
    match = float((q_end == q_start).mean())

    plaq = float(half_retr(plaquette(links)).mean())
    qsq = float(topological_charge(links).square().mean())
    qsq_exact = det_topological_susceptibility(final_beta, final_size) * final_size ** 2

    metadata = {
        "beta": final_beta,
        "lattice_size": final_size,
        "n_configs": int(links.shape[0]),
        "n_chains": int(links.shape[0]),
        "source": "bootstrap: diffusion lift chain from honest low-beta base "
                  "+ local retherm -- NO classical HMC at this beta",
        "chain": [{"lattice_size": L, "beta": b, "model_beta": model_beta(b)}
                 for L, b in rungs],
        "checkpoint": args.checkpoint,
        "plaquette": plaq,
        "plaquette_exact": plaquette_exact(final_beta, final_size),
        "q_squared": qsq,
        "q_squared_exact": qsq_exact,
        "charge_match_to_honest_base_fraction": match,
        "raw_z_before_retherm": raw_score,
        "post_z_after_retherm": post_score,
        "final_retherm_sweeps": args.final_retherm,
        "seconds": time.time() - t0,
    }
    save_ensemble(out / f"u2_L{final_size}_beta{final_beta:g}.pt", links.cpu(), metadata)
    save_json(out / "summary.json", [metadata])

    print(f"\n{'='*74}")
    print(f"BOOTSTRAPPED RUNG: L={final_size} beta={final_beta:.2f} "
          f"(model beta {model_beta(final_beta):.1f})")
    print(f"  plaquette: {plaq:.5f}  (exact {metadata['plaquette_exact']:.5f})")
    print(f"  <Q^2>: {qsq:.4f}  (exact {qsq_exact:.4f})")
    print(f"  raw  z(plaq/W2x2/W4x4) = {raw_score['z_W1x1']:+.2f} / "
          f"{raw_score['z_W2x2']:+.2f} / {raw_score['z_W4x4']:+.2f}")
    print(f"  post z(plaq/W2x2/W4x4) = {post_score['z_W1x1']:+.2f} / "
          f"{post_score['z_W2x2']:+.2f} / {post_score['z_W4x4']:+.2f}")
    print(f"  charge match to honest base's transported Q: {100*match:.1f}%")
    if abs(post_score["z_W1x1"]) < 3.0:
        print("  VERDICT: locally trustworthy -- usable as a training rung "
              "without ever running classical HMC at this coupling.")
    else:
        print("  VERDICT: NOT yet trustworthy at this coupling/chain length -- "
              "do not use as training data without investigation.")
    print(f"\nwrote {out / f'u2_L{final_size}_beta{final_beta:g}.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
