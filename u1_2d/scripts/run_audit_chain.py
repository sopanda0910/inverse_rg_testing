"""Post-audit chain: repairs, decomposition science, AIS transport, hardening.

Stages (sentinels in out/u1_2d/audit_chain/state/, resumable):

  PYTEST            full test suite incl. the audit-added exactness pins (critical)
  REBUILD_MATCHING  repair data/matching.json (B6: overwritten by the scale-up
                    run) by recomputing entries from every ensemble on disk
  MATCHRES_WILSON   script 27, Wilson, blend-free at the TRAINED sigma floor
                    (0.3): the clean arm of the Villain subtraction (blend-free
                    sampling below the trained floor would measure the
                    extrapolation artifact, not the model)
  MATCHRES_VILLAIN  script 27 --action-type villain, same settings: beta/4
                    matching is EXACT there, so the Villain spread is pure
                    model error; Wilson minus Villain isolates the matching
                    floor. Deployment-settings decomposition (blend on,
                    sigmin 0.03) comes free from the AIS stage's samples.
  AIS               script 28: surrogate-bridge AIS correction of ODE
                    transport -- the one untried mechanism (audit section 6.1)
  VALIDATE          script 04 rerun: tau_int-aware errors, n_eff p-values,
                    raw pre-enforcement pass, frozen-reference flags
  VERDICT           script 12 rerun (B7: close the log of record cleanly;
                    +inf Q^2 footnote now emitted by the generator)
  GEN_FRESH_S3/S4   script 06 fresh-seed reruns of the >3 sigma Wilson cases
                    (D_bc14.1464 both-fail is the priority) to classify
                    fluctuation vs real
  H2H_L64           script 14 at L = 64 (beta 55.0237, 218.58): first
                    L-scaling point for the head-to-head cost claims
  SUMMARY           audit_chain/report.md merging the key numbers

    .venv/Scripts/python.exe u1_2d/scripts/run_audit_chain.py
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
OUT = V2OUT / "audit_chain"
STATE = OUT / "state"
RKL2 = V2OUT / "checkpoints" / "score_net_rkl2.pt"

CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]


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


def summarize(failures: list[str]) -> None:
    lines = ["# Audit chain report", ""]
    if failures:
        lines += [f"Stages failed: {', '.join(failures)}", ""]

    for title, path in (
        ("Matching residual -- Wilson", V2OUT / "matching_residual" / "wilson" / "report.md"),
        ("Matching residual -- Villain control", V2OUT / "matching_residual" / "villain" / "report.md"),
        ("AIS-corrected transport", V2OUT / "ais_transport" / "report.md"),
    ):
        if path.exists():
            lines += [f"## {title}", ""] + path.read_text(encoding="utf-8").splitlines()[2:] + [""]

    wilson = V2OUT / "matching_residual" / "wilson" / "results.json"
    villain = V2OUT / "matching_residual" / "villain" / "results.json"
    if wilson.exists() and villain.exists():
        w = {(r["fine_L"], round(r["fine_beta"], 3)): r for r in json.loads(wilson.read_text())}
        v = {(r["fine_L"], round(r["fine_beta"], 3)): r for r in json.loads(villain.read_text())}
        lines += ["## Wilson minus Villain (matching floor by construction)", "",
                  "| L | beta_f | wilson std/site | villain std/site | difference |",
                  "|---|--------|-----------------|------------------|------------|"]
        for key in sorted(set(w) & set(v)):
            dw, dv = w[key]["per_site_std"], v[key]["per_site_std"]
            lines.append(f"| {key[0]} | {key[1]:g} | {dw:.4f} | {dv:.4f} | {dw - dv:+.4f} |")
        lines.append("")

    for title, path in (
        ("Validation report (tau_int-aware, raw pass)", V2OUT / "validation" / "report.md"),
        ("Campaign verdict (rerun)", V2OUT / "verdict" / "verdict.md"),
        ("L=64 head-to-head", V2OUT / "diffusion_vs_instanton" / "L64" / "report.md"),
    ):
        lines.append(f"- {title}: `{path.relative_to(REPO)}`"
                     + ("" if path.exists() else " (MISSING)"))
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"report: {OUT / 'report.md'}")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    failures = []

    def stage(name, cmd, critical=False):
        if not run_stage(name, cmd, critical=critical):
            failures.append(name)

    ckpt = ["--checkpoint", str(RKL2)] if RKL2.exists() else []
    if not ckpt:
        log(f"WARNING: {RKL2} missing; scripts 27/28 fall back to the config checkpoint")

    stage("PYTEST", [sys.executable, "-m", "pytest", "u1_2d/tests", "-q"], critical=True)
    stage("REBUILD_MATCHING", [
        sys.executable, str(SCRIPTS / "01_generate_data.py"),
        "--config", "u1_2d/configs/v2.yaml", "--rebuild-matching",
    ])
    control_cases = ["16:14.1464", "16:55.0237", "32:55.0237"]
    stage("MATCHRES_WILSON", [
        sys.executable, str(SCRIPTS / "27_matching_residual.py"), *ckpt,
        "--cases", *control_cases, "--n-configs", "96",
        "--sigma-min-coef", "0.3", "--physics-blend", "0",
        "--out", str(V2OUT / "matching_residual" / "wilson"),
    ])
    stage("MATCHRES_VILLAIN", [
        sys.executable, str(SCRIPTS / "27_matching_residual.py"), *ckpt,
        "--action-type", "villain", "--cases", *control_cases, "--n-configs", "96",
        "--sigma-min-coef", "0.3", "--physics-blend", "0",
        "--out", str(V2OUT / "matching_residual" / "villain"),
    ])
    stage("AIS", [
        sys.executable, str(SCRIPTS / "28_ais_transport.py"), *ckpt,
        "--cases", *CASES, "--n-configs", "96", "--n-bridge", "48",
        "--out", str(V2OUT / "ais_transport"),
    ])
    stage("VALIDATE", [
        sys.executable, str(SCRIPTS / "04_validate.py"),
        "--config", "u1_2d/configs/v2.yaml",
    ])
    stage("VERDICT", [
        sys.executable, str(SCRIPTS / "12_campaign_verdict.py"),
        "--study", str(V2OUT / "generalization"),
        "--out", str(V2OUT / "verdict"),
    ])
    for seed, tag in ((20260803, "S3"), (20260804, "S4")):
        stage(f"GEN_FRESH_{tag}", [
            sys.executable, str(SCRIPTS / "06_generalization_study.py"),
            "--cases", "D_bc14.1464,B_bt20,A_bc8,F_L64_bc55.0237",
            "--seed", str(seed),
            "--out-dir", str(V2OUT / f"generalization_fresh_{tag.lower()}"),
        ])
    stage("H2H_L64", [
        sys.executable, str(SCRIPTS / "14_diffusion_vs_instanton_hmc.py"),
        "--betas", "55.0237,218.58", "--lattice-size", "64",
        "--n-chains", "16", "--burn-in", "400", "--n-prod", "320", "--n-gen", "96",
        "--out-dir", str(V2OUT / "diffusion_vs_instanton" / "L64"),
    ])

    summarize(failures)
    log(f"CHAIN_DONE_WITH_ERRORS: {failures}" if failures else "CHAIN_DONE")


if __name__ == "__main__":
    main()
