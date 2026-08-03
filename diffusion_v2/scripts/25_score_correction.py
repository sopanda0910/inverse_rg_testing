"""Train the ~600-parameter (sigma, beta) score correction by ODE likelihood.

Generalization protocol (the point of this design):
  * capacity matched to the measured error: two smooth scalars of (sigma,
    beta) -- cannot memorize configurations or cases;
  * trained on ALL data rungs (continuous beta in [1, 60], L in {8, 16, 32}),
    never on a handful of named cases;
  * validation on held-out configs of an evenly-spaced rung subset; best-val
    selection only;
  * judged afterwards by fresh-seed script-19 verification on cases DISJOINT
    from anything used for selection (pass --correction to 19).

    .venv/Scripts/python.exe diffusion_v2/scripts/25_score_correction.py --steps 200
"""

import argparse
import importlib.util
import time
from pathlib import Path

import torch

from diffusion_v2.model.likelihood import conditional_log_likelihood
from diffusion_v2.model.likelihood_train import ml_conditional_log_likelihood
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.score_correction import CorrectedScore, save_correction
from diffusion_v2.model.train import load_checkpoint
from diffusion_v2.utils import load_config, resolve_device, save_json, set_seed

_spec = importlib.util.spec_from_file_location(
    "likelihood_finetune", Path(__file__).parent / "20_likelihood_finetune.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
load_pairs = _mod.load_pairs


def pick_val_rungs(val: list, n: int) -> list:
    ordered = sorted(val, key=lambda r: (r["fine"].shape[-1], r["beta"]))
    if len(ordered) <= n or n <= 1:
        return ordered[:max(n, 1)]
    idx = [round(i * (len(ordered) - 1) / (n - 1)) for i in range(n)]
    return [ordered[i] for i in sorted(set(idx))]


def eval_val_logq(model, schedule, val, args, device):
    model.eval()
    total, count = 0.0, 0
    for r in val:
        log_q = conditional_log_likelihood(
            model, schedule, r["coarse"], r["fine"], r["beta"],
            n_steps=args.eval_ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            physics_blend_beta_min=args.physics_blend_beta_min,
            batch_size=8, device=device, seed=args.seed,
        )
        total += float(log_q.sum()) / r["fine"][0].numel()
        count += log_q.numel()
    model.train()
    return total / count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="diffusion_v2/configs/v2.yaml")
    parser.add_argument("--checkpoint", default="out/diffusion_v2/checkpoints/score_net_rkl2.pt")
    parser.add_argument("--out", default="out/diffusion_v2/checkpoints/score_correction.pt")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--lr", type=float, default=3e-3)
    parser.add_argument("--hidden", type=int, default=16)
    parser.add_argument("--ml-batch", type=int, default=6)
    parser.add_argument("--ml-ode-steps", type=int, default=20)
    parser.add_argument("--eval-ode-steps", type=int, default=40)
    parser.add_argument("--n-probes", type=int, default=1)
    parser.add_argument("--beta-min", type=float, default=1.0)
    parser.add_argument("--configs-per-rung", type=int, default=24)
    parser.add_argument("--val-per-rung", type=int, default=4)
    parser.add_argument("--max-rungs", type=int, default=0)
    parser.add_argument("--n-val-rungs", type=int, default=16)
    parser.add_argument("--eval-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--consistency-weight", type=float, default=None)
    parser.add_argument("--physics-blend", type=float, default=None)
    parser.add_argument("--physics-blend-beta-min", type=float, default=None)
    parser.add_argument("--sigma-min-coef", type=float, default=0.03)
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(args.seed)
    device = resolve_device(config)
    ladder_cfg = config.get("ladder", {})
    if args.consistency_weight is None:
        args.consistency_weight = float(ladder_cfg.get("consistency_weight", 1.0))
    if args.physics_blend is None:
        args.physics_blend = float(ladder_cfg.get("physics_blend_coef", 0.0))
    if args.physics_blend_beta_min is None:
        args.physics_blend_beta_min = float(ladder_cfg.get("physics_blend_beta_min", 0.0))

    base, schedule = load_checkpoint(args.checkpoint, device)
    schedule = GeometricNoiseSchedule(
        schedule.sigma_min, schedule.sigma_max, sigma_min_beta_coef=args.sigma_min_coef
    )
    model = CorrectedScore(base, hidden=args.hidden).to(device)
    model.train()
    n_par = sum(p.numel() for p in model.net.parameters())

    train, val_all = load_pairs(config, args, device)
    val = pick_val_rungs(val_all, args.n_val_rungs)
    print(f"correction params: {n_par}; train rungs: {len(train)}; "
          f"val rungs: {[r['name'] for r in val]}", flush=True)

    optimizer = torch.optim.Adam(model.net.parameters(), lr=args.lr)
    gen = torch.Generator().manual_seed(args.seed)
    history = []
    val0 = eval_val_logq(model, schedule, val, args, device)
    best_val = val0
    print(f"initial val log q/dof: {val0:.4f}", flush=True)
    save_correction(model, args.checkpoint, args.out)

    for step in range(1, args.steps + 1):
        t0 = time.time()
        r = train[int(torch.randint(len(train), (1,), generator=gen))]
        idx = torch.randperm(r["fine"].shape[0], generator=gen)[: args.ml_batch]
        log_q = ml_conditional_log_likelihood(
            model, schedule, r["coarse"][idx], r["fine"][idx], r["beta"],
            n_steps=args.ml_ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            physics_blend_beta_min=args.physics_blend_beta_min,
            device=device,
        )
        loss = -log_q.mean() / r["fine"][0].numel()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        rec = {"step": step, "rung": r["name"], "loss_ml_per_dof": float(loss),
               "seconds": round(time.time() - t0, 1)}
        if step % args.eval_every == 0 or step == args.steps:
            rec["val_logq_per_dof"] = eval_val_logq(model, schedule, val, args, device)
            with torch.no_grad():
                probe_sig = torch.tensor([0.05, 0.5, 3.0], device=device)
                for b in (4.0, 55.0):
                    a_c, b_c = model.coefficients(probe_sig, torch.full((3,), b, device=device))
                    rec[f"coeffs_beta{b:g}"] = [[round(float(x), 4), round(float(y), 4)]
                                                for x, y in zip(a_c, b_c)]
            if rec["val_logq_per_dof"] > best_val:
                best_val = rec["val_logq_per_dof"]
                save_correction(model, args.checkpoint, args.out)
                rec["saved"] = args.out
        history.append(rec)
        print(rec, flush=True)
        save_json(Path(args.out).with_suffix(".history.json"), history)

    print(f"best val log q/dof: {best_val:.4f} (initial {val0:.4f})")
    print(f"correction: {args.out}")


if __name__ == "__main__":
    main()
