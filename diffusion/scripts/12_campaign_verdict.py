"""Campaign verdict: one-command tables + showcase figure for a generalization
study directory (06 output, optionally with seeds/*/ replicas and a
thermalization/ benchmark from 05 --generalization).

    .venv/Scripts/python.exe diffusion/scripts/12_campaign_verdict.py \
        --study out/diffusion/demo_v6/generalization --train-range 1:60
    .venv/Scripts/python.exe diffusion/scripts/12_campaign_verdict.py \
        --study out/diffusion/demo/generalization_v5 --train-range 1:60 \
        --baseline out/diffusion/demo/generalization_v4

Writes verdict.md and showcase.png into the study directory (or --out).
"""

import argparse
import glob
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.validate.report import GEN_COLOR, REF_COLOR, INK, MUTED, GRID_COLOR

PART_COLORS = {"A": GEN_COLOR, "D": GEN_COLOR, "E": "#c2571a", "F": "#8a1f9c",
               "B": MUTED, "C": REF_COLOR}
PART_MARKERS = {"A": "o", "D": "o", "E": "s", "F": "*", "B": "x", "C": "^"}
WILSON_SLOW = ("plaquette", "wilson_2x2", "wilson_4x4")


def load_summaries(study: Path) -> list[dict]:
    runs = []
    main = study / "summary.json"
    if main.exists():
        runs.append(json.loads(main.read_text(encoding="utf-8")))
    for p in sorted(study.glob("seeds/*/summary.json")):
        runs.append(json.loads(p.read_text(encoding="utf-8")))
    if not runs:
        raise SystemExit(f"no summary.json under {study}")
    return runs


def obs_z(rec: dict, name: str) -> float:
    row = next((r for r in rec.get("rows", []) if r["observable"] == name), {})
    v = row.get("z_exact")
    return float("nan") if v is None else v


def chi2_p(rec: dict):
    row = next((r for r in rec.get("rows", []) if r["observable"] == "Q histogram vs exact P(Q)"), {})
    return row.get("chi2_p")


def seed_values(runs: list[dict], case: str, fn) -> list[float]:
    vals = []
    for run in runs:
        rec = run.get(case)
        if rec and "rows" in rec:
            v = fn(rec)
            if v is not None and v == v:
                vals.append(v)
    return vals


def collect_cases(runs: list[dict]) -> list[dict]:
    cases = {}
    for run in runs:
        for k, rec in run.items():
            if "rows" in rec and k not in cases:
                cases[k] = rec
    out = []
    for k, rec in cases.items():
        entry = {
            "id": k, "part": rec["part"], "beta_f": float(rec["target_beta"]),
            "base_size": int(rec["base_size"]), "fine_size": 2 * int(rec["base_size"]),
        }
        for label, fn in [("plaq_z", lambda r: obs_z(r, "plaquette")),
                          ("w22_z", lambda r: obs_z(r, "wilson_2x2")),
                          ("q2_z", lambda r: obs_z(r, "Q^2")),
                          ("chi2_p", chi2_p),
                          ("raw_excess", lambda r: (r["q_squared_raw"] - r["base_q_squared"])
                           if "q_squared_raw" in r else None)]:
            entry[label] = seed_values(runs, k, fn)
        out.append(entry)
    return sorted(out, key=lambda e: (e["part"], e["beta_f"]))


def load_therm(study: Path) -> list[dict]:
    rows = []
    for p in sorted(glob.glob(str(study / "thermalization" / "*" / "*_summary.json"))):
        s = json.loads(Path(p).read_text(encoding="utf-8"))
        tt = s["t_therm"].get("diffusion seed", {})
        vals = [tt.get(o) for o in WILSON_SLOW]
        never = any(v is None or (isinstance(v, float) and math.isinf(v)) for v in vals)
        rows.append({
            "label": s["label"], "part": s["label"].split("_")[0],
            "beta_f": float(s["beta"]), "L": int(s["lattice_size"]),
            "t_therm": None if never else max(vals),
            "interval": float(s["hmc_interval_trajectories"]),
            "budget": int(s.get("n_traj_baseline", 640)),
        })
    return sorted(rows, key=lambda r: (r["L"], r["beta_f"]))


def fmt_seeds(vals: list[float], spec: str = "+.2f") -> str:
    if not vals:
        return "-"
    if len(vals) == 1:
        return format(vals[0], spec)
    mean = sum(vals) / len(vals)
    return f"{format(mean, spec)} ({'/'.join(format(v, spec) for v in vals)})"


