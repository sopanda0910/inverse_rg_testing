"""Phase 8: the remaining science + the regeneration gaps, both lanes saturated.

TWO LANES, DELIBERATELY
-----------------------
These workloads have opposite bottlenecks, so they are run concurrently rather
than in sequence:

  GPU lane  model-forward dominated (ODE sampling, reverse diffusion, script
            19/06). Measured ~850 MiB per process, so 8 GiB is not the binding
            constraint -- kernel-launch contention is. 3 workers.
  CPU lane  HMC dominated (AIS bridging, L=64 burn-in scans, P(Q) tails). Per
            CLAUDE.md threads make a single HMC process WORSE (154 sweeps/s at
            1 thread, 91 at 12), so this is 6 single-threaded workers, not 1
            six-threaded one.

AIS specifically MUST run on the CPU lane. The CPU arm reproduces the frozen
result exactly (surrogate R^2 0.717 to three decimals, every coefficient
identical); the GPU arm draws a different RNG stream and phase 7's GPU outputs
are therefore not comparable to the results of record. That is not a device
bug -- the ODE draws its initial noise on-device by construction -- but it does
mean CPU is the reproducible arm for this one stage.

WORK
----
  new science      FREEZING     TODO item 1: measure the sigma at which the
                                model stops changing sector, to validate (or
                                refute) charge_projection_sigma = 0.5, which
                                appears in every config and was never swept.
                   FLOOR_*      is the AIS "irreducible floor" real, or an
                                artifact of fitting 7-11 collinear features on
                                48 points? Measures held-out R^2 vs fit size.
  regeneration     CERT_EASY, ODE_EASY, ODE_PROBES8, GEN_SECTORS_*, PQ_TAIL,
                                BURNIN_L64 -- the six pre-campaign directories
                                that no driver ever owned.
  provenance       AIS_FINAL7, AIS_RICH11 on CPU, replacing phase 7's GPU runs.

    .venv/Scripts/python.exe u1_2d/scripts/run_gpu_verification_phase8.py
"""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
SCRIPTS = REPO / "u1_2d" / "scripts"
STATE = REPO / "artifacts" / "gpu_verify" / "state"
CANON = REPO / "out" / "u1_2d"
RKL2 = CANON / "checkpoints" / "score_net_rkl2.pt"

GPU_WORKERS = 3
CPU_WORKERS = 6
AIS_CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def sector_cases(name: str) -> list[str]:
    """The 06 case ids the frozen exact-sector runs actually covered."""
    p = CANON / name / "summary.json"
    if not p.exists():
        return []
    return sorted(json.loads(p.read_text(encoding="utf-8")).keys())


def gpu_jobs() -> list[tuple[str, list[str]]]:
    jobs = [
        ("FREEZING", [PY, str(SCRIPTS / "33_charge_freezing_sigma.py"),
                      "--cases", "16:14.1464", "32:55.0237", "--n-configs", "64"]),
        ("FLOOR_16", [PY, str(SCRIPTS / "34_surrogate_floor_vs_n.py"),
                      "--cases", "16:14.1464", "--n-configs", "768",
                      "--basis", "final7", "rich11",
                      "--out", str(CANON / "surrogate_floor" / "L16")]),
        ("FLOOR_32", [PY, str(SCRIPTS / "34_surrogate_floor_vs_n.py"),
                      "--cases", "32:55.0237", "--n-configs", "384",
                      "--fit-sizes", "24", "48", "96", "192",
                      "--basis", "final7", "rich11",
                      "--out", str(CANON / "surrogate_floor" / "L32")]),
        ("CERT_EASY", [PY, str(SCRIPTS / "19_ode_reweighting.py"),
                       "--checkpoint", str(RKL2), "--cases", "8:2",
                       "--n-configs", "256", "--exact-ref",
                       "--out", str(CANON / "exactness2" / "cert_easy")]),
        ("ODE_EASY", [PY, str(SCRIPTS / "19_ode_reweighting.py"),
                      "--cases", "16:4.44493", "--n-configs", "128",
                      "--out", str(CANON / "ode_reweighting_easy")]),
        ("ODE_PROBES8", [PY, str(SCRIPTS / "19_ode_reweighting.py"),
                         "--cases", "16:14.1464", "--n-configs", "64",
                         "--ode-steps", "240", "--n-probes", "8",
                         "--out", str(CANON / "ode_reweighting_probes8")]),
    ]
    for name, seed in (("generalization_exact_sectors_b", "1696899475"),
                       ("generalization_exact_sectors_seed2", "258239262")):
        cases = sector_cases(name)
        if not cases:
            log(f"SKIP {name}: no frozen summary to recover the case list from")
            continue
        jobs.append((f"SECTORS_{name.split('_')[-1].upper()}",
                     [PY, str(SCRIPTS / "06_generalization_study.py"),
                      "--cases", ",".join(cases), "--seed", seed,
                      "--sector-mode", "exact", "--device", "cuda",
                      "--out-dir", str(CANON / name)]))
    return jobs


