"""TODO item 1: check how the instanton charge projection is used, against sigma.

WHAT IS BEING CHECKED
---------------------
generate_fine_from_coarse applies the instanton charge projection only once the
sampler has descended BELOW `charge_projection_sigma` (default 0.5):

    if sigma_next >= charge_projection_sigma:   # ladder.py
        return theta                            # skip -- still too noisy

The stated justification (docs/NARRATIVE.md sec 13) is that above sigma ~ O(1)
the model still tunnels between sectors on its own, so enforcing there is
wasted work: subsequent steps would wander back out. That is an ASSUMPTION --
0.5 appears in every config in the repo and has never been swept or measured.

This script measures it. It runs the reverse process with enforcement OFF and
records the topological charge of every configuration at every sigma. The
quantity of interest is the largest sigma below which Q stops changing: the
"freezing sigma". The threshold is justified iff

    charge_projection_sigma  <=  sigma_freeze

i.e. projection happens only after the model has committed to a sector. If the
measured freezing sigma is well BELOW 0.5, the projection is firing while the
model is still tunnelling and part of it is being undone -- the threshold is
too high. If it is well ABOVE 0.5, the projection is being applied later than
necessary and configurations spend longer than they need to in the wrong
sector, leaving less noise to relax the instanton strain.

    .venv/Scripts/python.exe u1_2d/scripts/33_charge_freezing_sigma.py \
        --cases 16:14.1464 32:55.0237 --n-configs 64
"""

import argparse
import json
import math
from pathlib import Path

import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.model.sampler import sample_ancestral
from u1_2d.model.score_net import coarse_conditioning_channels
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import blocking_consistency_score
from u1_2d.utils import configure_device, resolve_device, save_json, set_seed

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out" / "u1_2d" / "charge_freezing"


def trace_case(model, schedule, fine_L, fine_beta, args, device):
    coarse_L = fine_L // 2
    coarse_beta = approx_matched_coarse_beta(fine_beta)
    step_size, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
    coarse, _ = run_hmc_ensemble(
        coarse_L, make_action("wilson", coarse_beta),
        n_configs=args.n_configs, n_chains=16, burn_in=burn_in, thin=5,
        n_steps=n_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=coarse_beta < 5,
    )
    coarse = coarse.cpu().to(device).float()
    cond = coarse_conditioning_channels(
        coarse, fine_L, n_channels=getattr(model, "cond_channels", 4)
    )
    coarse_plaq = plaquette_angles(coarse)
    beta = torch.full((coarse.shape[0],), float(fine_beta), device=device)
    sigmas = schedule.discrete_sigmas(args.n_sampler_steps, device=device, beta=fine_beta)

    def score_fn(theta, sigma):
        sig = sigma.expand(theta.shape[0])
        score = model.score(theta, sig, beta, cond)
        if args.consistency_weight > 0:
            score = score + args.consistency_weight * blocking_consistency_score(
                theta, coarse_plaq, sigma
            )
        return score

    # Enforcement OFF: we want the model's own sector dynamics, not the projection's.
    trace = []

    def step_callback(theta, sigma_next):
        trace.append((float(sigma_next), topological_charge(theta).cpu().clone()))
        return theta

    sample_ancestral(
        score_fn, (coarse.shape[0], 2, fine_L, fine_L), sigmas, device=device,
        n_corrector_steps=args.n_corrector_steps, corrector_snr=args.corrector_snr,
        step_callback=step_callback,
    )

    # Per sigma step, what fraction of configurations changed sector since the
    # previous step? The freezing sigma is where this hits (and stays at) zero.
    rows = []
    for i in range(1, len(trace)):
        sigma_prev, q_prev = trace[i - 1]
        sigma_now, q_now = trace[i]
        changed = float((q_now != q_prev).float().mean())
        rows.append({"sigma": sigma_now, "frac_changed": changed})
    # Largest sigma below which nothing changes again.
    sigma_freeze = None
    for i, r in enumerate(rows):
        if all(x["frac_changed"] == 0.0 for x in rows[i:]):
            sigma_freeze = r["sigma"]
            break
    q_final = trace[-1][1]
    q_coarse = topological_charge(coarse).cpu()
    return {
        "fine_L": fine_L, "fine_beta": fine_beta, "coarse_beta": coarse_beta,
        "n_configs": int(coarse.shape[0]),
        "sigma_freeze": sigma_freeze,
        "charge_projection_sigma": args.charge_projection_sigma,
        "threshold_is_below_freeze": (
            None if sigma_freeze is None else bool(args.charge_projection_sigma <= sigma_freeze)
        ),
        "match_rate_without_projection": float((q_final == q_coarse).float().mean()),
        "trace": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="u1_2d/configs/v2.yaml")
    p.add_argument("--checkpoint", default="out/u1_2d/checkpoints/score_net.pt")
    p.add_argument("--cases", nargs="+", default=["16:14.1464", "32:55.0237"])
    p.add_argument("--n-configs", type=int, default=64)
    p.add_argument("--n-sampler-steps", type=int, default=200)
    p.add_argument("--n-corrector-steps", type=int, default=1)
    p.add_argument("--corrector-snr", type=float, default=0.16)
    p.add_argument("--consistency-weight", type=float, default=1.0)
    p.add_argument("--charge-projection-sigma", type=float, default=0.5)
    p.add_argument("--device", default=None)
    p.add_argument("--seed", type=int, default=20260812)
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
        print(f"case L={L} beta={b} ...", flush=True)
        r = trace_case(model, schedule, int(L), float(b), args, device)
        sf = r["sigma_freeze"]
        print(f"  sigma_freeze={sf}  threshold={args.charge_projection_sigma}  "
              f"ok={r['threshold_is_below_freeze']}  "
              f"match_rate_no_projection={r['match_rate_without_projection']:.3f}",
              flush=True)
        results.append(r)

    save_json(out_dir / "charge_freezing.json", results)
    lines = ["# Charge-freezing sigma vs the projection threshold", "",
             "| case | sigma_freeze | threshold | threshold <= freeze | Q match w/o projection |",
             "|---|---|---|---|---|"]
    for r in results:
        sf = r["sigma_freeze"]
        sf_txt = "never froze" if sf is None else f"{sf:.4f}"
        lines.append(
            f"| {r['fine_L']}:{r['fine_beta']:g} | {sf_txt} | "
            f"{r['charge_projection_sigma']} | {r['threshold_is_below_freeze']} | "
            f"{r['match_rate_without_projection']:.3f} |"
        )
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
