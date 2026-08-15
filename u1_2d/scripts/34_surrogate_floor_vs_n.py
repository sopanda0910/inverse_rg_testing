"""Is the AIS "irreducible floor" real, or a small-sample artifact?

WHY
---
Table S7 reports a predicted AIS floor sqrt(1 - R^2) * std, with R^2 the
surrogate fit quality, and concludes the bridge saturates it. Every one of
those numbers was produced with n = 96 configurations, split in half, i.e.
**48 points to fit 7-11 collinear features**. Two independent observations now
point at overfitting rather than a physical floor:

  * the rich11 basis raised in-sample R^2 while EXPLODING the held-out weights
    at 2 of 4 cases (recorded as a basis-width negative);
  * the one seed of three where AIS blew up at 32:218.58 (12151 vs ~50) had
    the HIGHEST in-sample R^2 of the three (0.952).

Both are the classic signature of a regression fit on too few points, not of a
basis that is too wide.

WHAT THIS DOES
--------------
The floor depends only on the surrogate REGRESSION, not on the bridge. So this
skips AIS entirely: draw ODE samples once at large n, then re-fit the surrogate
at increasing fit-set sizes and watch the held-out R^2 (and hence the implied
floor) as a function of n_fit. Costs one ODE sampling run per case instead of
one full AIS run per (case, n).

Read the output as:
  * held-out R^2 rising and then flattening with n_fit -> the floor at the
    plateau is the real one, and n = 96 was simply too small to see it;
  * held-out R^2 flat from the start -> the floor is genuine and basis width,
    not sample size, is the binding constraint.

    .venv/Scripts/python.exe u1_2d/scripts/34_surrogate_floor_vs_n.py \
        --cases 16:14.1464 --n-configs 768 --basis final7 rich11
"""

import argparse
import math
from pathlib import Path

import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.model.ais import bridge_features, fit_surrogate_cv
from u1_2d.model.likelihood import conditional_ode_sample, snis_log_weights
from u1_2d.model.train import load_checkpoint
from u1_2d.utils import configure_device, resolve_device, save_json, set_seed

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out" / "u1_2d" / "surrogate_floor"


def study_case(model, schedule, fine_L, fine_beta, args, device):
    coarse_L = fine_L // 2
    coarse_beta = approx_matched_coarse_beta(fine_beta)
    step_size, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
    coarse, _ = run_hmc_ensemble(
        coarse_L, make_action(args.action_type, coarse_beta),
        n_configs=args.n_configs, n_chains=16, burn_in=burn_in, thin=5,
        n_steps=n_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=coarse_beta < 5,
    )
    coarse = coarse.cpu()
    fine, log_q = conditional_ode_sample(
        model, schedule, coarse, fine_beta,
        n_steps=args.ode_steps, n_probes=args.n_probes,
        batch_size=args.batch_size, device=device, seed=args.seed,
    )
    log_w_fiber = snis_log_weights(fine, log_q, fine_beta, args.action_type,
                                   coarse=coarse, coarse_beta_matched=coarse_beta)
    std_before = float(log_w_fiber.std())

    action_f = make_action(args.action_type, float(fine_beta))
    with torch.no_grad():
        target = (log_q.double() + action_f.per_config(fine.float()).cpu().double()).float()

    out = {"fine_L": fine_L, "fine_beta": fine_beta, "coarse_beta": coarse_beta,
           "n_configs": int(fine.shape[0]), "std_before": std_before, "bases": {}}

    n = fine.shape[0]
    hold = torch.arange(1, n, 2)          # fixed held-out half, never fitted on
    fit_pool = torch.arange(0, n, 2)
    for basis in args.basis:
        with torch.no_grad():
            feats = bridge_features(fine.float(), coarse_beta, args.action_type, basis)
        rows = []
        for n_fit in args.fit_sizes:
            if n_fit > len(fit_pool):
                continue
            idx = fit_pool[:n_fit]
            fit = fit_surrogate_cv(feats[idx], target[idx])
            pred_h = feats[hold].double() @ fit["g"] + fit["const"]
            resid_h = (target[hold].double() - pred_h)
            tgt_h = target[hold].double()
            r2_h = float(1.0 - resid_h.var() / tgt_h.var())
            rows.append({
                "n_fit": int(n_fit),
                "r2_insample": float(fit["r2"]),
                "r2_heldout": r2_h,
                "resid_std_heldout": float(resid_h.std()),
                "implied_floor": float(math.sqrt(max(1.0 - r2_h, 0.0)) * std_before),
                "ridge": float(fit.get("ridge", float("nan"))),
            })
            print(f"    {basis} n_fit={n_fit:4d}  R2_in={fit['r2']:.3f}  "
                  f"R2_held={r2_h:+.3f}  floor={rows[-1]['implied_floor']:.1f}", flush=True)
        out["bases"][basis] = rows
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", default="out/u1_2d/checkpoints/score_net_rkl2.pt")
    p.add_argument("--cases", nargs="+", default=["16:14.1464"])
    p.add_argument("--n-configs", type=int, default=768)
    p.add_argument("--fit-sizes", type=int, nargs="+",
                   default=[24, 48, 96, 192, 288, 384])
    p.add_argument("--basis", nargs="+", default=["final7", "rich11"])
    p.add_argument("--ode-steps", type=int, default=120)
    p.add_argument("--n-probes", type=int, default=2)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--action-type", default="wilson")
    p.add_argument("--device", default=None)
    p.add_argument("--seed", type=int, default=20260802)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    # resolve_device returns the DEVICE; configure_device returns a banner
    # string (and sets the CUDA fast paths). Assigning the banner to
    # `device` yields map_location="NVIDIA GeForce RTX 5060..." on load.
    device = resolve_device({"device": args.device or "auto"})
    print(f"device: {configure_device(device)}", flush=True)
    set_seed(args.seed)
    model, schedule = load_checkpoint(args.checkpoint, device)
    out_dir = Path(args.out) if args.out else OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in args.cases:
        L, b = case.split(":")
        print(f"case L={L} beta={b} (n={args.n_configs}) ...", flush=True)
        results.append(study_case(model, schedule, int(L), float(b), args, device))
    save_json(out_dir / "surrogate_floor.json", results)

    lines = ["# Surrogate held-out fit quality vs fit-set size", "",
             "Floor = sqrt(1 - R2_heldout) * std_before. n_fit = 48 is what the",
             "AIS results of record used.", ""]
    for r in results:
        lines += [f"## {r['fine_L']}:{r['fine_beta']:g}  (std_before {r['std_before']:.1f})", "",
                  "| basis | n_fit | R2 in-sample | R2 held-out | implied floor |",
                  "|---|---|---|---|---|"]
        for basis, rows in r["bases"].items():
            for row in rows:
                lines.append(f"| {basis} | {row['n_fit']} | {row['r2_insample']:.3f} | "
                             f"{row['r2_heldout']:+.3f} | {row['implied_floor']:.1f} |")
        lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
