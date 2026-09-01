"""Multi-case reverse-KL fine-tune -- the ESS-gap attempt with 08-01's lessons baked in.

Fixes for each failure mode of the single-case chain (see
out/u1_2d/ess_chain/chain_report.md):

  * single-case training wrecked other couplings (std 2202 at beta=218)
      -> train round-robin over cases spanning the deployed (L, beta) range;
  * eval-set selection noise (fixed 32 coarse configs, fixed seed)
      -> per-eval ROTATING disjoint slices of a large pre-generated coarse
         pool, rotating seeds; the save criterion is the MEAN ESS over all
         training cases, never a single lucky case;
  * beta-extrapolation damage went unmeasured until final verification
      -> an eval-only monitor case (32:218.58, outside the training set);
         saving is blocked while the monitor's log-w std exceeds 1.5x its
         initial value;
  * Tier-2's forward-KL objective degraded deployed ESS
      -> pure reverse KL from the ORIGINAL campaign checkpoint (not mlft),
         with the DSM anchor over all beta >= 10 rungs as the continuous-beta
         protector.

    .venv/Scripts/python.exe u1_2d/scripts/22_multicase_rkl.py --steps 300
"""

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path

import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import topological_charge
from u1_2d.model.likelihood import (
    _ess_from_log_weights, conditional_ode_sample, snis_log_weights,
)
from u1_2d.model.likelihood_train import reverse_kl_terms
from u1_2d.model.schedule import GeometricNoiseSchedule
from u1_2d.model.train import RungData, _prepare_rung, denoising_loss, load_checkpoint
from u1_2d.pipeline.ladder import conjugate_symmetrize
from u1_2d.utils import load_config, resolve_device, save_json, set_seed

