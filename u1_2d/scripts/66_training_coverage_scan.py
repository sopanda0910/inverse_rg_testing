"""Driver: run u1's thermalization scan for CHECKPOINTS that differ in
training coverage, mirroring `u2_2d/scripts/58_training_coverage_scan.py`.

UNLIKE u2, u1 has NO existing checkpoint pair that isolates coverage alone.
The two checkpoints on disk differ in CAPACITY, not range:

  score_net.pt       out/u1_2d/checkpoints/history.json, 101 epochs -- matches
                      configs/v2.yaml (hidden 56, depth 4, batch 16, epochs
                      100), random_rungs beta_max = 60.0 at every volume.
  score_net_big.pt    out/u1_2d/checkpoints/history_big.json, 81 epochs --
                      matches configs/v3_scale.yaml (hidden 80, depth 5,
                      batch 16, epochs 80), SAME beta_max = 60.0.

Both cap at beta = 60. So there is currently nothing on disk that plays the
role u2's det_score_net.pt (model beta ~104) vs det_score_net_v2.pt/_cap.pt
(model beta ~107, denser) play -- a coverage-only ablation for u1 needs an
ACTUAL RETRAIN, not just a re-run of an existing checkpoint under a new scan.
This script is scaffolding for that: point --config at a config whose
`rungs`/`random_rungs` beta_max differs from 60 (copy v2.yaml and edit it,
the way `make_v2_config.py` does for u2), train it with
`u1_2d/scripts/02_train.py --config <that config>`, then point this script
at the resulting checkpoint.

    python u1_2d/scripts/66_training_coverage_scan.py --dry-run
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Fill in once a genuinely coverage-varied checkpoint exists. Left empty by
# default so this script fails loudly rather than silently reusing the two
# capacity-only checkpoints as if they differed in coverage.
CHECKPOINTS: dict = {
    # "narrow60": {"path": "out/u1_2d/checkpoints/score_net.pt",
    #              "config": "u1_2d/configs/v2.yaml", "train_beta_max": 60.0},
    # "wideXXX":  {"path": "out/u1_2d/checkpoints/score_net_wideXXX.pt",
    #              "config": "u1_2d/configs/wideXXX.yaml", "train_beta_max": XXX},
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", nargs="+", default=list(CHECKPOINTS),
                        choices=list(CHECKPOINTS) or [""],
                        help="tags from the CHECKPOINTS table above")
    parser.add_argument("--out-root", default="out/u1_2d/coverage_scan")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not CHECKPOINTS:
        print("CHECKPOINTS is empty -- no u1 checkpoint pair isolates training "
              "coverage yet. See this file's docstring: train a wider- or "
              "narrower-coverage variant first (u1_2d/scripts/02_train.py "
              "--config <a rungs-edited copy of v2.yaml>), then fill in the "
              "table and re-run.")
        return 1

    print(f"{len(args.checkpoints)} checkpoint(s), reusing u1's existing "
          "per-summary scan machinery (05_hmc_thermalization.py --generalization "
          "+ 35_crossover_window.py) -- see u1_2d/scripts/05_hmc_thermalization.py "
          "for the per-coupling cost.")
    for tag in args.checkpoints:
        spec = CHECKPOINTS[tag]
        print(f"[{tag}] checkpoint={spec['path']} config={spec['config']} "
              f"train_beta_max={spec['train_beta_max']}")
        # `05_hmc_thermalization.py --generalization` scores a checkpoint
        # against the GENERALIZATION STUDY's matched coupling pairs, which
        # `06_generalization_study.py` must have already produced for THIS
        # checkpoint (`--generalization <dir>` points at that study's output,
        # defaulting to out/u1_2d/demo/generalization -- a fresh checkpoint
        # needs its own study directory, not the deployed one's). It writes
        # per-coupling `L*_beta*/*_summary.json` under `--out` (defaulting to
        # <study_dir>/../thermalization/generalization); 35 then merges
        # whatever sits under --dir into one crossover_window.json. Verify
        # the exact flag names against the live script before trusting this
        # verbatim -- --generalization's mode is more involved than u2's
        # single-shot 28_crossover_scan.py and this has not been dry-run
        # against a real second checkpoint.
        gen_dir = f"{args.out_root}/{tag}/generalization"
        out_dir = f"{args.out_root}/{tag}/thermalization"
        print(f"       (prerequisite) python u1_2d/scripts/06_generalization_study.py "
              f"--checkpoint {spec['path']} --config {spec['config']} --out-dir {gen_dir}")
        cmd = [sys.executable, "u1_2d/scripts/05_hmc_thermalization.py",
               "--generalization", gen_dir, "--checkpoint", spec["path"],
               "--config", spec["config"], "--out", out_dir]
        print("       $ " + " ".join(cmd))
        if not args.dry_run:
            t0 = time.time()
            subprocess.run(cmd, check=True)
            print(f"       -> done in {(time.time() - t0) / 3600:.2f}h")
        merge_cmd = [sys.executable, "u1_2d/scripts/35_crossover_window.py",
                    "--dir", out_dir, "--out", f"{args.out_root}/{tag}/crossover_window.json"]
        print("       $ " + " ".join(merge_cmd))
        if not args.dry_run:
            subprocess.run(merge_cmd, check=True)

    if args.dry_run:
        print("dry run only -- nothing executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
