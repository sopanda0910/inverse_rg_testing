"""How expensive is fixing topology WITHOUT the analytic P(Q)? (sec 21.5, route 1)

Sector statistics in this study are made correct either by transport (the
model's own sector, carried from the coarse configuration) or by exact-sector
resampling against the analytically known finite-volume P(Q). Only the first
exists in a theory where P(Q) is not solvable, and on its own it degrades
badly with volume -- the unaided sector match rate falls 0.484 / 0.234 / 0.094
at L = 16 / 32 / 64.

The theory-agnostic replacement is a short instanton-HMC tail: the Q-hop
proposal has a computable action difference, so Metropolis fixes the sector
distribution without anyone knowing P(Q). Script 18 already shows a
200-trajectory tail repairing P(Q) at one volume. The open question -- and the
single most informative unmeasured number in the study -- is how that tail
length SCALES.

    tail(V) flat or mild   -> P(Q) dependence is removable at negligible cost
    tail(V) ~ tunneling    -> the method inherits the critical slowing down it
                              exists to avoid, and the flat-cost claim dies
                              above some volume

Either answer is publishable; the second is more important. This script
measures it: for each volume, run the adaptive tail from script 18 and record
the trajectories needed for the P(Q) chi^2 to pass, plus what the tail costs
in wall-clock relative to the diffusion generation it is correcting.

Deliberately reuses 18's `hmc_tail` and `chi2_p` so the convergence criterion
is identical to Table S4's; a re-implementation here would produce numbers
that are not comparable to the table they extend.

    .venv/Scripts/python.exe u1_2d/scripts/38_sector_tail_scaling.py \
        --cases 32:14.1464 32:55.0237 64:55.0237 --max-traj 4000
"""

import argparse
import importlib.util
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from u1_2d.lgt import exact, make_action
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.lgt.lattice import topological_charge
from u1_2d.utils import load_config, load_ensemble, resolve_device, save_json

REPO = Path(__file__).resolve().parents[2]


