"""Exactness follow-up chain: the fixes scripted from the first audit-chain
results (2026-08-02 evening).

Stages (sentinel-resumable, state in out/u1_2d/exactness2/state/):

  WAIT_AUDIT   poll until the audit chain's CHAIN_DONE (never run two heavy
               chains at once -- the July-24 crash recipe was parallelism)
  CERT_EASY    script 19 at an easy case (8:2, n=256) where ESS is healthy:
               the free-energy certificate gap must close there, validating
               the whole weight chain + log_partition conventions on the real
               model (the unit test validates them on synthetic weights)
  AIS_RICH     script 28 rerun: 11-feature surrogate basis (adds W22, cos 4p,
               plaquette nn-correlator, blocked 3rd character -- the measured
               AIS floor equals the surrogate residual, so basis width is THE
               lever), sector-resolved plaquette estimates (within-sector SNIS
               x exact P(Q)), KL-measurement fields, per-half diagnostics for
               the 16:14 held-out anomaly
  BURNIN_L64   script 16 at L=64 beta=55.0237: burn-in scan 1600/6400 vs the
               baseline 400 that left instanton-HMC ~10 sigma biased -- turns
               the suspicious head-to-head arm into the entry-cost measurement

    .venv/Scripts/python.exe u1_2d/scripts/run_exactness2.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "u1_2d" / "scripts"
V2OUT = REPO / "out" / "u1_2d"
OUT = V2OUT / "exactness2"
STATE = OUT / "state"
RKL2 = V2OUT / "checkpoints" / "score_net_rkl2.pt"
AUDIT_LOG = V2OUT / "audit_chain" / "chain.log"


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {' '.join(cmd)}")
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env={**os.environ, "PYTHONUNBUFFERED": "1"}).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("CHAIN_FAILED (critical stage)")
        sys.exit(1)
    return False


def wait_for_audit_chain() -> None:
    sentinel = STATE / "stage_WAIT_AUDIT.done"
    if sentinel.exists():
        return
    while True:
        if AUDIT_LOG.exists() and "CHAIN_DONE" in AUDIT_LOG.read_text(encoding="utf-8", errors="replace"):
            break
        log("waiting for audit chain CHAIN_DONE ...")
        time.sleep(120)
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log("STAGE_WAIT_AUDIT_DONE")


def summarize(failures: list[str]) -> None:
    lines = ["# Exactness follow-up report", ""]
    if failures:
        lines += [f"Stages failed: {', '.join(failures)}", ""]
    for title, path in (
        ("Certificate closure at healthy ESS (8:2)",
         V2OUT / "exactness2" / "cert_easy" / "report.md"),
        ("AIS with rich basis + sector resolution",
         V2OUT / "ais_transport_rich" / "report.md"),
    ):
        if path.exists():
            lines += [f"## {title}", ""] + path.read_text(encoding="utf-8").splitlines()[2:] + [""]
        else:
            lines += [f"## {title}", "", "(MISSING)", ""]
    scan = V2OUT / "diffusion_vs_instanton" / "L64" / "burnin_scan"
    lines.append(f"- L=64 burn-in scan: `{(scan / 'report.md').relative_to(REPO)}`"
                 + ("" if (scan / "report.md").exists() else " (MISSING)"))
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"report: {OUT / 'report.md'}")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    failures = []

    def stage(name, cmd, critical=False):
        if not run_stage(name, cmd, critical=critical):
            failures.append(name)

    wait_for_audit_chain()
    ckpt = ["--checkpoint", str(RKL2)] if RKL2.exists() else []

    stage("CERT_EASY", [
        sys.executable, str(SCRIPTS / "19_ode_reweighting.py"), *ckpt,
        "--cases", "8:2", "--n-configs", "256", "--exact-ref",
        "--out", str(OUT / "cert_easy"),
    ])
    stage("AIS_RICH", [
        sys.executable, str(SCRIPTS / "28_ais_transport.py"), *ckpt,
        "--cases", "16:14.1464", "16:55.0237", "32:55.0237", "32:218.58",
        "--n-configs", "96", "--n-bridge", "48",
        "--out", str(V2OUT / "ais_transport_rich"),
    ])
    stage("BURNIN_L64", [
        sys.executable, str(SCRIPTS / "16_h2h_burnin_scan.py"),
        "--betas", "55.0237", "--burn-ins", "1600,6400",
        "--lattice-size", "64", "--n-chains", "16", "--n-prod", "320",
        "--baseline-summary",
        str(V2OUT / "diffusion_vs_instanton" / "L64" / "summary.json"),
        "--out-dir", str(V2OUT / "diffusion_vs_instanton" / "L64" / "burnin_scan"),
    ])

    summarize(failures)
    log(f"CHAIN_DONE_WITH_ERRORS: {failures}" if failures else "CHAIN_DONE")


if __name__ == "__main__":
    main()
