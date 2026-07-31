"""v2 campaign driver: data -> train -> ladder -> studies -> head-to-head -> ESS.

Designed for a detached overnight run on the Snapdragon laptop:
  * every stage is resumable -- a stage that completed writes a sentinel in
    OUT/campaign_state/ and is skipped on relaunch; the underlying scripts also
    skip their own finished work (01 skips existing ensembles, 06 skips
    completed cases via summary.json, 05 --skip-cached reuses benchmarks,
    02 --resume continues from its .resume snapshot);
  * thermal safety: single-process stages run with 6 torch threads; the one
    2-way-parallel window (study seed-2 shard alongside the thermalization
    scan) caps each process at 2 threads. EcoQoS throttling is left ON and no
    priority elevation is used -- the previously validated safe operating point
    (the unthrottle-watcher + parallelism combination caused hardware crashes
    on 2026-07-24 and must not be reintroduced);
  * all output appends to OUT/run.log (the launcher redirects); stage markers
    are STAGE_<NAME>_START / _DONE / _FAILED and the final sentinel is
    CHAIN_DONE or CHAIN_DONE_WITH_ERRORS.

    .venv/Scripts/python.exe diffusion_v2/scripts/run_campaign.py [--smoke]
"""

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CONFIG = "diffusion_v2/configs/v2.yaml"
OUT = REPO / "out" / "diffusion_v2" / "v2"
STATE = OUT / "campaign_state"
GEN_DIR = OUT / "generalization"
THERM_DIR = OUT / "thermalization"
CKPT = "out/diffusion_v2/v2/checkpoints/score_net.pt"
V6_BASELINES = REPO / "out" / "diffusion" / "demo_v6" / "generalization_blend_verify" / "thermalization"

SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], threads: int = 6, critical: bool = False) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {' '.join(cmd)}")
    env = {**os.environ, "DIFFUSION_V2_TORCH_THREADS": str(threads),
           "PYTHONUNBUFFERED": "1"}
    t0 = time.time()
    result = subprocess.run(cmd, cwd=REPO, env=env)
    dt = (time.time() - t0) / 60
    if result.returncode == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"STAGE_{name}_FAILED rc={result.returncode} ({dt:.1f} min)")
    if critical:
        log("CHAIN_FAILED (critical stage)")
        sys.exit(1)
    return False


