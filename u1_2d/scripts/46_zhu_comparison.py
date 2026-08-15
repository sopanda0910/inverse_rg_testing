"""Head-to-head against Zhu, Aarts, Wang, Zhou & Wang (arXiv:2410.19602) on their case.

Their setup: 2D U(1), L = 16 fixed, a U-Net score model trained at beta = 1 on
30,720 HMC configurations (x5 by gauge augmentation), then *extrapolated* in
the coupling by rescaling the learned score, s -> (beta/beta_0) s, which they
call physics conditioning. At beta = 7 they generate 1,024 configurations and
report that HMC "suffers from topological freezing, only sampling values of Q
at or around 0", while their model "is able to explore a wider range of
topological sectors, yielding a larger topological susceptibility".

The wider Q distribution is presented as the desirable outcome. Whether it is
correct was left open in that paper -- explicitly: "We are currently comparing
the numerically computed distribution with the analytical prediction, which is
possible in this simple theory." This project has that analytical prediction
(u1_2d.lgt.exact) and the machinery to test against it, so this script closes
that loop and puts our pipeline on the same case.

Three arms at L = 16, beta = 7:

  exact       the analytic finite-volume P(Q) -- the reference neither of us
              had when the respective claims were made
  hmc         plain periodic HMC, no topological moves -- their frozen arm
  inverse-rg  this project's pipeline, conditioned on an L = 8 coarse ensemble
              at the matched coupling, with sector transport

Caveat stated up front: our model is trained for 16 -> 32 and is used here at
8 -> 16, one rung below its training range. The architecture is convolutional
so this runs, but the arm is an out-of-range use of our checkpoint and is
labelled as such. The `exact` and `hmc` arms carry no such caveat, and the
comparison that matters most -- is a wider Q distribution automatically better?
-- rests on those two.

    .venv/Scripts/python.exe u1_2d/scripts/46_zhu_comparison.py --n-configs 1024
"""

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt import exact, make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import mean_plaquette, topological_charge
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import generate_fine_from_coarse
from u1_2d.utils import load_config, resolve_device, save_json, set_seed

REPO = Path(__file__).resolve().parents[2]


