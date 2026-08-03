"""Tier 3: reverse-KL fine-tune -- directly maximize the deployed proposal's ESS.

Minimizes E_q[S_f(x) + log q(x|c)] / n_dof = KL(q || p)/n_dof + const by
sampling the flow differentiably (reparameterized through the deterministic
ODE) conditioned on HMC coarse configs at the matched coupling. Needs no fine
data at the target coupling; this is the objective whose optimum is ESS/N = 1.

Guardrails (reverse KL is mode-seeking; the known failure is collapsing onto
few topological sectors, the exact pathology this project exists to avoid):
  * charge-conjugation symmetrization of the coarse batch every step,
  * DSM anchor on existing high-beta data pairs (dsm_weight),
  * P(Q) monitor at every eval: mean Q, <Q^2>, and a sector-collapse warning
    when <Q^2> drops below half its initial value or |<Q>| exceeds
    2 sqrt(<Q^2>/n). History records everything; abort judgment is yours.

Run AFTER Tier 2: warm-starting reverse KL from an ML-improved proposal is
both more stable and faster. Output defaults to score_net_rklft.pt.

    .venv/Scripts/python.exe diffusion_v2/scripts/21_reverse_kl_finetune.py \
        --config diffusion_v2/configs/v2.yaml --checkpoint <mlft ckpt> --case 16:55.0237
"""

import argparse
import math
import time
from pathlib import Path

import torch

from diffusion_v2.lgt import make_action, run_hmc_ensemble
from diffusion_v2.lgt.blocking import approx_matched_coarse_beta
from diffusion_v2.lgt.hmc import adapted_hmc_params
from diffusion_v2.lgt.lattice import topological_charge
from diffusion_v2.model.likelihood import conditional_ode_sample, snis_log_weights, _ess_from_log_weights
from diffusion_v2.model.likelihood_train import reverse_kl_terms
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.train import denoising_loss, load_checkpoint, _prepare_rung, RungData
from diffusion_v2.pipeline.ladder import conjugate_symmetrize
from diffusion_v2.utils import load_config, resolve_device, save_json, set_seed

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location(
    "likelihood_finetune", Path(__file__).parent / "20_likelihood_finetune.py"
)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
load_pairs = _mod.load_pairs