def run_parallel(stages: list[tuple[str, list[str]]], threads: int = 2) -> list[bool]:
    """The validated 2-way window: each process capped at `threads` torch threads,
    EcoQoS untouched, no priority games."""
    procs = []
    for name, cmd in stages:
        sentinel = STATE / f"stage_{name}.done"
        if sentinel.exists():
            log(f"STAGE_{name}: sentinel present, skipping")
            procs.append((name, None, time.time()))
            continue
        log(f"STAGE_{name}_START (parallel, {threads} threads): {' '.join(cmd)}")
        env = {**os.environ, "DIFFUSION_V2_TORCH_THREADS": str(threads),
               "PYTHONUNBUFFERED": "1"}
        procs.append((name, subprocess.Popen(cmd, cwd=REPO, env=env), time.time()))
    ok = []
    for name, proc, t0 in procs:
        if proc is None:
            ok.append(True)
            continue
        rc = proc.wait()
        dt = (time.time() - t0) / 60
        if rc == 0:
            (STATE / f"stage_{name}.done").write_text(
                f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
            log(f"STAGE_{name}_DONE ({dt:.1f} min)")
            ok.append(True)
        else:
            log(f"STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
            ok.append(False)
    return ok


def s2_case_ids() -> str:
    spec = importlib.util.spec_from_file_location(
        "study06", REPO / "diffusion_v2" / "scripts" / "06_generalization_study.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ids = [c.run_id for c in mod.build_cases(False)
           if c.run_id.startswith(("E_", "F_"))]
    return ",".join(ids)


def copy_caches(src: Path, dst: Path) -> None:
    import shutil
    for sub in ("bases", "reference"):
        s, d = src / sub, dst / sub
        if not s.exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        for f in s.glob("*.pt"):
            target = d / f.name
            if not target.exists():
                shutil.copy2(f, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true",
                        help="tiny end-to-end rehearsal of the whole chain")
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    log(f"CAMPAIGN_START (smoke={args.smoke}) repo={REPO}")

    if args.smoke:
        run_stage("SMOKE_STUDY", [PY, "diffusion_v2/scripts/06_generalization_study.py",
                                  "--smoke", *SAMPLER_FLAGS,
                                  "--checkpoint", "artifacts/diffusion/smoke/checkpoints/score_net.pt",
                                  "--out-dir", str(OUT / "smoke_study")], critical=True)
        run_stage("SMOKE_H2H", [PY, "diffusion_v2/scripts/14_diffusion_vs_instanton_hmc.py",
                                "--config", "diffusion_v2/configs/smoke.yaml",
                                "--checkpoint", "artifacts/diffusion/smoke/checkpoints/score_net.pt",
                                "--smoke", "--out-dir", str(OUT / "smoke_h2h")], critical=True)
        run_stage("SMOKE_ESS", [PY, "diffusion_v2/scripts/15_model_ess.py",
                                "--config", "diffusion_v2/configs/smoke.yaml",
                                "--checkpoint", "artifacts/diffusion/smoke/checkpoints/score_net.pt",
                                "--cases", "16:4.0", "--n-configs", "8",
                                "--ode-steps", "20", "--n-sampler-steps", "24",
                                "--out", str(OUT / "smoke_ess")], critical=True)
        log("CHAIN_DONE (smoke)")
        return

    failures = []

    run_stage("DATA", [PY, "diffusion_v2/scripts/01_generate_data.py",
                       "--config", CONFIG], critical=True)
    run_stage("TRAIN", [PY, "diffusion_v2/scripts/02_train.py",
                        "--config", CONFIG, "--resume"], critical=True)
    if not run_stage("LADDER", [PY, "diffusion_v2/scripts/03_run_ladder.py",
                                "--config", CONFIG]):
        failures.append("LADDER")
    if not run_stage("VALIDATE", [PY, "diffusion_v2/scripts/04_validate.py",
                                  "--config", CONFIG]):
        failures.append("VALIDATE")

    if not run_stage("STUDY_S1", [PY, "diffusion_v2/scripts/06_generalization_study.py",
                                  *SAMPLER_FLAGS, "--seed", "20260730",
                                  "--out-dir", str(GEN_DIR)]):
        failures.append("STUDY_S1")

    if not (STATE / "stage_CACHECOPY.done").exists():
        log("STAGE_CACHECOPY_START")
        copy_caches(GEN_DIR, GEN_DIR / "seeds" / "s2")
        (STATE / "stage_CACHECOPY.done").write_text("done\n")
        log("STAGE_CACHECOPY_DONE")

    therm_cmd = [PY, "diffusion_v2/scripts/05_hmc_thermalization.py",
                 "--config", CONFIG,
                 f"--generalization={GEN_DIR}",
                 "--parts", "A,D,E,F", "--skip-cached",
                 "--checkpoint", CKPT, *SAMPLER_FLAGS,
                 "--out", str(THERM_DIR)]
    if V6_BASELINES.exists():
        therm_cmd += ["--reuse-baselines", str(V6_BASELINES)]
    s2_cmd = [PY, "diffusion_v2/scripts/06_generalization_study.py",
              *SAMPLER_FLAGS, "--seed", "314159",
              "--cases", s2_case_ids(),
              "--out-dir", str(GEN_DIR / "seeds" / "s2")]
    for name, ok in zip(("THERM", "STUDY_S2"),
                        run_parallel([("THERM", therm_cmd), ("STUDY_S2", s2_cmd)])):
        if not ok:
            failures.append(name)

    if not run_stage("HEADTOHEAD", [PY, "diffusion_v2/scripts/14_diffusion_vs_instanton_hmc.py",
                                    "--config", CONFIG]):
        failures.append("HEADTOHEAD")
    if not run_stage("ESS", [PY, "diffusion_v2/scripts/15_model_ess.py",
                             "--config", CONFIG,
                             "--cases", "16:14.1464", "16:55.0237",
                             "32:55.0237", "32:218.58",
                             "--n-configs", "64"]):
        failures.append("ESS")
    if not run_stage("AUTOCORR", [PY, "diffusion_v2/scripts/11_autocorrelation.py",
                                  "--dir", str(THERM_DIR)]):
        failures.append("AUTOCORR")
    if not run_stage("VERDICT", [PY, "diffusion_v2/scripts/12_campaign_verdict.py",
                                 "--study", str(GEN_DIR),
                                 "--out", str(OUT / "verdict")]):
        failures.append("VERDICT")

    if failures:
        log(f"CHAIN_DONE_WITH_ERRORS: {failures}")
    else:
        log("CHAIN_DONE")


if __name__ == "__main__":
    main()
