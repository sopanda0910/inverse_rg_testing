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
# Shard counts are VRAM-bounded, not core-bounded: every concurrent process
# carries its own CUDA context plus the score net (~0.5-0.7 GiB of 8 GiB). Four
# shards plus the four-way concurrent group never overlap in this driver.
SECTOR_SHARDS = 4
# Generous because phase 2's THERM is the long pole and was badly misjudged:
# measured ~28 min/case over 29 cases (~13.5 h), not the 1-2 h first estimated.
# It computes its own hot/cold baselines (32 chains x 640 trajectories each) --
# the original campaign passed --reuse-baselines and skipped that entirely, which
# is why its 297 min is not a comparable number.
WAIT_TIMEOUT_H = 36.0


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


def run_concurrent(stages: list[tuple[str, list[str]]], device: str | None = None) -> list[str]:
    """Run independent stages at once; return the names that failed.

    Each still gets its own sentinel, so a partial failure re-runs only the
    stages that did not finish.
    """
    pending = [(n, c) for n, c in stages if not (STATE / f"stage_{n}.done").exists()]
    for name, _ in stages:
        if (STATE / f"stage_{name}.done").exists():
            log(f"STAGE_{name}: sentinel present, skipping")
    if not pending:
        return []
    log(f"CONCURRENT_START: {', '.join(n for n, _ in pending)}")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if device:
        env["U1_2D_DEVICE"] = device
    t0 = time.time()
    procs = [(n, subprocess.Popen(c, cwd=REPO, env=env)) for n, c in pending]
    failed = []
    for name, proc in procs:
        rc = proc.wait()
        if rc == 0:
            (STATE / f"stage_{name}.done").write_text(
                f"done {time.strftime('%Y-%m-%d %H:%M:%S')} (concurrent)\n")
            log(f"STAGE_{name}_DONE")
        else:
            log(f"STAGE_{name}_FAILED rc={rc}")
            failed.append(name)
    log(f"CONCURRENT_DONE ({(time.time()-t0)/60:.1f} min)")
    return failed


def run_sharded_stage(name: str, base_args: list[str], n_shards: int) -> bool:
    """A --shard/--merge-shards stage (06). See shard_runner.py for the contract."""
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"STAGE_{name}: sentinel present, skipping")
        return True
    log(f"STAGE_{name}_START: {n_shards} shards")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    t0 = time.time()
    procs = [subprocess.Popen([*base_args, "--shard", f"{i}/{n_shards}"],
                              cwd=REPO, env=env) for i in range(n_shards)]
    if any(p.wait() for p in procs):
        log(f"STAGE_{name}_FAILED in shards ({(time.time()-t0)/60:.1f} min)")
        return False
    if subprocess.run([*base_args, "--merge-shards"], cwd=REPO, env=env).returncode != 0:
        log(f"STAGE_{name}_FAILED at merge")
        return False
    dt = (time.time() - t0) / 60
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({dt:.1f} min, {n_shards} shards)\n")
    log(f"STAGE_{name}_DONE ({dt:.1f} min)")
    return True


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
    # The training ensembles, too. run_ess_chain calls 20/21 with no --config,
    # so they resolve data.out_dir through v2.yaml to out/u1_2d/data -- while
    # this run generated into artifacts/gpu_verify/data. Without this the
    # likelihood fine-tune dies on "no rungs with beta >= 10.0 under
    # out\u1_2d\data" and takes FIG_23 and FIG_26 down with it. 33 MB.
    data_src = REPO / "artifacts" / "gpu_verify" / "data"
    if data_src.exists():
        data_dst = CANON / "data"
        data_dst.mkdir(parents=True, exist_ok=True)
        for f in data_src.iterdir():
            if f.is_file():
                shutil.copy2(f, data_dst / f.name)
        log(f"  data -> {data_dst} ({len(list(data_dst.glob('*.pt')))} ensembles)")
    invalidate_downstream()
    sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log("STAGE_PROMOTE_DONE")
    return True