def _load_18():
    """Reuse script 18's tail and chi^2 so the criterion matches Table S4."""
    spec = importlib.util.spec_from_file_location(
        "pq18", REPO / "u1_2d" / "scripts" / "18_pq_hmc_tail.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_ensemble(gen_dir: Path, action_type: str, L: int, beta: float,
                  variant: str = "transport"):
    """Fine ensemble for (L, beta) from the study outputs.

    Files are named `{run_id}_{action}_L{L}_beta{beta}.pt`, with a parallel
    `_raw_` variant written before charge enforcement.

      transport -- charge projection applied. Uses only the coarse
                   conditioner, so it is available in ANY theory and is the
                   realistic starting point for a tail that must work without
                   an analytic P(Q).
      raw       -- the model's own sectors, no enforcement. This is the
                   control: the difference between the two tails is what
                   transport actually buys.

    Exact-sector ensembles are excluded from both -- they have already used
    the crutch this experiment exists to remove.
    """
    pat = f"*_{action_type}_L{L}_beta*.pt"
    want_raw = variant == "raw"
    for cand in sorted((gen_dir / "generated").glob(pat)) + sorted(gen_dir.glob(pat)):
        if ("_raw_" in cand.name) != want_raw:
            continue
        try:
            b = float(cand.stem.split("beta")[1])
        except (ValueError, IndexError):
            continue
        if abs(b - beta) <= 1e-3 * max(1.0, abs(beta)):
            return cand
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="u1_2d/configs/v2.yaml")
    ap.add_argument("--cases", nargs="+",
                    default=["32:14.1464", "32:55.0237", "64:55.0237",
                             "32:218.58", "64:218.58"],
                    help="fine_L:fine_beta. The study generates L >= 32 (base "
                         "16 -> fine 32), so L=16 has no ensemble to tail.")
    ap.add_argument("--gen-dir", default="out/u1_2d/generalization")
    ap.add_argument("--n-configs", type=int, default=96)
    ap.add_argument("--max-traj", type=int, default=4000,
                    help="hard cap; a case that hits this is reported as unconverged")
    ap.add_argument("--check-every", type=int, default=50)
    ap.add_argument("--min-traj", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260814)
    ap.add_argument("--device", default=None)
    ap.add_argument("--variant", choices=["transport", "raw"], default="transport",
                    help="transport = charge projection applied (the theory-agnostic "
                         "input); raw = the model's own sectors, as a control")
    ap.add_argument("--out", default="out/u1_2d/sector_tail_scaling")
    args = ap.parse_args()

    m18 = _load_18()
    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    action_type = config["action_type"]
    gen_dir = REPO / args.gen_dir
    out_dir = REPO / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in args.cases:
        L_s, beta_s = case.split(":")
        L, beta = int(L_s), float(beta_s)
        path = find_ensemble(gen_dir, action_type, L, beta, args.variant)
        if path is None:
            print(f"[skip] {case}: no generated ensemble under {gen_dir}", flush=True)
            continue
        configs, _ = load_ensemble(path)
        configs = configs[: args.n_configs]
        V = 2 * L * L

        # Same construction as 18.run_case, so the convergence criterion and
        # the chi^2 are identical to Table S4's.
        q_values, probs = exact.topological_charge_distribution(beta, L, action_type)
        exact_q2 = float((q_values.astype(float) ** 2 * probs).sum())

        q_before = topological_charge(configs).numpy()
        p_before = m18.chi2_p(q_before, q_values, probs)

        # Power guard. The stopping rule is (chi^2 p >= 0.05) AND (<Q^2> within
        # 2 sem of exact). The second half holds its relative precision at any
        # volume -- 2 sem / <Q^2> -> 2 sqrt(2/n) for near-Gaussian Q, i.e. 29%
        # at n = 96 regardless of V -- so the measurement stays comparable
        # across the series. The first half does NOT: `chi2_p` keeps only
        # sectors with expected count > 2, and as V grows P(Q) spreads until
        # too few survive, at which point it returns None and `sector_converged`
        # reads that as a PASS. A tail that shortens because the test lost power
        # is not a tail that got easier, so record the bin count per volume.
        n_cfg = int(configs.shape[0])
        testable_bins = int((probs * n_cfg > 2.0).sum())

        # The adaptive loop cannot report a tail shorter than
        # min_traj + check_every (two consecutive passing checks), so a case
        # that needed NO correction and a case that needed 100 trajectories
        # both come back as 100. Evaluate the stopping rule on the untouched
        # ensemble to tell those apart -- "already correct" is the interesting
        # answer here, and it is invisible without this.
        already = bool(m18.sector_converged(q_before, q_values, probs, exact_q2))

        t0 = time.time()
        final, q_series, converged = m18.hmc_tail(
            configs, beta, action_type, args.max_traj, device, args.seed,
            q_values=q_values, probs=probs, exact_q2=exact_q2,
            check_every=args.check_every, min_traj=args.min_traj)
        secs = time.time() - t0

        n_traj = len(q_series) - 1
        q_after = q_series[-1]
        p_after = m18.chi2_p(q_after, q_values, probs)

        row = {
            "L": L, "beta": beta, "V": V,
            "n_configs": int(configs.shape[0]),
            "chi2_p_before": p_before, "chi2_p_after": p_after,
            "q2_before": float((q_before.astype(float) ** 2).mean()),
            "q2_after": float((q_after.astype(float) ** 2).mean()),
            "exact_q2": float(exact_q2),
            "tail_trajectories": None if not converged else int(n_traj),
            "converged": bool(converged),
            "chi2_testable_bins": testable_bins,
            "chi2_available": p_after is not None,
            "already_converged": already,
            "tail_needed": 0 if already else (None if not converged else int(n_traj)),
            "variant": args.variant,
            "exact_q2_relative_tol": (2.0 * (2.0 / n_cfg) ** 0.5),
            "seconds": round(secs, 1),
            "seconds_per_config": round(secs / max(configs.shape[0], 1), 3),
        }
        rows.append(row)
        shown = ("0 (already correct)" if already
                 else (f"{n_traj}" if converged else f">{args.max_traj}"))
        fmt = lambda v: "n/a" if v is None else f"{v:.3g}"
        print(f"{case} [{args.variant}]: V={V} tail={shown}  chi2 p {fmt(p_before)} -> "
              f"{fmt(p_after)} ({testable_bins} bins)  {secs:.0f}s", flush=True)

    if not rows:
        raise SystemExit("no cases ran; check --gen-dir")

    save_json(out_dir / "sector_tail_scaling.json", rows)

    print("\n| L | beta_f | V | <Q^2> exact | chi2 bins | chi2 p before | after | "
          "tail traj | s/config |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        tail = ("0" if r["already_converged"]
                else (str(r["tail_trajectories"]) if r["converged"]
                      else f">{args.max_traj}"))
        def g(v):
            return "--" if v is None else f"{v:.3g}"
        print(f"| {r['L']} | {r['beta']:g} | {r['V']} | {r['exact_q2']:.3g} | "
              f"{r['chi2_testable_bins']} | {g(r['chi2_p_before'])} | "
              f"{g(r['chi2_p_after'])} | {tail} | {r['seconds_per_config']} |")

    degraded = [r for r in rows if not r["chi2_available"]]
    if degraded:
        print("\nWARNING: at " + ", ".join(f"V={r['V']}" for r in degraded) +
              " the chi^2 half of the stopping rule was\nnot testable (too few "
              "sectors with expected count > 2) and passed by default. Those\n"
              "tails are set by the <Q^2> criterion alone and are lower bounds.")

    free = [r for r in rows if r["already_converged"]]
    if free:
        print(f"\n{len(free)} of {len(rows)} cases needed NO tail: the ensemble "
              "already satisfies the\nstopping rule before a single trajectory. "
              "For those the exact-P(Q) dependence\ncosts nothing to remove, and "
              "the scaling question does not arise.")
        if all(r["chi2_testable_bins"] >= 3 for r in free):
            print("All of them had a testable chi^2 (>= 3 bins), so this is a "
                  "pass, not an absence of power.")

    conv = [r for r in rows if r["converged"] and not r["already_converged"]]
    if len(conv) >= 2:
        # Fit tail ~ V^k. k ~ 0 means the P(Q) dependence is removable cheaply;
        # k >= 1 means the tail cost grows at least as fast as the volume and
        # the flat-cost claim has a ceiling.
        lv = np.log([r["V"] for r in conv])
        lt = np.log([r["tail_trajectories"] for r in conv])
        k = float(np.polyfit(lv, lt, 1)[0])
        print(f"\ntail trajectories ~ V^{k:.2f} over {len(conv)} converged volumes")
        if k < 0.3:
            print("=> essentially flat: the analytic P(Q) is removable at "
                  "negligible cost.")
        elif k < 1.0:
            print("=> grows sub-linearly in V: removable, at a cost that must be "
                  "quoted alongside the flat-cost claim.")
        else:
            print("=> grows at least linearly in V: the sector fix inherits the "
                  "scaling problem the method exists to avoid. This bounds the "
                  "flat-cost claim and must be stated.")
    else:
        print("\n(need >= 2 converged volumes to fit a scaling exponent)")
    print(f"wrote {(out_dir / 'sector_tail_scaling.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
