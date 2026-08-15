"""TODO item 2, the decisive follow-up: does `topo_weight` lift the RAW sector match rate?

`TODO.md` §2 measured six never-tuned hyperparameters against the deployed
fiber log-weight spread and found five inside seed noise, with `topo_weight`
the one that replicated (all five raised-weight seeds below all three baseline
seeds, pooled one-sided rank p = 0.018). It then recorded the follow-up that
would actually settle it:

    "The decisive follow-up is *not* more spread measurements: it is whether
     topo_weight improves the **raw sector match rate**, since that is the
     mechanism it would have to act through. That runs against the checkpoints
     already trained, with no further training."

This is that measurement. The raw match rate -- the fraction of generated
configurations whose topological charge equals their coarse conditioner's, with
the instanton projection OFF -- is the quantity `topo_weight` is supposed to
move: its training penalty ties the soft charge of the denoised estimate to the
clean target's. If it does not move this, the spread result was acting through
something else and should not be carried forward as a topology recommendation.

DESIGN: the comparison is PAIRED. One coarse ensemble per case is drawn once
and every arm is conditioned on the SAME configurations, because the coarse HMC
draw is a larger source of variance than the effect being measured -- the error
`TODO.md` §2 was written to avoid. Three baseline seeds give the noise floor;
without them a 2% difference between two arms is unreadable.

    .venv/Scripts/python.exe u1_2d/scripts/49_topo_weight_match_rate.py \
        --cases 32:14.1464 32:55.0237 --n-configs 128
"""

import argparse
import itertools
import math
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.lattice import plaquette_angles, topological_charge
from u1_2d.model.sampler import sample_ancestral
from u1_2d.model.score_net import coarse_conditioning_channels
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import blocking_consistency_score
from u1_2d.utils import load_config, resolve_device, save_json, set_seed

REPO = Path(__file__).resolve().parents[2]

BASELINE = ["base_s0", "base_s1", "base_s2"]
TOPO = ["topo03", "topo03_s1", "topo03_s2", "topo05", "topo05_s1"]


def draw_coarse(fine_L, fine_beta, n_configs, device, seed):
    coarse_beta = approx_matched_coarse_beta(fine_beta)
    step_size, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
    burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
    set_seed(seed)
    coarse, _ = run_hmc_ensemble(
        fine_L // 2, make_action("wilson", coarse_beta),
        n_configs=n_configs, n_chains=16, burn_in=burn_in, thin=5,
        n_steps=n_steps, step_size=step_size, device=device,
        topological_updates=True, hot_start=coarse_beta < 5,
    )
    return coarse.cpu(), coarse_beta


def match_rate(model, schedule, coarse, fine_L, fine_beta, args, device):
    """Raw sector match rate with the instanton projection OFF."""
    coarse = coarse.to(device).float()
    cond = coarse_conditioning_channels(
        coarse, fine_L, n_channels=getattr(model, "cond_channels", 4))
    coarse_plaq = plaquette_angles(coarse)
    beta = torch.full((coarse.shape[0],), float(fine_beta), device=device)
    sigmas = schedule.discrete_sigmas(args.n_sampler_steps, device=device,
                                      beta=fine_beta)

    def score_fn(theta, sigma):
        sig = sigma.expand(theta.shape[0])
        score = model.score(theta, sig, beta, cond)
        if args.consistency_weight > 0:
            score = score + args.consistency_weight * blocking_consistency_score(
                theta, coarse_plaq, sigma)
        return score

    fine = sample_ancestral(
        score_fn, (coarse.shape[0], 2, fine_L, fine_L), sigmas, device=device,
        n_corrector_steps=args.n_corrector_steps, corrector_snr=args.corrector_snr)
    q_fine = topological_charge(fine).cpu()
    q_coarse = topological_charge(coarse).cpu()
    dq = (q_fine - q_coarse).abs().float()
    return {"match_rate": float((dq == 0).float().mean()),
            "mean_abs_dq": float(dq.mean()),
            "q2_fine": float(q_fine.double().square().mean()),
            "q2_coarse": float(q_coarse.double().square().mean())}


