"""Norm-ablation chain: retrain with GroupNorm, rerun a targeted 06 subset, compare.

Attribution experiment for the mid-beta Wilson-loop undershoot in the v2 seed-1
study: everything identical to v2.yaml except train.norm_type: group. Reuses the
v2 data ensembles and the main study's bases/references, so the chain is ~2 h of
training plus ~1-2 h of study cases. Independent sampler noise (seed 777) per
the CLAUDE.md checkpoint-comparison rules; raw pre-enforcement topology metrics
are the topology yardstick.

    .venv/Scripts/python.exe diffusion_v2/scripts/run_ablation.py
"""

import json
import math
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CONFIG = "diffusion_v2/configs/v2_ablate_norm.yaml"
OUT = REPO / "out" / "diffusion_v2" / "v2_ablate_norm"
STATE = OUT / "campaign_state"
GEN_DIR = OUT / "generalization"
MAIN_GEN = REPO / "out" / "diffusion_v2" / "generalization"
CKPT = "out/diffusion_v2/v2_ablate_norm/checkpoints/score_net.pt"
SAMPLER_FLAGS = ["--physics-blend", "1.0", "--physics-blend-beta-min", "5.0",
                 "--sigma-floor-coef", "0.1"]
# The undershoot band plus controls: mid-beta A cases, the worst D cases, mid E,
# and two low-beta topology controls to confirm the augmentation win persists.
CASES = ("A_bc0.5,A_bc1,A_bc3,A_bc4,A_bc5,A_bc6,A_bc8,B_bt20,"
         "D_bc14.1464,D_bc20,D_bc30,D_bc55.0237,E_bc9,E_bc11.8,E_bc18,E_bc35,E_bc45")


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def run_stage(name: str, cmd: list[str], threads: int = 6, critical: bool = True) -> bool:
    sentinel = STATE / f"stage_{name}.done"
    if sentinel.exists():
        log(f"ABL_STAGE_{name}: sentinel present, skipping")
        return True
    log(f"ABL_STAGE_{name}_START: {' '.join(cmd)}")
    env = {**os.environ, "DIFFUSION_V2_TORCH_THREADS": str(threads),
           "PYTHONUNBUFFERED": "1"}
    t0 = time.time()
    rc = subprocess.run(cmd, cwd=REPO, env=env).returncode
    dt = (time.time() - t0) / 60
    if rc == 0:
        sentinel.write_text(f"done {time.strftime('%Y-%m-%d %H:%M:%S')} ({dt:.1f} min)\n")
        log(f"ABL_STAGE_{name}_DONE ({dt:.1f} min)")
        return True
    log(f"ABL_STAGE_{name}_FAILED rc={rc} ({dt:.1f} min)")
    if critical:
        log("ABL_CHAIN_FAILED")
        sys.exit(1)
    return False


def get_z(record: dict, obs_prefix: str):
    for row in record.get("rows", []):
        if str(row.get("observable", "")).lower().startswith(obs_prefix):
            z = row.get("z_exact")
            if z is not None and math.isfinite(z):
                return z
    return None


def write_compare() -> None:
    abl = json.loads((GEN_DIR / "summary.json").read_text(encoding="utf-8"))
    main = json.loads((MAIN_GEN / "summary.json").read_text(encoding="utf-8"))
    lines = [
        "# Norm ablation: v2 (channel norm) vs ablation (group norm)",
        "",
        "Same data, same augmentation/bias/FiLM/blend settings, independent",
        "sampler noise (seed 777 vs 20260730). Only train.norm_type differs.",
        "",
        "| case | beta_f | plaq z: channel | group | W22 z: channel | group | "
        "raw Q2 excess: channel | group |",
        "|---|---|---|---|---|---|---|---|",
    ]
    stats = {"plaq": ([], []), "w22": ([], [])}
    for cid in CASES.split(","):
        a, m = abl.get(cid), main.get(cid)
        if not a or not m or "rows" not in a or "rows" not in m:
            continue
        pm, pa = get_z(m, "plaquette"), get_z(a, "plaquette")
        wm, wa = get_z(m, "w(2x2)") or get_z(m, "wilson_2x2"), get_z(a, "w(2x2)") or get_z(a, "wilson_2x2")
        em = (m.get("q_squared_raw") or 0) - (m.get("base_q_squared") or 0)
        ea = (a.get("q_squared_raw") or 0) - (a.get("base_q_squared") or 0)

        def f(x):
            return f"{x:+.2f}" if isinstance(x, (int, float)) else "--"

        lines.append(f"| {cid} | {m.get('target_beta', 0):g} | {f(pm)} | {f(pa)} | "
                     f"{f(wm)} | {f(wa)} | {f(em)} | {f(ea)} |")
        if pm is not None and pa is not None:
            stats["plaq"][0].append(abs(pm)); stats["plaq"][1].append(abs(pa))
        if wm is not None and wa is not None:
            stats["w22"][0].append(abs(wm)); stats["w22"][1].append(abs(wa))
    lines.append("")
    for name, (ch, gr) in stats.items():
        if ch:
            lines.append(f"mean |{name} z|: channel {statistics.mean(ch):.2f} vs "
                         f"group {statistics.mean(gr):.2f} (n={len(ch)})")
    lines += ["", "If group-norm restores |z| ~ 0.8 while keeping the raw-topology",
              "gains, the channel norm is the regression source and v2 should switch",
              "back (revisit the L=128 volume-transfer trade-off separately)."]
    (OUT / "ablation_compare.md").write_text("\n".join(lines), encoding="utf-8")
    log(f"wrote {OUT / 'ablation_compare.md'}")


def main() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    log("ABL_CHAIN_START")
    run_stage("TRAIN", [PY, "diffusion_v2/scripts/02_train.py",
                        "--config", CONFIG, "--resume"])
    if not (STATE / "stage_CACHECOPY.done").exists():
        import shutil
        for sub in ("bases", "reference"):
            src, dst = MAIN_GEN / sub, GEN_DIR / sub
            if src.exists():
                dst.mkdir(parents=True, exist_ok=True)
                for fp in src.glob("*.pt"):
                    if not (dst / fp.name).exists():
                        shutil.copy2(fp, dst / fp.name)
        (STATE / "stage_CACHECOPY.done").write_text("done\n")
        log("ABL_STAGE_CACHECOPY_DONE")
    run_stage("STUDY", [PY, "diffusion_v2/scripts/06_generalization_study.py",
                        *SAMPLER_FLAGS, "--seed", "777",
                        "--checkpoint", CKPT,
                        "--cases", CASES,
                        "--out-dir", str(GEN_DIR)])
    write_compare()
    log("ABL_CHAIN_DONE")


if __name__ == "__main__":
    main()