def _load_18():
    spec = importlib.util.spec_from_file_location(
        "pq18", REPO / "u1_2d" / "scripts" / "18_pq_hmc_tail.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def summarize(q: np.ndarray, plaq: float, q_values, probs, chi2_p,
              exact_q2: float, label: str) -> dict:
    q = np.asarray(q, dtype=float)
    n = len(q)
    q2 = float((q ** 2).mean())
    sem = float((q ** 2).std()) / math.sqrt(max(n, 1))
    hist = {int(v): float((np.round(q) == v).mean()) for v in range(-4, 5)}
    keep = probs * n > 2.0
    return {
        "arm": label, "n": n,
        "q2": q2, "q2_sem": sem, "exact_q2": exact_q2,
        "q2_over_exact": q2 / exact_q2 if exact_q2 else float("nan"),
        "z_q2": (q2 - exact_q2) / sem if sem > 0 else float("nan"),
        "plaquette": plaq,
        "hist": hist,
        "chi2_p": chi2_p(q, q_values, probs),
        "testable_bins": int(keep.sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--fine-L", type=int, default=16)
    ap.add_argument("--betas", nargs="+", type=float, default=[7.0],
                    help="their extrapolation target; 1.0 is their training point")
    ap.add_argument("--n-configs", type=int, default=1024)
    ap.add_argument("--hmc-burn-in", type=int, default=2000)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--skip-model", action="store_true",
                    help="exact + HMC arms only (no checkpoint needed)")
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u1_2d/zhu_comparison")
    args = ap.parse_args()

    m18 = _load_18()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    action_type = config["action_type"]
    set_seed(args.seed)
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    model = schedule = None
    if not args.skip_model:
        model, schedule = load_checkpoint(
            args.checkpoint or config["train"]["checkpoint"], device)
    ladder_cfg = config.get("ladder", {})
    results = []

    for beta in args.betas:
        L = args.fine_L
        q_values, probs = exact.topological_charge_distribution(beta, L, action_type)
        exact_q2 = float((q_values.astype(float) ** 2 * probs).sum())
        exact_plaq = exact.plaquette_exact(beta, action_type, L)
        print(f"\n=== L={L} beta={beta:g} ===", flush=True)
        print(f"  exact <Q^2> = {exact_q2:.4f}   chi_Q = {exact_q2 / (L * L):.5f}"
              f"   P(0) = {float(probs[list(q_values).index(0)]):.4f}", flush=True)

        arms = []
        # -- their frozen arm: plain periodic HMC, no topological updates
        step, n_steps = adapted_hmc_params(beta, 0.2, 5)
        t0 = time.time()
        cfgs, _ = run_hmc_ensemble(
            L, make_action(action_type, beta), n_configs=args.n_configs,
            n_chains=32, burn_in=args.hmc_burn_in, thin=5, n_steps=n_steps,
            step_size=step, device=device, topological_updates=False,
            hot_start=False)
        cfgs = cfgs.cpu()
        arms.append(summarize(topological_charge(cfgs).numpy(),
                              float(mean_plaquette(cfgs).mean()),
                              q_values, probs, m18.chi2_p, exact_q2,
                              "hmc (no topological moves)"))
        print(f"  hmc done ({time.time() - t0:.0f}s)", flush=True)

        # -- this project's pipeline on the same target
        if model is not None:
            coarse_beta = approx_matched_coarse_beta(beta)
            cstep, cn = adapted_hmc_params(coarse_beta, 0.2, 5)
            t0 = time.time()
            coarse, _ = run_hmc_ensemble(
                L // 2, make_action(action_type, coarse_beta),
                n_configs=args.n_configs, n_chains=32, burn_in=600, thin=5,
                n_steps=cn, step_size=cstep, device=device,
                topological_updates=True, hot_start=coarse_beta < 5)
            fine = generate_fine_from_coarse(
                model, schedule, coarse.cpu(), beta,
                n_sampler_steps=int(ladder_cfg.get("n_sampler_steps", 200)),
                n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
                batch_size=args.batch_size, device=device,
                consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
                enforce_coarse_charge=True,
                charge_projection_sigma=float(
                    ladder_cfg.get("charge_projection_sigma", 0.5)),
                physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
                physics_blend_beta_min=float(
                    ladder_cfg.get("physics_blend_beta_min", 0.0)),
            ).cpu()
            arms.append(summarize(topological_charge(fine).numpy(),
                                  float(mean_plaquette(fine).mean()),
                                  q_values, probs, m18.chi2_p, exact_q2,
                                  f"inverse-rg ({L // 2}->{L}, out of trained range)"))
            print(f"  inverse-rg done ({time.time() - t0:.0f}s)", flush=True)

        results.append({
            "L": L, "beta": beta, "exact_q2": exact_q2,
            "exact_chi_Q": exact_q2 / (L * L),
            "exact_plaquette": exact_plaq,
            "exact_hist": {int(v): float(p) for v, p in zip(q_values, probs)
                           if -4 <= int(v) <= 4},
            "arms": arms,
        })
        save_json(out_dir / "zhu_comparison.json", results)

    print("\n| L | beta | arm | <Q^2> | /exact | z | chi2 p | bins | plaquette |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['L']} | {r['beta']:g} | **exact** | {r['exact_q2']:.4f} | 1.00 "
              f"| -- | -- | -- | {r['exact_plaquette']:.5f} |")
        for a in r["arms"]:
            p = "not testable" if a["chi2_p"] is None else f"{a['chi2_p']:.3g}"
            print(f"| {r['L']} | {r['beta']:g} | {a['arm']} | {a['q2']:.4f} | "
                  f"{a['q2_over_exact']:.2f} | {a['z_q2']:+.1f} | {p} | "
                  f"{a['testable_bins']} | {a['plaquette']:.5f} |")

    print("\nP(Q) by sector (exact vs arms):")
    for r in results:
        print(f"  L={r['L']} beta={r['beta']:g}")
        qs = sorted(int(k) for k in r["exact_hist"])
        print("    Q       " + "".join(f"{q:>8d}" for q in qs))
        print("    exact   " + "".join(f"{r['exact_hist'][q]:>8.4f}" for q in qs))
        for a in r["arms"]:
            print(f"    {a['arm'][:7]:7s} " +
                  "".join(f"{a['hist'].get(q, 0.0):>8.4f}" for q in qs))
    print(f"\nwrote {(out_dir / 'zhu_comparison.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