def rank_test(base_vals, topo_vals) -> float:
    """Exact one-sided p that all baselines rank lowest, under exchangeability."""
    n, k = len(base_vals) + len(topo_vals), len(base_vals)
    if max(base_vals) < min(topo_vals):
        return 1.0 / math.comb(n, k)
    return float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--hparam-dir", default="artifacts/hparam")
    ap.add_argument("--arms", nargs="+", default=BASELINE + TOPO)
    ap.add_argument("--cases", nargs="+", default=["32:14.1464", "32:55.0237"])
    ap.add_argument("--n-configs", type=int, default=128)
    ap.add_argument("--n-sampler-steps", type=int, default=200)
    ap.add_argument("--n-corrector-steps", type=int, default=1)
    ap.add_argument("--corrector-snr", type=float, default=0.16)
    ap.add_argument("--consistency-weight", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u1_2d/topo_weight_match_rate")
    args = ap.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    hp = REPO / args.hparam_dir
    arms = [a for a in args.arms if (hp / a / "score_net.pt").exists()]
    if missing := [a for a in args.arms if a not in arms]:
        print(f"missing checkpoints, skipped: {missing}", flush=True)

    rows = []
    for spec in args.cases:
        Ls, bs = spec.split(":")
        fine_L, fine_beta = int(Ls), float(bs)
        # ONE coarse ensemble, shared by every arm -- this is the whole point.
        coarse, coarse_beta = draw_coarse(fine_L, fine_beta, args.n_configs,
                                          device, args.seed)
        print(f"\n=== {spec} (coarse beta {coarse_beta:.4f}, "
              f"{coarse.shape[0]} configs shared across arms) ===", flush=True)
        for arm in arms:
            model, schedule = load_checkpoint(str(hp / arm / "score_net.pt"), device)
            set_seed(args.seed + 1)
            r = match_rate(model, schedule, coarse, fine_L, fine_beta, args, device)
            r.update({"arm": arm, "case": spec, "fine_L": fine_L,
                      "fine_beta": fine_beta,
                      "group": "baseline" if arm in BASELINE else "topo"})
            rows.append(r)
            print(f"  {arm:12s} match_rate={r['match_rate']:.4f}  "
                  f"mean|dQ|={r['mean_abs_dq']:.4f}  "
                  f"Q2 fine/coarse={r['q2_fine']:.3f}/{r['q2_coarse']:.3f}",
                  flush=True)
            save_json(out_dir / "topo_weight_match_rate.json", rows)

    # Pool per arm across cases, then compare against the baseline seed spread.
    per_arm = {}
    for arm in arms:
        vals = [r["match_rate"] for r in rows if r["arm"] == arm]
        per_arm[arm] = float(np.mean(vals)) if vals else float("nan")
    base = [per_arm[a] for a in BASELINE if a in per_arm]
    topo = [per_arm[a] for a in TOPO if a in per_arm]

    print("\n| arm | group | mean raw match rate |")
    print("|---|---|---|")
    for arm in arms:
        print(f"| {arm} | {'baseline' if arm in BASELINE else 'topo'} "
              f"| {per_arm[arm]:.4f} |")

    print(f"\nbaseline seed spread : {min(base):.4f} - {max(base):.4f}")
    print(f"topo arms            : {min(topo):.4f} - {max(topo):.4f}")
    p = rank_test(base, topo)
    if math.isnan(p):
        print("\nVERDICT: the topo arms do NOT separate from the baseline seed\n"
              "spread. topo_weight does not act through the raw sector match\n"
              "rate, so the TODO.md §2 spread result should not be carried\n"
              "forward as a topology recommendation on this evidence.")
    else:
        print(f"\nVERDICT: complete separation, exact one-sided rank p = {p:.4f}\n"
              "topo_weight raises the raw sector match rate -- the mechanism it\n"
              "would have to act through is confirmed.")
    save_json(out_dir / "summary.json",
              {"per_arm": per_arm, "baseline": base, "topo": topo,
               "rank_p": None if math.isnan(p) else p,
               "cases": args.cases, "n_configs": args.n_configs})
    print(f"\nwrote {(out_dir / 'summary.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
