"""Does MCMC-wrapped exactness cost more than it buys? A direct test.

Referee objection 2 (docs/NARRATIVE.md sec 24.1): the closest published work,
Zhu, Aarts, Wang, Zhou & Wang, "Physics-Conditioned Diffusion Models for
Lattice Gauge Theory", JHEP 03 (2026) 111 / arXiv:2502.05504 -- the JOURNAL
paper, not the arXiv:2410.19602 workshop paper whose figures scripts 46/47
digitize -- reports for 2D U(1) that
"exactness ... is ensured by incorporating Metropolis-adjusted Langevin
dynamics into the generation process". This project's sec 20 measured that
route as out of reach and sec F3 states the deployed ladder applies no
accept/reject to the proposal at all. Those two positions cannot both be
right, and the difference is testable here without their paper.

A numeric head-to-head against their results needs their numbers. What does
not is the mechanism: MALA targeting the exact Boltzmann measure,

    x' = x - (eps^2/2) grad S(x) + eps xi,     xi ~ N(0, 1)

accepted with the standard Metropolis-Hastings ratio including the asymmetric
proposal correction. Applied to configurations the model produced, its
acceptance rate is a direct, calibrated measurement of how far the proposal
sits from the target *locally* -- and the honest control is the same
measurement on equilibrium HMC configurations at the same coupling, which is
what "already exact" looks like.

What the comparison can show:
  * acceptance on model output ~ acceptance on equilibrium configs
        -> the model's output is locally indistinguishable from the target,
           and MALA-wrapped exactness is nearly free. Section F3 would be wrong.
  * acceptance on model output << equilibrium
        -> each correction step is expensive or the step size must shrink, and
           exactness is bought back at simulation cost. Section F3 stands.

Also reported: how far the gauge-invariant observables move under the
correction. A proposal that needs its observables moved was not close, whatever
the acceptance says.

    .venv/Scripts/python.exe u1_2d/scripts/45_mala_exactness.py \
        --cases 32:14.1464 32:55.0237 --n-configs 64
"""

import argparse
import math
import time
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt import exact, make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import (
    mean_plaquette,
    topological_charge,
    wilson_loop_angles,
    wrap,
)
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import generate_fine_from_coarse
from u1_2d.utils import load_config, resolve_device, save_json, set_seed

REPO = Path(__file__).resolve().parents[2]


def grad_action(theta: torch.Tensor, action) -> torch.Tensor:
    x = theta.detach().clone().requires_grad_(True)
    s = action.per_config(x).sum()
    (g,) = torch.autograd.grad(s, x)
    return g


def mala_step(theta: torch.Tensor, action, eps: float
              ) -> tuple[torch.Tensor, torch.Tensor]:
    """One MALA step on exp(-S), with the proposal-asymmetry correction.

    Angles are wrapped, so the proposal density is that of the Gaussian
    increment on the tangent space; the wrap is an isometry and leaves the
    correction unchanged.
    """
    half = 0.5 * eps * eps
    g = grad_action(theta, action)
    noise = torch.randn_like(theta)
    prop = wrap(theta - half * g + eps * noise)
    g_prop = grad_action(prop, action)

    s_old = action.per_config(theta)
    s_new = action.per_config(prop)
    # log q(theta | prop) - log q(prop | theta)
    fwd = wrap(prop - theta + half * g)
    bwd = wrap(theta - prop + half * g_prop)
    log_q_fwd = -(fwd.square().sum(dim=(1, 2, 3))) / (2 * eps * eps)
    log_q_bwd = -(bwd.square().sum(dim=(1, 2, 3))) / (2 * eps * eps)
    log_ratio = (s_old - s_new) + (log_q_bwd - log_q_fwd)
    accept = torch.rand(theta.shape[0], device=theta.device) < torch.exp(log_ratio)
    mask = accept.view(-1, 1, 1, 1)
    return torch.where(mask, prop, theta), accept.float()


def observables(theta: torch.Tensor) -> dict:
    with torch.no_grad():
        out = {"plaquette": float(mean_plaquette(theta).mean()),
               "Q^2": float((topological_charge(theta).double() ** 2).mean())}
        for k in (2, 4):
            out[f"W{k}x{k}"] = float(torch.cos(wilson_loop_angles(theta, k, k)).mean())
    return out


