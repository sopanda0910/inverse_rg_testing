"""Driver: run `28_crossover_scan.py` for several CHECKPOINTS that differ in
training coverage, so `59_coverage_comparison_figure.py` can show how the
cost-efficiency curve of `57_cost_efficiency_figure.py` falls off at different
points depending on how much beta range the net was shown.

NO RETRAINING NEEDED. Three checkpoints already on disk span exactly the
comparison the paper wants, and their differences are already characterized
in CLAUDE.md / the training histories:

  det_score_net.pt      12 fixed rungs only, no random-beta coverage.
                         Highest model beta seen: 104.132 (narrowest).
  det_score_net_v2.pt   the same 12 fixed rungs + ~102 random-beta rungs to
                         model beta ~430, SAME capacity/epochs as the
                         deployed net (hidden 64, depth 4, batch 32, 120
                         epochs). This is "more coverage, same capacity" --
                         CLAUDE.md's own retrain measured this as diluting
                         precision (the tuned-sweep-count regression 5 -> 30).
  det_score_net_cap.pt  the same wide data as v2 PLUS more capacity/epochs
                         (hidden 96, depth 5, batch 64, 260 epochs). "More
                         coverage, capacity raised to match" -- the intended
                         fix for v2's dilution.

That triple is the whole point: it isolates coverage from capacity (default
vs v2) and then shows what restores the falloff when capacity is added back
(v2 vs cap). Read `docs/u2_2d/DESIGN.md` / CLAUDE.md's capacity-retrain
section before trusting cap's numbers blindly -- its own scorecard there is
mixed, not a clean win everywhere.

This script only ORCHESTRATES -- it shells out to `28_crossover_scan.py`
once per (checkpoint, round) into its own --out-dir/seeds cache (checkpoints
differ, so lifted seeds are NOT shared across them; each combination pays
for its own diffusion lift). It does not touch out/u2_2d/crossover, the
directory the deployed checkpoint's figure already reads.

    python u2_2d/scripts/58_training_coverage_scan.py --dry-run
    python u2_2d/scripts/58_training_coverage_scan.py --checkpoints v2 cap
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

CHECKPOINTS = {
    "default": {
        "path": "out/u2_2d/checkpoints/det_score_net.pt",
        "train_model_beta_max": 104.132,
        "label": "default (12 fixed rungs, no random coverage)",
    },
    "cov": {
        "path": "out/u2_2d/checkpoints/det_score_net_cov.pt",
        "train_model_beta_max": 104.132,  # 12 fixed rungs, same betas as default
        "label": "cov (12 fixed rungs, extended fixed-rung betas)",
    },
    "v2": {
        "path": "out/u2_2d/checkpoints/det_score_net_v2.pt",
        "train_model_beta_max": 430.0 / 4.0,  # random_rungs beta_max=430 -> model beta ~ beta/4 at this range
        "label": "v2 (+102 random rungs to beta 430, same capacity as default)",
    },
    "cap": {
        "path": "out/u2_2d/checkpoints/det_score_net_cap.pt",
        "train_model_beta_max": 430.0 / 4.0,
        "label": "cap (same wide data as v2, hidden 96/depth 5/260 epochs)",
    },
    "cov60": {
        "path": "out/u2_2d/checkpoints/det_score_net_cov60.pt",
        "train_model_beta_max": 56.83,
        "label": "cov60 (coverage capped at model beta ~60, matching u1_2d; "
                 "same capacity as default)",
    },
    "cov30": {
        "path": "out/u2_2d/checkpoints/det_score_net_cov30.pt",
        "train_model_beta_max": 29.60,
        "label": "cov30 (coverage capped at model beta ~30; same capacity)",
    },
    "cov15": {
        "path": "out/u2_2d/checkpoints/det_score_net_cov15.pt",
        "train_model_beta_max": 14.55,
        "label": "cov15 (coverage capped at model beta ~15; same capacity)",
    },
}

# Per-round wall clock estimate (hours) for ONE (checkpoint, round) at L=32,
# 14 couplings, the same budget schedule 28_crossover_scan.py defaults to.
# This is a coarse estimate from the measured GPU throughput in CLAUDE.md
# (~5 traj/s, flat in L, launch-bound) and the scan's own trajectory budget
# (100:400,600:200,inf:150) plus lift generation (200 sampler steps x 14
# couplings). NOT a promise -- print it, then let the first coupling's
# reported [Ns] time refine it live.
EST_HOURS_PER_ROUND = 1.5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", nargs="+", default=["v2", "cap"],
                        choices=list(CHECKPOINTS),
                        help="which of the table above to scan (default "
                             "already has data under out/u2_2d/crossover)")
    parser.add_argument("--fine-size", type=int, default=32)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--n-couplings", type=int, default=14)
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-root", default="out/u2_2d/coverage_scan")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the commands and the ETA, run nothing")
    args = parser.parse_args()

    n = len(args.checkpoints)
    total_hours = n * 2 * EST_HOURS_PER_ROUND
    print(f"{n} checkpoint(s) x 2 rounds (plain, winding) x ~{EST_HOURS_PER_ROUND:.1f}h "
          f"= ~{total_hours:.1f}h estimated, sequential on one GPU context.")
    print("(measured GPU HMC throughput is flat in L, so an L=64 pass would "
          "cost about the same per coupling -- add it only after L=32 confirms "
          "the story.)")
    print()

    for tag in args.checkpoints:
        spec = CHECKPOINTS[tag]
        out_dir = f"{args.out_root}/{tag}"
        print(f"[{tag}] {spec['label']}")
        print(f"       checkpoint: {spec['path']}")
        print(f"       out-dir:    {out_dir}")
        for topo_flag, round_tag in ((False, "crossover"), (True, "crossover_topo")):
            cmd = [
                sys.executable, "u2_2d/scripts/28_crossover_scan.py",
                "--checkpoint", spec["path"],
                "--fine-size", str(args.fine_size),
                "--n-chains", str(args.n_chains),
                "--n-couplings", str(args.n_couplings),
                "--out-dir", out_dir,
                "--tag", round_tag,
            ]
            if topo_flag:
                cmd.append("--topological-updates")
            if args.device:
                cmd += ["--device", args.device]
            print("       $ " + " ".join(cmd))
            if args.dry_run:
                continue
            t0 = time.time()
            subprocess.run(cmd, check=True)
            print(f"       -> {round_tag} done in {(time.time() - t0) / 3600:.2f}h")
        print()

    if args.dry_run:
        print("dry run only -- nothing executed")
    else:
        print("all requested scans complete; run "
              "59_coverage_comparison_figure.py next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
