"""Exactness suite: frontier scan + low-beta regression check + SMC ladder.

Stages (sentinels in OUT/ess_chain/exactness_state/, resumable):

  FRONTIER_RKL2  script 19 --exact-ref with score_net_rkl2.pt over a (L, beta)
                 grid at n = 256: maps where valid-weight reweighting and
                 independence-MH are already usable (small volume / low beta)
                 and z-scores every estimator against exact references.
  FRONTIER_V2    the original campaign checkpoint on the low-beta subset:
                 rkl2's fine-tune only guarded beta >= 10, so this checks the
                 unguarded low-beta region for regressions.
  SMC            script 24: per-level weights + systematic resampling up the
                 production ladder (8:1.35 -> 16:4 -> 32:14.15), two arms.
  REPORT         exactness_report.md merging the key numbers.

    .venv/Scripts/python.exe u1_2d/scripts/run_exactness_suite.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "u1_2d" / "scripts"
V2OUT = REPO / "out" / "u1_2d"
OUT = V2OUT / "ess_chain"
STATE = OUT / "exactness_state"
RKL2 = V2OUT / "checkpoints" / "score_net_rkl2.pt"

FRONTIER_CASES = ["8:2.0", "8:4.0", "8:8.0", "8:14.1464",
                  "16:4.0", "16:8.0", "16:14.1464", "16:25.0", "16:55.0237"]
LOWBETA_CASES = ["8:2.0", "8:4.0", "8:14.1464", "16:4.0", "16:14.1464"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], critical: bool = True) -> bool:
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


def summarize() -> None:
    lines = ["# Exactness suite report", ""]
    for title, path in (
        ("Frontier (rkl2 checkpoint)", OUT / "frontier_rkl2" / "reweighting_results.json"),
        ("Low-beta check (original v2 checkpoint)", OUT / "frontier_v2" / "reweighting_results.json"),
    ):
        lines += [f"## {title}", "",
                  "| case | ESS/N (fiber) | log-w std | i-MH acc | z(raw) plaq | z(rw) plaq | z(raw) Q^2 | z(rw) Q^2 |",
                  "|------|---------------|-----------|----------|-------------|------------|------------|-----------|"]
        if path.exists():
            for r in json.loads(path.read_text()):
                obs = r["observables"]
                def z(name, key):
                    v = obs.get(name, {}).get(key)
                    return f"{v:+.1f}" if isinstance(v, float) else "--"
                lines.append(
                    f"| {r['fine_L']}:{r['fine_beta']:g} | {r.get('ess_per_n_fiber', 0):.3f} | "
                    f"{r.get('log_weight_std_fiber', 0):.1f} | {r.get('imh_acceptance', 0):.2f} | "
                    f"{z('plaquette', 'z_raw')} | {z('plaquette', 'z_reweighted')} | "
                    f"{z('Q^2', 'z_raw')} | {z('Q^2', 'z_reweighted')} |"
                )
        else:
            lines.append("| -- | -- | -- | -- | -- | -- | -- | -- |")
        lines.append("")
    smc = OUT / "smc_ladder" / "report.md"
    if smc.exists():
        lines += ["## SMC ladder", ""] + smc.read_text(encoding="utf-8").splitlines()[2:]
    (OUT / "exactness_report.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"report: {OUT / 'exactness_report.md'}")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    run_stage("FRONTIER_RKL2", [
        sys.executable, str(SCRIPTS / "19_ode_reweighting.py"),
        "--checkpoint", str(RKL2), "--exact-ref", "--n-configs", "256",
        "--cases", *FRONTIER_CASES, "--out", str(OUT / "frontier_rkl2"),
    ])
    run_stage("FRONTIER_V2", [
        sys.executable, str(SCRIPTS / "19_ode_reweighting.py"),
        "--exact-ref", "--n-configs", "256",
        "--cases", *LOWBETA_CASES, "--out", str(OUT / "frontier_v2"),
    ], critical=False)
    run_stage("SMC", [
        sys.executable, str(SCRIPTS / "24_smc_ladder.py"), "--n-configs", "192",
    ], critical=False)
    summarize()
    log("CHAIN_DONE")


if __name__ == "__main__":
    main()
