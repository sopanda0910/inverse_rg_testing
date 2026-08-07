"""Phase 3: promote the verification run to canonical, re-run the rest of the
campaign against it, and regenerate all 27 appendix figures.

Design note -- why this promotes first instead of threading paths.
The figure scripts read hardcoded canonical locations:

    17 -> OUT/diffusion_vs_instanton, OUT/model_ess, OUT/model_ess_noguide
    23 -> OUT/checkpoints, OUT/ess_chain, OUT/ode_reweighting{,_sweep}
    26 -> OUT/diffusion_vs_instanton, OUT/ess_chain, OUT/ode_reweighting{,_sweep},
          OUT/thermalization

and run_ess_chain.py has no base-checkpoint override at all -- it, like every
other campaign driver, relies on the default out/u1_2d/checkpoints/score_net.pt.
Pointing a dozen scripts at gpu_verification/ would mean either patching each one
or having them silently read the OLD frozen data and emit a figure set that mixes
two models while looking successful. So instead PROMOTE moves the verification
checkpoint and phase-2 outputs into the canonical tree, and every later stage
then runs with its published invocation, unmodified.

DESTRUCTIVE, deliberately: this replaces out/u1_2d/checkpoints/score_net.pt,
generalization/, thermalization/, and paper_appendix/. The previous state is
committed on branch gpu-port-verification (9dc0cba) and recoverable with
`git checkout 9dc0cba -- out/u1_2d`.

Waits on phase 2's AUTOCORR sentinel, so it is safe to queue immediately.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase3.py
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CONFIG = "u1_2d/configs/v2_gpu_verify.yaml"
STATE = REPO / "artifacts" / "gpu_verify" / "state"
VERIFY = REPO / "out" / "u1_2d" / "gpu_verification"
CANON = REPO / "out" / "u1_2d"
VERIFY_CKPT = REPO / "artifacts" / "gpu_verify" / "checkpoints" / "score_net.pt"
CANON_CKPT = CANON / "checkpoints" / "score_net.pt"

SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]
CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]
WAIT_TIMEOUT_H = 12.0


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def wait_for(sentinel: str) -> bool:
    target = STATE / sentinel
    if target.exists():
        log(f"{sentinel} already present")
        return True
    log(f"waiting for {sentinel}, timeout {WAIT_TIMEOUT_H} h")
    deadline = time.time() + WAIT_TIMEOUT_H * 3600
    while time.time() < deadline:
        if target.exists():
            log(f"{sentinel} present, continuing")
            return True
        time.sleep(60)
    log(f"PHASE3_ABORTED: timed out waiting for {sentinel}")
    return False


def run_stage(name: str, cmd: list[str], device: str | None = None,
              threads: str | None = None, critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    for key, val in (("U1_2D_DEVICE", device), ("U1_2D_TORCH_THREADS", threads)):
        if val:
            env[key] = val
        else:
            env.pop(key, None)
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("PHASE3_ABORTED: downstream stages depend on this one")
        sys.exit(1)
    return False


def promote() -> bool:
    """Move the verification run into the canonical tree it will be read from."""
    sentinel = STATE / "stage_PROMOTE.done"
    if sentinel.exists():
        log("STAGE_PROMOTE: sentinel present, skipping")
        return True
    if not VERIFY_CKPT.exists():
        log(f"PHASE3_ABORTED: no verification checkpoint at {VERIFY_CKPT}")
        return False
    log("STAGE_PROMOTE_START")
    CANON_CKPT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERIFY_CKPT, CANON_CKPT)
    log(f"  checkpoint -> {CANON_CKPT}")
    for name in ("generalization", "thermalization", "validation"):
        src, dst = VERIFY / name, CANON / name
        if not src.exists():
            log(f"  SKIP {name}: not produced by phase 1/2")
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        log(f"  {name} -> {dst}")
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log("STAGE_PROMOTE_DONE")
    return True


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("PHASE3_START")
    if not wait_for("stage_AUTOCORR.done"):
        sys.exit(1)
    if not promote():
        sys.exit(1)

    failures = []
    # Every stage below uses its published invocation and default paths, which
    # now resolve to the promoted checkpoint.
    data_stages = [
        ("HEADTOHEAD", [PY, "u1_2d/scripts/14_diffusion_vs_instanton_hmc.py",
                        "--config", CONFIG], "cuda"),
        ("ESS", [PY, "u1_2d/scripts/15_model_ess.py", "--config", CONFIG,
                 "--cases", *CASES, "--n-configs", "64"], "cuda"),
        ("ESS_NOGUIDE", [PY, "u1_2d/scripts/15_model_ess.py", "--config", CONFIG,
                         "--cases", *CASES, "--n-configs", "64",
                         "--consistency-weight", "0.0",
                         "--out", str(CANON / "model_ess_noguide")], "cuda"),
        ("BURNIN_SCAN", [PY, "u1_2d/scripts/16_h2h_burnin_scan.py",
                         "--config", CONFIG], "cuda"),
        ("SECTOR_STUDY", [PY, "u1_2d/scripts/06_generalization_study.py",
                          *SAMPLER_FLAGS, "--seed", "20260730", "--device", "cuda",
                          "--symmetrize-base", "--sector-mode", "exact",
                          "--out-dir", str(CANON / "generalization_exact_sectors")], None),
        ("PQ_TAIL", [PY, "u1_2d/scripts/18_pq_hmc_tail.py", "--device", "cuda",
                     "--gen-dir", str(CANON / "generalization"),
                     "--n-traj", "200"], None),
        # Tier-0 sweep must precede the ESS chain: run_ess_chain picks its knobs
        # from sweep_summary.md and blocks waiting for it otherwise.
        ("ODE_SWEEP", [PY, "u1_2d/scripts/run_ode_sweep.py"], "cuda"),
        ("ESS_CHAIN", [PY, "u1_2d/scripts/run_ess_chain.py"], "cuda"),
        ("VERDICT", [PY, "u1_2d/scripts/12_campaign_verdict.py",
                     "--study", str(CANON / "generalization"),
                     "--out", str(CANON / "verdict")], None),
    ]
    for name, cmd, dev in data_stages:
        if not run_stage(name, cmd, device=dev):
            failures.append(name)

    # Figure assembly -- writes into out/u1_2d/paper_appendix.
    for name, cmd in [
        ("FIG_17", [PY, "u1_2d/scripts/17_appendix_figures.py"]),
        ("FIG_23", [PY, "u1_2d/scripts/23_ess_progress_figures.py"]),
        ("FIG_26", [PY, "u1_2d/scripts/26_final_results_figures.py"]),
        ("ASSEMBLE", [PY, "u1_2d/scripts/30_assemble_appendix_figures.py"]),
    ]:
        if not run_stage(name, cmd):
            failures.append(name)

    log(f"PHASE3_DONE_WITH_ERRORS: {failures}" if failures else "PHASE3_DONE")


if __name__ == "__main__":
    main()