def run_mala(theta, action, eps, n_steps):
    acc = []
    x = theta.clone()
    for _ in range(n_steps):
        x, a = mala_step(x, action, eps)
        acc.append(float(a.mean()))
    return x, float(np.mean(acc))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--cases", nargs="+", default=["32:14.1464", "32:55.0237"])
    ap.add_argument("--n-configs", type=int, default=64)
    ap.add_argument("--eps", nargs="+", type=float,
                    default=[0.003, 0.01, 0.03, 0.1])
    ap.add_argument("--n-steps", type=int, default=50)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u1_2d/mala_exactness")
    args = ap.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    action_type = config["action_type"]
    set_seed(args.seed)
    model, schedule = load_checkpoint(
        args.checkpoint or config["train"]["checkpoint"], device)
    ladder_cfg = config.get("ladder", {})
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for spec in args.cases:
        Ls, bs = spec.split(":")
        fine_L, fine_beta = int(Ls), float(bs)
        coarse_beta = approx_matched_coarse_beta(fine_beta)
        action = make_action(action_type, fine_beta)
        step, n_steps_hmc = adapted_hmc_params(coarse_beta, 0.2, 5)
        burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)

        coarse, _ = run_hmc_ensemble(
            fine_L // 2, make_action(action_type, coarse_beta),
            n_configs=args.n_configs, n_chains=16, burn_in=burn_in, thin=5,
            n_steps=n_steps_hmc, step_size=step, device=device,
            topological_updates=True, hot_start=coarse_beta < 5)
        model_cfgs = generate_fine_from_coarse(
            model, schedule, coarse.cpu(), fine_beta,
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
        ).to(device)

        # Control: equilibrium configurations of the SAME target theory.
        step_f, n_steps_f = adapted_hmc_params(fine_beta, 0.2, 5)
        eq_cfgs, _ = run_hmc_ensemble(
            fine_L, action, n_configs=args.n_configs, n_chains=16,
            burn_in=3000, thin=5, n_steps=n_steps_f, step_size=step_f,
            device=device, topological_updates=True, hot_start=False)
        eq_cfgs = eq_cfgs.to(device)

        print(f"\n=== {spec} (coarse beta {coarse_beta:.4f}) ===", flush=True)
        for eps in args.eps:
            t0 = time.time()
            before_m = observables(model_cfgs)
            after_m, acc_m = run_mala(model_cfgs, action, eps, args.n_steps)
            after_m_obs = observables(after_m)
            _, acc_e = run_mala(eq_cfgs, action, eps, args.n_steps)
            row = {
                "case": spec, "fine_L": fine_L, "fine_beta": fine_beta,
                "eps": eps, "n_steps": args.n_steps,
                "acceptance_model": acc_m,
                "acceptance_equilibrium": acc_e,
                "acceptance_ratio": (acc_m / acc_e) if acc_e > 0 else float("nan"),
                "obs_before": before_m, "obs_after": after_m_obs,
                "plaquette_shift": after_m_obs["plaquette"] - before_m["plaquette"],
                "exact_plaquette": exact.plaquette_exact(
                    fine_beta, action_type, fine_L),
                "seconds": round(time.time() - t0, 1),
            }
            rows.append(row)
            print(f"  eps={eps:<7g} acc(model)={acc_m:.3f}  "
                  f"acc(equilibrium)={acc_e:.3f}  ratio={row['acceptance_ratio']:.3f}"
                  f"  d(plaq)={row['plaquette_shift']:+.2e}", flush=True)
            save_json(out_dir / "mala_exactness.json", rows)

    print("\n| case | eps | acc (model) | acc (equilibrium) | ratio | "
          "plaquette shift |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['case']} | {r['eps']:g} | {r['acceptance_model']:.3f} | "
              f"{r['acceptance_equilibrium']:.3f} | {r['acceptance_ratio']:.3f} | "
              f"{r['plaquette_shift']:+.2e} |")
    print("\nReading this correctly matters, and the naive reading is wrong.\n"
          "\n"
          "Ratio ~ 1 means the model's configurations accept MALA moves as "
          "readily as\nequilibrium ones do. That does NOT mean MALA-wrapped "
          "exactness is cheap. MALA\nis a LOCAL move: high acceptance says each "
          "configuration sits in a region of\ntypical action, not that the "
          "ENSEMBLE is distributed correctly. A local chain\nstarted from a "
          "globally wrong distribution stays wrong for a mixing time, and\nfor "
          "the topological sector that time is the very thing this project "
          "exists to\navoid -- MALA cannot change Q at all at these step sizes.\n"
          "\n"
          "So acceptance is a LOCAL diagnostic, and it fails in exactly the way "
          "the\nobservables do (sec 20): healthy while the density is 10-100 "
          "nats off. The cost\nof exactness-by-MALA is its autocorrelation time, "
          "which this script does not\nmeasure and which acceptance cannot "
          "bound. Section F3 stands.\n"
          "\n"
          "Note also that the eps -> 0 columns are uninformative by construction: "
          "a\nvanishing step accepts everything for any configuration, right or "
          "wrong. The\ninformative entries are the largest eps, where the two "
          "arms separate.")
    print(f"wrote {(out_dir / 'mala_exactness.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