_spec = importlib.util.spec_from_file_location(
    "likelihood_finetune", Path(__file__).parent / "20_likelihood_finetune.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
load_pairs = _mod.load_pairs


def make_coarse_pool(case, n_configs, action_type, device):
    fine_L, fine_beta = case
    coarse_L = fine_L // 2
    coarse_beta = approx_matched_coarse_beta(fine_beta)
    step_size, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
    pool, _ = run_hmc_ensemble(
        coarse_L, make_action(action_type, coarse_beta),
        n_configs=n_configs, n_chains=16, burn_in=burn_in, thin=5,
        n_steps=n_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=coarse_beta < 5,
    )
    return pool, coarse_beta


def eval_case(model, schedule, pool, case, coarse_beta, round_idx, n_eval, args,
              action_type, device):
    """Rotating slice of the pool, rotating seed -- no fixed eval set.

    Slices are disjoint within one sweep of the pool (floor(pool/n_eval)
    aligned windows); after a full sweep the rotation restarts from slice 0,
    so slices repeat across sweeps but never straddle two windows."""
    fine_L, fine_beta = case
    n_slices = max(pool.shape[0] // n_eval, 1)
    start = (round_idx % n_slices) * n_eval
    coarse_eval = pool[start : start + n_eval]
    model.eval()
    fine, log_q = conditional_ode_sample(
        model, schedule, coarse_eval, fine_beta,
        n_steps=args.eval_ode_steps, n_probes=args.n_probes,
        consistency_weight=args.consistency_weight,
        physics_blend_coef=args.physics_blend,
        physics_blend_beta_min=args.physics_blend_beta_min,
        batch_size=8, device=device, seed=args.seed + 1000 * round_idx,
    )
    model.train()
    log_w = snis_log_weights(fine, log_q, fine_beta, action_type,
                             coarse=coarse_eval, coarse_beta_matched=coarse_beta)
    ess, std, _ = _ess_from_log_weights(log_w)
    q = topological_charge(fine.float())
    return {"ess": ess, "log_w_std": std,
            "mean_Q": float(q.mean()), "mean_Q2": float((q**2).mean())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="u1_2d/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None,
                        help="default: the ORIGINAL campaign checkpoint from config")
    parser.add_argument("--out-checkpoint", default=None,
                        help="default: score_net_rkl2.pt next to the input checkpoint")
    parser.add_argument("--train-cases", nargs="+",
                        default=["16:14.1464", "16:55.0237", "32:55.0237"])
    parser.add_argument("--monitor-cases", nargs="+", default=["32:218.58"],
                        help="eval-only guard cases, never trained on; saves are "
                        "blocked while ANY monitor's log-w std exceeds the guard "
                        "factor times its initial value")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--batch-l16", type=int, default=4)
    parser.add_argument("--batch-l32", type=int, default=2)
    parser.add_argument("--ode-steps", type=int, default=24)
    parser.add_argument("--eval-ode-steps", type=int, default=60)
    parser.add_argument("--n-probes", type=int, default=1)
    parser.add_argument("--n-train-coarse", type=int, default=64)
    parser.add_argument("--n-eval", type=int, default=32,
                        help="eval configs per L=16 case (halved for L=32)")
    parser.add_argument("--eval-rotations", type=int, default=8,
                        help="pool holds this many disjoint eval slices")
    parser.add_argument("--dsm-weight", type=float, default=1.0)
    parser.add_argument("--dsm-batch", type=int, default=16)
    parser.add_argument("--beta-min", type=float, default=10.0)
    parser.add_argument("--configs-per-rung", type=int, default=48)
    parser.add_argument("--val-per-rung", type=int, default=8)
    parser.add_argument("--max-rungs", type=int, default=0)
    parser.add_argument("--eval-every", type=int, default=50)
    parser.add_argument("--monitor-guard", type=float, default=1.5,
                        help="block saves while monitor log-w std exceeds this "
                        "factor of its initial value")
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--consistency-weight", type=float, default=None)
    parser.add_argument("--physics-blend", type=float, default=None)
    parser.add_argument("--physics-blend-beta-min", type=float, default=None)
    parser.add_argument("--sigma-min-coef", type=float, default=0.03)
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    action_type = config["action_type"]
    ladder_cfg = config.get("ladder", {})
    if args.consistency_weight is None:
        args.consistency_weight = float(ladder_cfg.get("consistency_weight", 1.0))
    if args.physics_blend is None:
        args.physics_blend = float(ladder_cfg.get("physics_blend_coef", 0.0))
    if args.physics_blend_beta_min is None:
        args.physics_blend_beta_min = float(ladder_cfg.get("physics_blend_beta_min", 0.0))

    ckpt_path = args.checkpoint or config["train"]["checkpoint"]
    out_path = Path(args.out_checkpoint or (Path(ckpt_path).parent / "score_net_rkl2.pt"))
    model, schedule = load_checkpoint(ckpt_path, device)
    schedule = GeometricNoiseSchedule(
        schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=args.sigma_min_coef
    )
    model.train()

    def parse_case(spec):
        L, beta = spec.split(":")
        return (int(L), float(beta))

    train_cases = [parse_case(s) for s in args.train_cases]
    monitor_cases = [parse_case(s) for s in args.monitor_cases]

    pools, coarse_betas, n_evals = {}, {}, {}
    for case in train_cases + monitor_cases:
        n_ev = args.n_eval if case[0] <= 16 else args.n_eval // 2
        n_evals[case] = n_ev
        pool_n = args.n_train_coarse + n_ev * args.eval_rotations
        if case in monitor_cases:
            pool_n = n_ev * args.eval_rotations
        t0 = time.time()
        pool, cb = make_coarse_pool(case, pool_n, action_type, device)
        pools[case], coarse_betas[case] = pool, cb
        print(f"pool {case[0]}:{case[1]:g}: {pool.shape[0]} coarse @ beta_c={cb:.3f} "
              f"({time.time() - t0:.0f}s)", flush=True)

    dsm_data = []
    if args.dsm_weight > 0:
        train_pairs, _ = load_pairs(config, args, device)
        dsm_data = [
            _prepare_rung(RungData(r["name"], r["fine"], r["coarse"], r["beta"]),
                          device, getattr(model, "cond_channels", 4))
            for r in train_pairs
        ]

    actions = {c: make_action(action_type, c[1]) for c in train_cases}
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    gen = torch.Generator().manual_seed(args.seed)
    history = []

    def run_evals(round_idx):
        out = {}
        for case in train_cases:
            r = eval_case(model, schedule, pools[case][args.n_train_coarse:], case,
                          coarse_betas[case], round_idx, n_evals[case], args,
                          action_type, device)
            out[f"{case[0]}:{case[1]:g}"] = r
        out["monitors"] = {
            f"{c[0]}:{c[1]:g}": eval_case(
                model, schedule, pools[c], c, coarse_betas[c],
                round_idx, n_evals[c], args, action_type, device,
            )
            for c in monitor_cases
        }
        out["mean_train_ess"] = sum(
            out[f"{c[0]}:{c[1]:g}"]["ess"] for c in train_cases
        ) / len(train_cases)
        return out

    ev0 = run_evals(0)
    print(json.dumps({"step": 0, **ev0}), flush=True)
    best_mean_ess = ev0["mean_train_ess"]
    monitor_std_init = {k: max(v["log_w_std"], 1e-6) for k, v in ev0["monitors"].items()}
    round_idx = 1

    for step in range(1, args.steps + 1):
        t0 = time.time()
        case = train_cases[(step - 1) % len(train_cases)]
        batch_n = args.batch_l16 if case[0] <= 16 else args.batch_l32
        pool = pools[case][: args.n_train_coarse]
        idx = torch.randperm(pool.shape[0], generator=gen)[:batch_n]
        c_batch = conjugate_symmetrize(pool[idx], generator=gen)
        x0, log_q = reverse_kl_terms(
            model, schedule, c_batch, case[1],
            n_steps=args.ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            physics_blend_beta_min=args.physics_blend_beta_min,
            device=device,
        )
        n_dof = x0[0].numel()
        loss_rkl = (actions[case].per_config(x0) + log_q).mean() / n_dof

        loss = loss_rkl
        loss_dsm = None
        if dsm_data:
            d = dsm_data[int(torch.randint(len(dsm_data), (1,), generator=gen))]
            j = torch.randperm(d["fine"].shape[0], generator=gen)[: args.dsm_batch]
            loss_dsm = denoising_loss(model, d["fine"][j], d["cond"][j], d["beta"][j], schedule)
            loss = loss + args.dsm_weight * loss_dsm

        optimizer.zero_grad()
        loss.backward()
        if args.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
        optimizer.step()

        rec = {"step": step, "case": f"{case[0]}:{case[1]:g}",
               "loss_rkl_per_dof": float(loss_rkl),
               "loss_dsm": None if loss_dsm is None else float(loss_dsm),
               "seconds": round(time.time() - t0, 1)}
        if step % args.eval_every == 0 or step == args.steps:
            ev = run_evals(round_idx)
            round_idx += 1
            rec.update(ev)
            blocked = [k for k, v in ev["monitors"].items()
                       if v["log_w_std"] > args.monitor_guard * monitor_std_init[k]]
            guard_ok = not blocked
            if blocked:
                rec["monitor_guard_blocked"] = blocked
            if guard_ok and ev["mean_train_ess"] > best_mean_ess:
                best_mean_ess = ev["mean_train_ess"]
                payload = torch.load(ckpt_path, map_location="cpu", weights_only=True)
                payload["model_state"] = {k: v.detach().cpu().clone()
                                          for k, v in model.state_dict().items()}
                out_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(payload, out_path)
                rec["saved"] = str(out_path)
        history.append(rec)
        print(json.dumps(rec), flush=True)
        save_json(out_path.with_suffix(".history.json"), history)

    print(f"best mean train ESS/N: {best_mean_ess:.4f} (initial {ev0['mean_train_ess']:.4f})")
    print(f"checkpoint: {out_path}" if out_path.exists() else "never improved; no checkpoint saved")


if __name__ == "__main__":
    main()
