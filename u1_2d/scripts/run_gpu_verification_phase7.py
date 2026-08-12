"""Phase 7: the matching-residual decomposition and both AIS arms.

WHY THIS EXISTS
---------------
Phases 1-6 regenerated every artifact the 27 appendix figures read. A scan of
out/u1_2d for directories older than the campaign then found ten that no
driver ever owned; three of them carry load-bearing appendix claims:

  matching_residual/wilson    Table S6 -- the within-arm R^2_c decomposition.
  matching_residual/villain   CLAUDE.md calls this the argument that ELIMINATES
                              the matching-residual explanation of the density
                              gap. It was still frozen-checkpoint data sitting
                              inside an otherwise regenerated appendix, and
                              three claims re-derived on 2026-08-08 moved
                              materially, so it cannot be assumed to have held
                              still.
  ais_transport               Table S7, final7 surrogate basis (result of
                              record: saturates its derived floor).
  ais_transport_rich          Table S7, rich11 basis (the recorded negative:
                              held-out weights explode at 2 of 4 cases). It
                              also sourced the appendix's headline density
                              number until phase 6 re-sourced that to the
                              regenerated free-energy certificate.

The two AIS arms differ ONLY by --basis; in the original chains they differed
by a script edit between runs, which is why both invocations look identical in
run_audit_chain.py and run_exactness2.py. The flag exists now, so both arms
are reproducible from one script version.

All four arms are independent, so they run concurrently -- four CUDA contexts,
the documented ceiling on 8 GiB.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase7.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCRIPTS = REPO / "u1_2d" / "scripts"
STATE = REPO / "artifacts" / "gpu_verify" / "state"
CANON = REPO / "out" / "u1_2d"
RKL2 = CANON / "checkpoints" / "score_net_rkl2.pt"

# Parameters recovered verbatim from run_audit_chain.py (MATCHRES_*, AIS) and
# run_exactness2.py (AIS_RICH). Both chains judge on the rkl2 checkpoint.
MATCHRES_CASES = ["16:14.1464", "16:55.0237", "32:55.0237"]
AIS_CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def arms() -> list[tuple[str, list[str]]]:
    ckpt = ["--checkpoint", str(RKL2)]
    return [
        ("MATCHRES_WILSON", [
            PY, str(SCRIPTS / "27_matching_residual.py"), *ckpt,
            "--cases", *MATCHRES_CASES, "--n-configs", "96",
            "--sigma-min-coef", "0.3", "--physics-blend", "0",
            "--out", str(CANON / "matching_residual" / "wilson")]),
        ("MATCHRES_VILLAIN", [
            PY, str(SCRIPTS / "27_matching_residual.py"), *ckpt,
            "--action-type", "villain",
            "--cases", *MATCHRES_CASES, "--n-configs", "96",
            "--sigma-min-coef", "0.3", "--physics-blend", "0",
            "--out", str(CANON / "matching_residual" / "villain")]),
        ("AIS_FINAL7", [
            PY, str(SCRIPTS / "28_ais_transport.py"), *ckpt,
            "--cases", *AIS_CASES, "--n-configs", "96", "--n-bridge", "48",
            "--basis", "final7", "--out", str(CANON / "ais_transport")]),
        ("AIS_RICH11", [
            PY, str(SCRIPTS / "28_ais_transport.py"), *ckpt,
            "--cases", *AIS_CASES, "--n-configs", "96", "--n-bridge", "48",
            "--basis", "rich11", "--out", str(CANON / "ais_transport_rich")]),
    ]


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("PHASE7_START")
    if not RKL2.exists():
        log(f"PHASE7_ABORTED: no rkl2 checkpoint at {RKL2}")
        sys.exit(1)

    env = {**os.environ, "PYTHONUNBUFFERED": "1", "U1_2D_DEVICE": "cuda"}
    pending = [(n, c) for n, c in arms() if not (STATE / f"stage_{n}.done").exists()]
    for name, _ in arms():
        if (STATE / f"stage_{name}.done").exists():
            log(f"STAGE_{name}: sentinel present, skipping")
    if not pending:
        log("PHASE7_DONE (nothing to do)")
        return

    log(f"launching {len(pending)} arms concurrently: {[n for n, _ in pending]}")
    t0 = time.time()
    procs = [(n, subprocess.Popen(c, cwd=REPO, env=env)) for n, c in pending]
    failures = []
    for name, p in procs:
        rc = p.wait()
        dt = (time.time() - t0) / 60
        if rc == 0:
            (STATE / f"stage_{name}.done").write_text(
                f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min wall)\n")
            log(f"STAGE_{name}_DONE ({dt:.1f} min wall)")
        else:
            log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min wall)")
            failures.append(name)

    log(f"PHASE7_DONE_WITH_ERRORS: {failures}" if failures else "PHASE7_DONE")


if __name__ == "__main__":
    main()