def invalidate_downstream() -> None:
    """Delete results computed from the checkpoint we just replaced.

    Every stage after PROMOTE is resumable against its OWN cache, independently
    of this driver's sentinels: run_ess_chain keeps chain_state/stage_*.done,
    run_ode_sweep skips any point with reweighting_results.json, 06 skips cases
    whose summary.json entry has "rows", 16 reuses its burnin_scan output. Those
    caches survive PROMOTE, so without this every one of them looks complete and
    the stage exits in seconds -- reporting success while the figures quietly
    rebuild from the previous checkpoint's numbers. That is exactly what
    happened on the 18:35 run: SECTOR_STUDY "finished" in 0.4 min, ODE_SWEEP and
    ESS_CHAIN in 0.0, against results dated 2026-08-01.

    Promoting a checkpoint invalidates everything derived from the old one, so
    this is a correctness requirement, not an optimization.

    Kept deliberately: bases/ and reference/ ensembles are direct HMC and carry
    no model dependence, so they stay and save real time.
    """
    log("  invalidating caches derived from the previous checkpoint")
    for rel in ("ess_chain", "diffusion_vs_instanton/burnin_scan"):
        path = CANON / rel
        if path.exists():
            shutil.rmtree(path)
            log(f"    removed {rel}")
    for point in sorted((CANON / "ode_reweighting_sweep").glob("*/reweighting_results.json")):
        point.unlink()
    log("    cleared ode_reweighting_sweep point results")
    sec = CANON / "generalization_exact_sectors"
    for sub in ("summary.json",):
        if (sec / sub).exists():
            (sec / sub).unlink()
            log(f"    removed generalization_exact_sectors/{sub}")
    gen = sec / "generated"
    if gen.exists():
        shutil.rmtree(gen)
        log("    removed generalization_exact_sectors/generated")


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
    #
    # GROUP 1 -- mutually independent, so run concurrently. Each reads only the
    # checkpoint and writes its own output directory; none consumes another's
    # result. Serially these are ~2 h of mostly-idle machine (a single-threaded
    # dispatcher against a GPU that sits at 5-30% on these batch sizes), so
    # overlapping them is close to free.
    #
    # --out/--out-dir are passed EXPLICITLY and are not optional. Both 14 and 15
    # default to `Path(config["validate"]["out_dir"]).parent / <name>`, which
    # under v2_gpu_verify.yaml resolves to out/u1_2d/gpu_verification/ -- while
    # 17 and 26 read the canonical out/u1_2d/<name>. Left to the defaults these
    # stages write somewhere the figure scripts never look, and the figures
    # silently rebuild from the OLD frozen data instead.
    group1 = [
        ("HEADTOHEAD", [PY, "u1_2d/scripts/14_diffusion_vs_instanton_hmc.py",
                        "--config", CONFIG,
                        "--out-dir", str(CANON / "diffusion_vs_instanton")]),
        ("ESS", [PY, "u1_2d/scripts/15_model_ess.py", "--config", CONFIG,
                 "--cases", *CASES, "--n-configs", "64",
                 "--out", str(CANON / "model_ess")]),
        ("ESS_NOGUIDE", [PY, "u1_2d/scripts/15_model_ess.py", "--config", CONFIG,
                         "--cases", *CASES, "--n-configs", "64",
                         "--consistency-weight", "0.0",
                         "--out", str(CANON / "model_ess_noguide")]),
        # The deployment-knob ODE reweighting baseline. Figures 23 and 26 both
        # read out/u1_2d/ode_reweighting/reweighting_results.json (26 labels it
        # "v2 ckpt, ladder knobs"), and nothing else in this driver produces it
        # -- run_ess_chain's 19 invocations write to ess_chain/verify_*. Without
        # this the baseline series in those figures stays on the old checkpoint.
        # Parameters recovered from the frozen result: 4 cases, n=64,
        # ode_steps=120, n_probes=2. Note 19 spells the noise floor
        # --sigma-min-coef, not --sigma-floor-coef, so SAMPLER_FLAGS cannot be
        # spread here verbatim.
        ("ODE_BASELINE", [PY, "u1_2d/scripts/19_ode_reweighting.py",
                          "--config", CONFIG, "--cases", *CASES,
                          "--n-configs", "64", "--ode-steps", "120",
                          "--n-probes", "2",
                          "--physics-blend", "1.0",
                          "--physics-blend-beta-min", "5.0",
                          "--sigma-min-coef", "0.1",
                          "--out", str(CANON / "ode_reweighting")]),
    ]
    failures += run_concurrent(group1, device="cuda")

    # NOT in group 1: 16 reads --baseline-summary, which defaults to
    # out/u1_2d/diffusion_vs_instanton/summary.json -- HEADTOHEAD's output. Run
    # concurrently it would race, reading either the previous campaign's summary
    # or a half-written one.
    if not run_stage("BURNIN_SCAN", [PY, "u1_2d/scripts/16_h2h_burnin_scan.py",
                                     "--config", CONFIG], device="cuda"):
        failures.append("BURNIN_SCAN")

    # SECTOR_STUDY is 06 again (exact-sector arm, figure 20), so it shards the
    # same way the main study does.
    sector_args = [PY, "u1_2d/scripts/06_generalization_study.py",
                   *SAMPLER_FLAGS, "--seed", "20260730", "--device", "cuda",
                   "--symmetrize-base", "--sector-mode", "exact",
                   "--out-dir", str(CANON / "generalization_exact_sectors")]
    if not run_sharded_stage("SECTOR_STUDY", sector_args, SECTOR_SHARDS):
        failures.append("SECTOR_STUDY")

    # GROUP 2 -- ordered. PQ_TAIL reads the generalization output; the Tier-0
    # sweep must precede the ESS chain because run_ess_chain picks its knobs
    # from sweep_summary.md and blocks waiting for it otherwise.
    for name, cmd, dev in [
        ("PQ_TAIL", [PY, "u1_2d/scripts/18_pq_hmc_tail.py", "--device", "cuda",
                     "--gen-dir", str(CANON / "generalization"),
                     "--n-traj", "200"], None),
        ("ODE_SWEEP", [PY, "u1_2d/scripts/run_ode_sweep.py"], "cuda"),
        ("ESS_CHAIN", [PY, "u1_2d/scripts/run_ess_chain.py"], "cuda"),
        ("VERDICT", [PY, "u1_2d/scripts/12_campaign_verdict.py",
                     "--study", str(CANON / "generalization"),
                     "--out", str(CANON / "verdict")], None),
    ]:
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
