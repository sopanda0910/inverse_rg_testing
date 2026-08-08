"""Phase 5: the exactness-suite arms phase 3 invalidated but nothing re-ran.

WHY THIS EXISTS
---------------
Phase 3's invalidate_downstream() correctly deleted every result computed from
the pre-promotion checkpoint. But three of those results have no producer in
the phase 1-4 driver chain, so they were deleted and never rebuilt:

    ess_chain/frontier_rkl2      run_exactness_suite.py FRONTIER_RKL2
    ess_chain/frontier_v2        run_exactness_suite.py FRONTIER_V2
    ess_chain/smc_ladder         run_exactness_suite.py SMC
    ess_chain/verify_rkl2_extra  NO SCRIPT -- it was an ad-hoc script-19 call,
                                 reconstructed below from the frozen report
                                 (2 cases at L=32, --exact-ref, default n=64)

26_final_results_figures.py reads frontier_rkl2 and verify_rkl2_extra for
figure 27 panel (b) -- the per-site density gap across the full (L, beta) grid
covered by the rkl2 checkpoint. With them missing it raised FileNotFoundError,
which is why phase 4 ended PHASE4_DONE_WITH_ERRORS: ['FIG_26'] and figures
26/27 in paper_appendix are still the frozen-campaign renders.

verify_correction/ was deleted too and is also producerless, but figure 27
deliberately EXCLUDES the correction head ("2-6x worse on its disjoint grid,
omitted for scale"), so nothing reads it. It is not rebuilt here.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase5.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCRIPTS = REPO / "u1_2d" / "scripts"
CONFIG = "u1_2d/configs/v2_gpu_verify.yaml"
STATE = REPO / "artifacts" / "gpu_verify" / "state"
CANON = REPO / "out" / "u1_2d"
RKL2 = CANON / "checkpoints" / "score_net_rkl2.pt"

# Recovered from the frozen out/u1_2d/ess_chain/verify_rkl2_extra/report.md:
# two L=32 cases carrying an exact reference column, which is what pins
# --exact-ref. n was not recorded in the JSON; script 19's default of 64
# matches the reported error bars and matches phase 4's VERIFY_RKL2 run.
RKL2_EXTRA_CASES = ["32:14.1464", "32:110"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], device: str | None = None,
              critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if device:
        env["U1_2D_DEVICE"] = device
    else:
        env.pop("U1_2D_DEVICE", None)
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("PHASE5_ABORTED: downstream figures depend on this one")
        sys.exit(1)
    return False


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("PHASE5_START")
    if not RKL2.exists():
        log(f"PHASE5_ABORTED: no rkl2 checkpoint at {RKL2}")
        sys.exit(1)

    failures = []

    # The suite carries its own sentinels in ess_chain/exactness_state/, which
    # phase 3 deleted, so all three of its stages re-run. FRONTIER_RKL2 is
    # critical inside the suite; FRONTIER_V2 and SMC are not.
    if not run_stage("EXACTNESS_SUITE",
                     [PY, str(SCRIPTS / "run_exactness_suite.py")],
                     device="cuda"):
        failures.append("EXACTNESS_SUITE")

    if not run_stage("RKL2_EXTRA",
                     [PY, str(SCRIPTS / "19_ode_reweighting.py"),
                      "--config", CONFIG, "--checkpoint", str(RKL2),
                      "--exact-ref", "--cases", *RKL2_EXTRA_CASES,
                      "--out", str(CANON / "ess_chain" / "verify_rkl2_extra")],
                     device="cuda"):
        failures.append("RKL2_EXTRA")

    # Phase 4 left ASSEMBLE's sentinel behind from the run that tracked the
    # stale figures 26/27; clear both so they actually rebuild.
    for name in ("FIG_26", "ASSEMBLE"):
        (STATE / f"stage_{name}.done").unlink(missing_ok=True)

    for name, cmd in [
        ("FIG_26", [PY, "u1_2d/scripts/26_final_results_figures.py"]),
        ("ASSEMBLE", [PY, "u1_2d/scripts/30_assemble_appendix_figures.py"]),
    ]:
        if not run_stage(name, cmd):
            failures.append(name)

    log(f"PHASE5_DONE_WITH_ERRORS: {failures}" if failures else "PHASE5_DONE")


if __name__ == "__main__":
    main()