def eval_proposal(model, schedule, coarse_eval, fine_beta, coarse_beta, args, action_type, device):
    """No-grad ESS + topology snapshot of the current proposal."""
    model.eval()
    fine, log_q = conditional_ode_sample(
        model, schedule, coarse_eval, fine_beta,
        n_steps=args.eval_ode_steps, n_probes=args.n_probes,
        consistency_weight=args.consistency_weight,
        physics_blend_coef=args.physics_blend,
        physics_blend_beta_min=args.physics_blend_beta_min,
        batch_size=args.batch * 2, device=device, seed=args.seed,
    )
    model.train()
    log_w = snis_log_weights(fine, log_q, fine_beta, action_type,
                             coarse=coarse_eval, coarse_beta_matched=coarse_beta)
    ess, std, _ = _ess_from_log_weights(log_w)
    q = topological_charge(fine.float())
    return {"ess_per_n": ess, "log_w_std": std,
            "mean_Q": float(q.mean()), "mean_Q2": float((q**2).mean())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default=None,
                        help="warm start; use the Tier-2 (mlft) checkpoint when available")
    parser.add_argument("--out-checkpoint", default=None,
                        help="default: score_net_rklft.pt next to the input checkpoint")
    parser.add_argument("--case", default="16:55.0237", help="fine_L:fine_beta target")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--ode-steps", type=int, default=24)
    parser.add_argument("--eval-ode-steps", type=int, default=60)
    parser.add_argument("--n-probes", type=int, default=1)
    parser.add_argument("--n-coarse", type=int, default=64)
    parser.add_argument("--n-coarse-eval", type=int, default=32)
    parser.add_argument("--dsm-weight", type=float, default=1.0)
    parser.add_argument("--dsm-batch", type=int, default=16)
    parser.add_argument("--beta-min", type=float, default=10.0)
    parser.add_argument("--configs-per-rung", type=int, default=48)
    parser.add_argument("--val-per-rung", type=int, default=8)
    parser.add_argument("--max-rungs", type=int, default=0,
                        help="cap number of DSM-anchor rungs loaded (0 = all)")
    parser.add_argument("--eval-every", type=int, default=20)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--consistency-weight", type=float, default=None)
    parser.add_argument("--physics-blend", type=float, default=None)
    parser.add_argument("--physics-blend-beta-min", type=float, default=None)
    parser.add_argument("--sigma-min-coef", type=float, default=None)
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
    out_path = Path(args.out_checkpoint or (Path(ckpt_path).parent / "score_net_rklft.pt"))
    model, schedule = load_checkpoint(ckpt_path, device)
    coef = (args.sigma_min_coef if args.sigma_min_coef is not None
            else ladder_cfg.get("sigma_min_beta_coef"))
    if coef is not None:
        schedule = GeometricNoiseSchedule(
            schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=float(coef)
        )
    model.train()

    L_str, beta_str = args.case.split(":")
    fine_L, fine_beta = int(L_str), float(beta_str)
    coarse_L = fine_L // 2
    coarse_beta = approx_matched_coarse_beta(fine_beta)
    step_size, n_hmc_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
    print(f"coarse base: L={coarse_L} beta={coarse_beta:.4f} x {args.n_coarse + args.n_coarse_eval}")
    coarse_all, _ = run_hmc_ensemble(
        coarse_L, make_action(action_type, coarse_beta),
        n_configs=args.n_coarse + args.n_coarse_eval, n_chains=16, burn_in=burn_in,
        thin=5, n_steps=n_hmc_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=coarse_beta < 5,
    )
    coarse_train, coarse_eval = coarse_all[: args.n_coarse], coarse_all[args.n_coarse:]

    dsm_data = []
    if args.dsm_weight > 0:
        train_pairs, _ = load_pairs(config, args, device)
        dsm_data = [
            _prepare_rung(RungData(r["name"], r["fine"], r["coarse"], r["beta"]),
                          device, getattr(model, "cond_channels", 4))
            for r in train_pairs
        ]

    action = make_action(action_type, fine_beta)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    gen = torch.Generator().manual_seed(args.seed)
    history = []
    ev0 = eval_proposal(model, schedule, coarse_eval, fine_beta, coarse_beta,
                        args, action_type, device)
    print({"step": 0, **ev0})
    best_ess, q2_init = ev0["ess_per_n"], max(ev0["mean_Q2"], 1e-6)

    for step in range(1, args.steps + 1):
        t0 = time.time()
        idx = torch.randperm(coarse_train.shape[0], generator=gen)[: args.batch]
        c_batch = conjugate_symmetrize(coarse_train[idx], generator=gen)
        x0, log_q = reverse_kl_terms(
            model, schedule, c_batch, fine_beta,
            n_steps=args.ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            physics_blend_beta_min=args.physics_blend_beta_min,
            device=device,
        )
        n_dof = x0[0].numel()
        loss_rkl = (action.per_config(x0) + log_q).mean() / n_dof

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

        rec = {"step": step, "loss_rkl_per_dof": float(loss_rkl),
               "loss_dsm": None if loss_dsm is None else float(loss_dsm),
               "seconds": round(time.time() - t0, 1)}
        if step % args.eval_every == 0 or step == args.steps:
            ev = eval_proposal(model, schedule, coarse_eval, fine_beta, coarse_beta,
                               args, action_type, device)
            rec.update(ev)
            n_ev = args.n_coarse_eval
            if ev["mean_Q2"] < 0.5 * q2_init or abs(ev["mean_Q"]) > 2.0 * (ev["mean_Q2"] / n_ev) ** 0.5:
                rec["sector_collapse_warning"] = True
            if ev["ess_per_n"] > best_ess:
                best_ess = ev["ess_per_n"]
                payload = torch.load(ckpt_path, map_location="cpu", weights_only=True)
                payload["model_state"] = {k: v.detach().cpu().clone()
                                          for k, v in model.state_dict().items()}
                out_path.parent.mkdir(parents=True, exist_ok=True)
                torch.save(payload, out_path)
                rec["saved"] = str(out_path)
        history.append(rec)
        print(rec, flush=True)
        save_json(out_path.with_suffix(".history.json"), history)

    print(f"best eval ESS/N: {best_ess:.4f} (initial {ev0['ess_per_n']:.4f})")
    print(f"checkpoint: {out_path}")


if __name__ == "__main__":
    main()