def write_tables(cases, therm, out_path: Path, baseline_note: str) -> None:
    lines = ["# Campaign verdict", ""]
    if baseline_note:
        lines += [baseline_note, ""]
    lines += ["## Pipeline observables vs exact (mean over seeds, per-seed in parentheses)", "",
              "| case | part | L_f | beta_f | plaq z | W22 z | Q^2 z | P(Q) chi2 p |",
              "|" + "---|" * 8]
    for e in cases:
        lines.append("| " + " | ".join([
            e["id"], e["part"], str(e["fine_size"]), f"{e['beta_f']:g}",
            fmt_seeds(e["plaq_z"]), fmt_seeds(e["w22_z"]), fmt_seeds(e["q2_z"]),
            fmt_seeds(e["chi2_p"], ".2f"),
        ]) + " |")
    lines.append("")

    lines += ["## Raw topology (spurious Q^2 excess over base, pre-enforcement)", ""]
    for part in sorted({e["part"] for e in cases}):
        vals = [v for e in cases if e["part"] == part for v in e["raw_excess"]]
        if vals:
            lines.append(f"- part {part}: mean excess {sum(vals)/len(vals):.2f} (n={len(vals)})")
    lines.append("")

    if therm:
        lines += ["## Thermalization (raw seeds; slowest Wilson observable)", "",
                  "| case | L | beta_f | t_therm | 2 tau_int | verdict |",
                  "|" + "---|" * 6]
        for r in therm:
            t = "never" if r["t_therm"] is None else f"{r['t_therm']:.0f}"
            verdict = ("-" if r["t_therm"] is None
                       else ("seed wins" if r["t_therm"] < r["interval"] else "HMC wins"))
            lines.append(f"| {r['label']} | {r['L']} | {r['beta_f']:g} | {t} | "
                         f"{r['interval']:.1f} | {verdict} |")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def make_figure(cases, therm, train_range, out_path: Path) -> None:
    n_panels = 3 if therm else 2
    fig, axes = plt.subplots(1, n_panels, figsize=(4.4 * n_panels, 4.0))

    def style(ax):
        ax.grid(axis="y", color=GRID_COLOR, lw=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=8, colors=MUTED)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
        ax.set_xscale("log")
        ax.set_xlabel(r"target $\beta_f$", fontsize=9, color=INK)
        if train_range:
            ax.axvspan(train_range[0], train_range[1], color=GRID_COLOR, alpha=0.35, zorder=0)

    seen = set()
    for e in cases:
        vals = e["q2_z"]
        if not vals:
            continue
        mean = sum(vals) / len(vals)
        lo, hi = min(vals), max(vals)
        label = f"part {e['part']}" if e["part"] not in seen else None
        seen.add(e["part"])
        axes[0].errorbar([e["beta_f"]], [mean], yerr=[[mean - lo], [hi - mean]],
                         fmt=PART_MARKERS[e["part"]], color=PART_COLORS[e["part"]],
                         ms=7 if e["part"] == "F" else 5, lw=1.1, capsize=2, label=label)
    axes[0].axhspan(-2, 2, color=GRID_COLOR, alpha=0.45, zorder=0)
    axes[0].axhline(0.0, color=INK, lw=0.8)
    axes[0].set_title(r"$\langle Q^2 \rangle$ z vs exact (seed range)", fontsize=10, color=INK)
    axes[0].legend(fontsize=7, frameon=False)
    style(axes[0])

    for e in cases:
        for v in e["raw_excess"]:
            axes[1].plot([e["beta_f"]], [v], PART_MARKERS[e["part"]],
                         color=PART_COLORS[e["part"]], ms=6 if e["part"] == "F" else 4, alpha=0.85)
    axes[1].set_title("raw spurious $Q^2$ excess (pre-enforcement)", fontsize=10, color=INK)
    style(axes[1])

    if therm:
        ax = axes[2]
        budget = max((r.get("budget", 640) for r in therm), default=640)
        for r in therm:
            color = PART_COLORS.get(r["part"], MUTED)
            marker = PART_MARKERS.get(r["part"], "o")
            if r["t_therm"] is None:
                ax.plot([r["beta_f"]], [budget], marker, color=color,
                        mfc="none", ms=6, alpha=0.7)
            else:
                ax.plot([r["beta_f"]], [max(r["t_therm"], 0.5)], marker, color=color, ms=5)
        ax.axhline(budget, color=MUTED, ls="--", lw=1.0, zorder=1)
        ax.set_yscale("log")
        ax.set_title("raw-seed t_therm (HMC trajectories);\nopen marker at budget = never",
                     fontsize=9, color=INK)
        style(ax)

    fig.suptitle("One model across the coupling track (shaded = training range)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--train-range", default=None,
                        help="beta_min:beta_max of the training couplings (figure shading)")
    parser.add_argument("--baseline", default=None,
                        help="another study dir; its per-part raw excess is quoted for comparison")
    args = parser.parse_args()
    study = Path(args.study)
    out = Path(args.out) if args.out else study
    runs = load_summaries(study)
    cases = collect_cases(runs)
    therm = load_therm(study)
    train_range = None
    if args.train_range:
        lo, hi = args.train_range.split(":")
        train_range = (float(lo), float(hi))

    baseline_note = ""
    if args.baseline:
        base_runs = load_summaries(Path(args.baseline))
        base_cases = collect_cases(base_runs)
        parts = []
        for part in sorted({e["part"] for e in base_cases}):
            vals = [v for e in base_cases if e["part"] == part for v in e["raw_excess"]]
            if vals:
                parts.append(f"{part}: {sum(vals)/len(vals):.2f} (n={len(vals)})")
        baseline_note = f"Baseline raw Q^2 excess ({args.baseline}): " + "; ".join(parts)

    write_tables(cases, therm, out / "verdict.md", baseline_note)
    make_figure(cases, therm, train_range, out / "showcase.png")
    print(f"verdict: {out / 'verdict.md'}")
    print(f"figure:  {out / 'showcase.png'}")


if __name__ == "__main__":
    main()