def cpu_jobs() -> list[tuple[str, list[str]]]:
    return [
        ("AIS_FINAL7_CPU", [PY, str(SCRIPTS / "28_ais_transport.py"),
                            "--checkpoint", str(RKL2), "--cases", *AIS_CASES,
                            "--n-configs", "96", "--n-bridge", "48",
                            "--basis", "final7",
                            "--out", str(CANON / "ais_transport")]),
        ("AIS_RICH11_CPU", [PY, str(SCRIPTS / "28_ais_transport.py"),
                            "--checkpoint", str(RKL2), "--cases", *AIS_CASES,
                            "--n-configs", "96", "--n-bridge", "48",
                            "--basis", "rich11",
                            "--out", str(CANON / "ais_transport_rich")]),
        # 18 has no --adaptive flag: leaving --n-traj unset IS the adaptive
        # mode (it runs the sector-convergence check up to --max-traj). The
        # non-adaptive sibling directory used a fixed 200-trajectory tail.
        ("PQ_TAIL_ADAPTIVE", [PY, str(SCRIPTS / "18_pq_hmc_tail.py"),
                              "--out", str(CANON / "pq_hmc_tail_adaptive")]),
        ("BURNIN_L64", [PY, str(SCRIPTS / "16_h2h_burnin_scan.py"),
                        "--betas", "55.0237", "--burn-ins", "1600,6400",
                        "--lattice-size", "64", "--n-chains", "16",
                        "--n-prod", "320", "--baseline-summary",
                        str(CANON / "diffusion_vs_instanton" / "L64" / "summary.json"),
                        "--out-dir", str(CANON / "diffusion_vs_instanton" / "L64" / "burnin_scan")]),
    ]


def run_one(name: str, cmd: list[str], lane: str) -> tuple[str, bool, float]:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"{lane} {name}: sentinel present, skipping")
        return name, True, 0.0
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if lane == "GPU":
        env["U1_2D_DEVICE"] = "cuda"
        env.pop("U1_2D_TORCH_THREADS", None)
    else:
        env["U1_2D_DEVICE"] = "cpu"
        env["U1_2D_TORCH_THREADS"] = "1"
    log(f"{lane} {name}: START")
    t0 = time.time()
    log_path = CANON / "gpu_verification" / f"phase8_{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as fh:
        rc = subprocess.run(cmd, cwd=REPO, env=env, stdout=fh,
                            stderr=subprocess.STDOUT).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"{lane} {name}: DONE ({dt:.1f} min)")
        return name, True, dt
    log(f"{lane} {name}: FAILED rc={rc} ({dt:.1f} min) -- see {log_path.name}")
    return name, False, dt


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("PHASE8_START")
    if not RKL2.exists():
        log(f"PHASE8_ABORTED: no rkl2 checkpoint at {RKL2}")
        sys.exit(1)

    gpu, cpu = gpu_jobs(), cpu_jobs()
    log(f"GPU lane: {len(gpu)} jobs across {GPU_WORKERS} workers -> {[n for n, _ in gpu]}")
    log(f"CPU lane: {len(cpu)} jobs across {CPU_WORKERS} workers -> {[n for n, _ in cpu]}")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=GPU_WORKERS) as gpu_pool, \
         ThreadPoolExecutor(max_workers=CPU_WORKERS) as cpu_pool:
        futures = [gpu_pool.submit(run_one, n, c, "GPU") for n, c in gpu]
        futures += [cpu_pool.submit(run_one, n, c, "CPU") for n, c in cpu]
        results = [f.result() for f in futures]

    failures = [n for n, ok, _ in results if not ok]
    log(f"PHASE8 wall clock: {(time.time() - t0) / 60:.1f} min")
    log(f"PHASE8_DONE_WITH_ERRORS: {failures}" if failures else "PHASE8_DONE")


if __name__ == "__main__":
    main()
