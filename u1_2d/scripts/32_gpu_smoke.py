"""Run every compute-bearing script once on a GPU, with the smallest workload
that still exercises its device plumbing.

Why this exists: the scripts were all written and validated on CPU-only
machines, so a whole class of bug is invisible there -- a tensor that lands on
the wrong device only conflicts when the two devices actually differ. 06 had
exactly that bug (hmc_ensemble_cached returned on `device` while
generate_fine_from_coarse returns CPU) and it killed every case instantly.

The convention these scripts must follow:
  * ensembles are CPU-resident -- load_ensemble pins map_location='cpu',
    save_ensemble calls .cpu(), generate_fine_from_coarse returns CPU chunks
  * only the model forward and the HMC integrator run on `device`
  * run_hmc_ensemble is the ONE function that returns tensors on its `device`,
    so its output must be normalized before mixing with anything else

    .venv/Scripts/python.exe u1_2d/scripts/32_gpu_smoke.py            # all
    .venv/Scripts/python.exe u1_2d/scripts/32_gpu_smoke.py --only 05,06
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CFG = "u1_2d/configs/v2_gpu_verify.yaml"
CKPT = "out/u1_2d/checkpoints/score_net.pt"
SCRATCH = "artifacts/gpu_smoke"
CASE = "16:14.1464"

# Smallest arguments that still build a model, move data, and run the sampler.
CASES: dict[str, list[str]] = {
    "16": ["16_h2h_burnin_scan.py", "--config", CFG, "--betas", "14.1464",
           "--burn-ins", "20", "--lattice-size", "16", "--n-chains", "4",
           "--n-prod", "10", "--out-dir", f"{SCRATCH}/16"],
    "19": ["19_ode_reweighting.py", "--config", CFG, "--checkpoint", CKPT,
           "--cases", CASE, "--n-configs", "4", "--ode-steps", "6",
           "--n-probes", "1", "--batch-size", "4", "--out", f"{SCRATCH}/19"],
    "20": ["20_likelihood_finetune.py", "--config", CFG, "--checkpoint", CKPT,
           "--out-checkpoint", f"{SCRATCH}/20.pt", "--steps", "2", "--ml-batch", "2",
           "--ml-ode-steps", "4", "--eval-ode-steps", "4", "--n-probes", "1",
           "--max-rungs", "2", "--configs-per-rung", "4", "--val-per-rung", "2",
           "--eval-every", "2"],
    "21": ["21_reverse_kl_finetune.py", "--config", CFG, "--checkpoint", CKPT,
           "--out-checkpoint", f"{SCRATCH}/21.pt", "--case", CASE, "--steps", "2",
           "--batch", "2", "--ode-steps", "4", "--eval-ode-steps", "4",
           "--n-probes", "1", "--n-coarse", "4", "--n-coarse-eval", "4",
           "--max-rungs", "2", "--configs-per-rung", "4", "--val-per-rung", "2",
           "--eval-every", "2"],
    "22": ["22_multicase_rkl.py", "--config", CFG, "--checkpoint", CKPT,
           "--out-checkpoint", f"{SCRATCH}/22.pt", "--train-cases", CASE,
           "--steps", "2", "--batch-l16", "2", "--ode-steps", "4",
           "--eval-ode-steps", "4", "--n-probes", "1", "--n-train-coarse", "4",
           "--n-eval", "4", "--max-rungs", "2", "--configs-per-rung", "4",
           "--val-per-rung", "2", "--eval-every", "2"],
    "24": ["24_smc_ladder.py", "--config", CFG, "--checkpoint", CKPT,
           "--n-configs", "4", "--ode-steps", "6", "--n-probes", "1",
           "--batch-size", "4", "--out", f"{SCRATCH}/24"],
    "25": ["25_score_correction.py", "--config", CFG, "--checkpoint", CKPT,
           "--out", f"{SCRATCH}/25", "--steps", "2", "--ml-batch", "2",
           "--ml-ode-steps", "4", "--eval-ode-steps", "4", "--n-probes", "1",
           "--max-rungs", "2", "--configs-per-rung", "4", "--val-per-rung", "2",
           "--eval-every", "2"],
    "27": ["27_matching_residual.py", "--config", CFG, "--checkpoint", CKPT,
           "--cases", CASE, "--n-configs", "4", "--ode-steps", "6",
           "--n-probes", "1", "--batch-size", "4", "--out", f"{SCRATCH}/27"],
    "28": ["28_ais_transport.py", "--config", CFG, "--checkpoint", CKPT,
           "--cases", CASE, "--n-configs", "4", "--ode-steps", "6",
           "--n-probes", "1", "--batch-size", "4", "--n-bridge", "2",
           "--out", f"{SCRATCH}/28"],
}

DEVICE_ERROR = "expected all tensors to be on the same device"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None, help="comma-separated script prefixes")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    wanted = set(args.only.split(",")) if args.only else set(CASES)
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_DEVICE": args.device}
    rows = []
    for key in sorted(wanted):
        if key not in CASES:
            print(f"unknown script key {key}; have {sorted(CASES)}")
            continue
        cmd = [PY, f"u1_2d/scripts/{CASES[key][0]}", *CASES[key][1:]]
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True,
                               text=True, timeout=args.timeout)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                verdict, detail = "PASS", ""
            elif DEVICE_ERROR in out.lower():
                verdict, detail = "DEVICE-BUG", "cuda/cpu tensor mix"
            else:
                last = [l for l in out.strip().splitlines() if l.strip()]
                verdict, detail = "FAIL", (last[-1][:90] if last else f"rc={r.returncode}")
        except subprocess.TimeoutExpired:
            verdict, detail = "TIMEOUT", f">{args.timeout}s"
        rows.append((key, CASES[key][0], verdict, f"{time.time()-t0:.0f}s", detail))
        print(f"  {key:4s} {verdict:10s} {rows[-1][3]:>6s}  {detail}", flush=True)

    print(f"\n{'script':34s} {'verdict':10s} {'time':>6s}  detail")
    for key, name, verdict, secs, detail in rows:
        print(f"{name:34s} {verdict:10s} {secs:>6s}  {detail}")
    bad = [r for r in rows if r[2] != "PASS"]
    print(f"\n{len(rows)-len(bad)}/{len(rows)} pass on {args.device}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
