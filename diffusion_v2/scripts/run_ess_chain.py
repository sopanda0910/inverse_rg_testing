"""ESS improvement chain: Tier-0 knobs -> Tier-2 ML fine-tune -> Tier-3 reverse KL.

Stages (each writes a sentinel in OUT/chain_state/ and is skipped on relaunch):

  SWEEP_WAIT   wait for the Tier-0 sweep summary (the sweep normally runs as a
               separate process); after a timeout, run the sweep driver here
               (it skips finished points, so this is safe after a crash --
               but do NOT start it while another sweep process is live).
  MLFT         Tier 2: 20_likelihood_finetune.py with the sweep's best knobs
               -> checkpoints/score_net_mlft.pt
  VERIFY_MLFT  19_ode_reweighting.py --checkpoint mlft on the standard cases
  RKLFT        Tier 3: 21_reverse_kl_finetune.py warm-started from mlft
               -> checkpoints/score_net_rklft.pt (only saved on ESS gain)
  VERIFY_RKLFT 19_ode_reweighting.py --checkpoint rklft (skipped if Tier 3
               never improved ESS and thus never saved)
  REPORT       chain_report.md comparing baseline / mlft / rklft per case

Knob selection: best ess_per_n_fiber over the sweep's non-stability points,
ties broken by lower log-weight std; the chosen sampling-time knobs are used
consistently for training AND all verification runs (one proposal family).

    .venv/Scripts/python.exe diffusion_v2/scripts/run_ess_chain.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "diffusion_v2" / "scripts"
V2OUT = REPO / "out" / "diffusion_v2"
OUT = V2OUT / "ess_chain"
STATE = OUT / "chain_state"
SWEEP_DIR = V2OUT / "ode_reweighting_sweep"
CASES = ["16:14.1464", "16:55.0237", "32:55.0237", "32:218.58"]
TIER3_CASE = "16:55.0237"
SWEEP_WAIT_TIMEOUT_S = 3600
STABILITY_POINTS = {"probes8", "steps240"}

_spec = importlib.util.spec_from_file_location("ode_sweep", SCRIPTS / "run_ode_sweep.py")
_sweep_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sweep_mod)
SWEEP_POINTS = dict(_sweep_mod.POINTS)


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


def wait_for_sweep() -> None:
    summary = SWEEP_DIR / "sweep_summary.md"
    t0 = time.time()
    while not summary.exists():
        if time.time() - t0 > SWEEP_WAIT_TIMEOUT_S:
            log("sweep summary missing after timeout; running sweep driver inline")
            run_stage("SWEEP_INLINE", [sys.executable, str(SCRIPTS / "run_ode_sweep.py")])
            return
        log("waiting for Tier-0 sweep summary ...")
        time.sleep(60)
    log(f"sweep summary present: {summary}")


def best_sweep_knobs() -> tuple[str, list[str], dict]:
    rows = []
    for label in SWEEP_POINTS:
        if label in STABILITY_POINTS:
            continue
        f = SWEEP_DIR / label / "reweighting_results.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())[0]
        rows.append((label, r))
    if not rows:
        raise SystemExit("no sweep results found")
    rows.sort(key=lambda t: (-(t[1].get("ess_per_n_fiber") or 0.0),
                             t[1].get("log_weight_std_fiber") or 1e9))
    label, r = rows[0]
    log(f"best sweep point: {label} "
        f"(ESS/N fiber {r.get('ess_per_n_fiber'):.4f}, "
        f"log-w std {r.get('log_weight_std_fiber'):.2f})")
    return label, list(SWEEP_POINTS[label]), r


def collect_case_rows(result_file: Path) -> dict:
    if not result_file.exists():
        return {}
    out = {}
    for r in json.loads(result_file.read_text()):
        key = f"{r['fine_L']}:{r['fine_beta']:g}"
        out[key] = r
    return out


def write_report(knob_label: str, knob_args: list[str]) -> None:
    variants = [
        ("baseline (pre-chain knobs)", V2OUT / "ode_reweighting" / "reweighting_results.json"),
        (f"sweep-best knobs [{knob_label}]", SWEEP_DIR / knob_label / "reweighting_results.json"),
        ("mlft (Tier 2)", OUT / "verify_mlft" / "reweighting_results.json"),
        ("rklft (Tier 3)", OUT / "verify_rklft" / "reweighting_results.json"),
    ]
    lines = [
        "# ESS chain report",
        "",
        f"Knobs used from sweep point `{knob_label}`: `{' '.join(knob_args) or '(defaults)'}`",
        "",
        "| variant | case | ESS/N (fiber) | log-w std (fiber) | i-MH acc |",
        "|---------|------|---------------|-------------------|----------|",
    ]
    for name, f in variants:
        rows = collect_case_rows(f)
        if not rows:
            lines.append(f"| {name} | -- | -- | -- | -- |")
            continue
        for key, r in rows.items():
            fib = r.get("ess_per_n_fiber")
            std = r.get("log_weight_std_fiber")
            fib_s = f"{fib:.4f}" if fib is not None else "--"
            std_s = f"{std:.2f}" if std is not None else "--"
            lines.append(f"| {name} | {key} | {fib_s} | {std_s} | "
                         f"{r.get('imh_acceptance', float('nan')):.2f} |")
    lines += [
        "",
        "baseline row = original run with pre-sweep default knobs; sweep-best",
        "row isolates the knob-only gain (same checkpoint); mlft adds Tier-2",
        "ML fine-tuning; rklft adds Tier-3 reverse-KL on top of mlft.",
        "Success metric: log-w std (fiber) down, ESS/N and i-MH acceptance up.",
    ]
    (OUT / "chain_report.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"report: {OUT / 'chain_report.md'}")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    ckpt_dir = V2OUT / "checkpoints"
    mlft = ckpt_dir / "score_net_mlft.pt"
    rklft = ckpt_dir / "score_net_rklft.pt"

    wait_for_sweep()
    knob_label, knob_args, _ = best_sweep_knobs()
    (OUT / "chosen_knobs.json").write_text(
        json.dumps({"label": knob_label, "args": knob_args}), encoding="utf-8"
    )

    run_stage("MLFT", [
        sys.executable, str(SCRIPTS / "20_likelihood_finetune.py"),
        "--steps", "300", "--eval-every", "50",
        "--out-checkpoint", str(mlft), *knob_args,
    ])
    run_stage("VERIFY_MLFT", [
        sys.executable, str(SCRIPTS / "19_ode_reweighting.py"),
        "--checkpoint", str(mlft), "--cases", *CASES,
        "--out", str(OUT / "verify_mlft"), *knob_args,
    ])
    run_stage("RKLFT", [
        sys.executable, str(SCRIPTS / "21_reverse_kl_finetune.py"),
        "--checkpoint", str(mlft), "--out-checkpoint", str(rklft),
        "--case", TIER3_CASE, "--steps", "200", *knob_args,
    ], critical=False)
    if rklft.exists():
        run_stage("VERIFY_RKLFT", [
            sys.executable, str(SCRIPTS / "19_ode_reweighting.py"),
            "--checkpoint", str(rklft), "--cases", *CASES,
            "--out", str(OUT / "verify_rklft"), *knob_args,
        ], critical=False)
    else:
        log("Tier 3 never improved eval ESS (no rklft checkpoint); skipping its verification")

    write_report(knob_label, knob_args)
    log("CHAIN_DONE")


if __name__ == "__main__":
    main()
