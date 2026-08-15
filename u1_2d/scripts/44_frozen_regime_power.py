"""Give the deep-frozen sector tests enough configurations to mean something.

The residual caveat left by sec 21.6: at large beta the exact-P(Q) chi^2 has
almost no power, because P(Q) concentrates on Q = 0 and `chi2_p` only keeps
bins with expected count > 2. At beta = 218.58, L = 32 the study's 128
configurations leave

    P(0) = 0.9710, P(+-1) = 0.0145  ->  expected count 1.86 in the +-1 bins

so exactly one bin survives the filter, `chi2_p` returns None, and the
convergence rule treats that as a pass. A "pass" there is close to vacuous, and
the honest reading of the topology result at the extrapolation coupling has
been limited by it.

That is a sample-size problem with a sample-size fix. The threshold for three
testable bins is n >= 138; for expected counts >= 5 (the usual chi^2 rule of
thumb) it is n >= 345. This regenerates the deep-frozen cases at n = 512 and
re-runs the test where it can actually fail.

Reported per case: the number of testable bins, the expected count in the
smallest kept bin, chi^2 p, and z(<Q^2>) -- plus, for contrast, the same
quantities recomputed on the first 128 configurations, so the gain in power is
visible rather than asserted.

    .venv/Scripts/python.exe u1_2d/scripts/44_frozen_regime_power.py \
        --cases 55.0237 118.473 218.58 --n-configs 512
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
from u1_2d.lgt.lattice import topological_charge
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


def power_report(q, q_values, probs, chi2_p) -> dict:
    """chi^2 with its power stated, not just its p-value."""
    n = len(q)
    keep = probs * n > 2.0
    kept = int(keep.sum())
    smallest = float((probs[keep] * n).min()) if kept else float("nan")
    return {
        "n": n,
        "testable_bins": kept,
        "smallest_expected_count": smallest,
        "chi2_p": chi2_p(q, q_values, probs),
        "meets_rule_of_thumb": bool(kept >= 3 and smallest >= 5.0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--cases", nargs="+", type=float,
                    default=[55.0237, 118.473, 218.58],
                    help="fine beta values at L=32 (deep-frozen end of the scan)")
    ap.add_argument("--fine-L", type=int, default=32)
    ap.add_argument("--n-configs", type=int, default=512)
    ap.add_argument("--compare-n", type=int, default=128,
                    help="subsample size to show the power gain against")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out", default="out/u1_2d/frozen_regime_power")
    args = ap.parse_args()

    m18 = _load_18()
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

    for fine_beta in args.cases:
        coarse_beta = approx_matched_coarse_beta(fine_beta)
        coarse_L = args.fine_L // 2
        step, n_steps = adapted_hmc_params(coarse_beta, 0.2, 5)
        burn_in = 200 if coarse_beta < 5 else (2000 if coarse_beta >= 20 else 600)
        t0 = time.time()
        coarse, _ = run_hmc_ensemble(
            coarse_L, make_action(action_type, coarse_beta),
            n_configs=args.n_configs, n_chains=16, burn_in=burn_in, thin=5,
            n_steps=n_steps, step_size=step, device=device,
            topological_updates=True, hot_start=coarse_beta < 5)
        coarse = coarse.cpu()
        fine = generate_fine_from_coarse(
            model, schedule, coarse, fine_beta,
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
        secs = time.time() - t0

        q = topological_charge(fine).numpy()
        q_values, probs = exact.topological_charge_distribution(
            fine_beta, args.fine_L, action_type)
        exact_q2 = float((q_values.astype(float) ** 2 * probs).sum())

        full = power_report(q, q_values, probs, m18.chi2_p)
        sub = power_report(q[: args.compare_n], q_values, probs, m18.chi2_p)

        q2 = float((q.astype(float) ** 2).mean())
        sem = float((q.astype(float) ** 2).std()) / math.sqrt(len(q))
        row = {
            "fine_L": args.fine_L, "fine_beta": fine_beta,
            "coarse_beta": coarse_beta,
            "exact_q2": exact_q2, "q2": q2, "q2_sem": sem,
            "z_q2": (q2 - exact_q2) / sem if sem > 0 else float("nan"),
            "at_n": full, f"at_n{args.compare_n}": sub,
            "seconds": round(secs, 1),
        }
        rows.append(row)
        print(f"beta={fine_beta:g}: n={full['n']} bins={full['testable_bins']} "
              f"(min exp {full['smallest_expected_count']:.1f}) "
              f"chi2 p={full['chi2_p']}  |  at n={sub['n']}: "
              f"bins={sub['testable_bins']} chi2 p={sub['chi2_p']}  "
              f"z(Q^2)={row['z_q2']:+.2f}  [{secs:.0f}s]", flush=True)
        save_json(out_dir / "frozen_regime_power.json", rows)

    print("\n| L | beta_f | n | testable bins | min expected count | chi2 p | "
          f"chi2 p at n={args.compare_n} | z(<Q^2>) | powered? |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        f, s = r["at_n"], r[f"at_n{args.compare_n}"]
        fmt = lambda v: "not testable" if v is None else f"{v:.3g}"
        print(f"| {r['fine_L']} | {r['fine_beta']:g} | {f['n']} | "
              f"{f['testable_bins']} | {f['smallest_expected_count']:.1f} | "
              f"{fmt(f['chi2_p'])} | {fmt(s['chi2_p'])} | {r['z_q2']:+.2f} | "
              f"{'yes' if f['meets_rule_of_thumb'] else 'no'} |")
    print("\nA case that is 'powered' has >= 3 bins with expected count >= 5, so "
          "the chi^2\ncould have failed. Where the n=%d column reads 'not "
          "testable' and the\nfull column does not, the extra configurations "
          "bought a real test." % args.compare_n)
    print(f"wrote {(out_dir / 'frozen_regime_power.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
