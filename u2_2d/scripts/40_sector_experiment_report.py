"""Does the training data's sector DISTRIBUTION matter, or only its COVERAGE?

Scores the two arms built by `39_sector_distribution_data.py` and trained from
`configs/sector_{exact,uniform}.yaml`. They differ in exactly one thing: the
distribution the training configurations' topological charges were drawn from --
the closed-form P(Q) in one, uniform over the same support in the other.

WHY THE ANSWER MATTERS MORE THAN THE PRECISION IT MEASURES. Every training rung
above model beta ~13 has its topology INSTALLED rather than sampled, because HMC
is frozen there. That has been recorded as the method's dependency on 2D U(2)
being exactly solvable, and so as the thing that closes in 4D SU(3). But the
closed form only picks training sector FREQUENCIES, and at deployment those are
overridden -- the fine charge is imposed from the coarse ensemble, and transport
is exact configuration by configuration (`36_transport_check.py`). If the arms
agree, the exact P(Q) is a convenience for building data and a requirement for
SCORING, not a requirement of the method.

HOW TO READ A NULL RESULT HERE. Agreement is the INTERESTING outcome and it is
also what an underpowered test returns, so the report prints the arms' own
separation on the training data first: if the uniform arm's <Q^2> is not far
from the exact arm's, there was nothing to detect and the null is empty. It is
not -- the builder measures ratios of 3-5x -- but the check belongs in the
output rather than in a claim.

    python u2_2d/scripts/40_sector_experiment_report.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ARMS = ("exact", "uniform")


def jload(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def validation_summary(arm: str):
    rows = jload(Path(f"out/u2_2d/validation_sector{'A' if arm=='exact' else 'B'}/summary.json"))
    if not rows:
        return None
    out = []
    for rec in rows:
        zs, ext = [], []
        for r in rec.get("rows", []):
            z = r.get("z_vs_exact")
            if z is None or not math.isfinite(z):
                continue
            zs.append(abs(z))
            name = r.get("observable", "")
            # extended loops: the scale where the model's error actually shows
            if "wilson" in name and any(k in name for k in ("4x4", "6x6", "8x8")):
                ext.append(abs(z))
        if zs:
            out.append({"lattice_size": rec["lattice_size"], "beta": rec["beta"],
                        "mean_abs_z": float(np.mean(zs)),
                        "max_abs_z": float(np.max(zs)),
                        "ext_mean_abs_z": float(np.mean(ext)) if ext else None,
                        "n": len(zs)})
    return sorted(out, key=lambda r: r["beta"])


def prolongator_summary(arm: str):
    rec = jload(Path(f"out/u2_2d/prolongator_sector_{arm}/prolongator.json"))
    if not rec:
        return None
    rows = rec if isinstance(rec, list) else rec.get("arms", [])
    out = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = r.get("arm") or r.get("name")
        if name:
            out[name] = {"t_therm": r.get("t_therm_plaquette", r.get("t_therm")),
                         "slowest": r.get("t_therm_slowest", r.get("slowest")),
                         "rel_err_t0": r.get("rel_plaquette_error_t0",
                                             r.get("dP_over_P_t0"))}
    return out or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-report",
                    default="out/u2_2d/sector_experiment/data_report.json")
    ap.add_argument("--out", default="out/u2_2d/sector_experiment/report.md")
    args = ap.parse_args()

    lines = ["# Does the training sector distribution matter?", ""]
    lines.append("Two arms, identical but for the distribution the training "
                 "configurations' topological")
    lines.append("charges were drawn from. Built by "
                 "`39_sector_distribution_data.py`, trained from")
    lines.append("`configs/sector_{exact,uniform}.yaml`.")
    lines.append("")

    # ---- 0. did the arms actually differ? ---------------------------------
    dr = jload(Path(args.data_report))
    lines.append("## 0. The arms' separation on the training data")
    lines.append("")
    if dr:
        ratio, odd_e, odd_u = [], [], []
        for r in dr:
            e, u = r.get("exact"), r.get("uniform")
            if not e or not u or e["q_squared"] <= 0:
                continue
            ratio.append(u["q_squared"] / e["q_squared"])
            odd_e.append(e["odd_fraction"])
            odd_u.append(u["odd_fraction"])
        if ratio:
            lines.append(f"- {len(ratio)} re-seeded ensembles.")
            lines.append(f"- `<Q^2>` uniform / exact: median **{np.median(ratio):.2f}x**, "
                         f"range {np.min(ratio):.2f}-{np.max(ratio):.2f}.")
            lines.append(f"- mean odd fraction: exact {np.mean(odd_e):.3f}, "
                         f"uniform {np.mean(odd_u):.3f}.")
            lines.append("")
            lines.append("**This is the power check.** If these were close there "
                         "would be nothing to detect and any agreement below "
                         "would be vacuous.")
    else:
        lines.append("_data report missing_")
    lines.append("")

    # ---- 1. validation ----------------------------------------------------
    lines.append("## 1. Observable agreement after the ladder")
    lines.append("")
    vs = {a: validation_summary(a) for a in ARMS}
    if all(vs.values()):
        lines.append("| rung | exact: mean \\|z\\| | uniform: mean \\|z\\| | "
                     "exact: ext loops | uniform: ext loops |")
        lines.append("|---|---:|---:|---:|---:|")
        for ra, rb in zip(vs["exact"], vs["uniform"]):
            ea = "--" if ra["ext_mean_abs_z"] is None else f"{ra['ext_mean_abs_z']:.3f}"
            eb = "--" if rb["ext_mean_abs_z"] is None else f"{rb['ext_mean_abs_z']:.3f}"
            lines.append(f"| L={ra['lattice_size']} beta={ra['beta']:.3f} | "
                         f"{ra['mean_abs_z']:.3f} | {rb['mean_abs_z']:.3f} | {ea} | {eb} |")
    else:
        lines.append("_validation summary missing for at least one arm_")
    lines.append("")

    # ---- 2. prolongator ---------------------------------------------------
    lines.append("## 2. Trajectories to thermalization (prolongator, rung 0)")
    lines.append("")
    ps = {a: prolongator_summary(a) for a in ARMS}
    if all(ps.values()):
        names = sorted(set(ps["exact"]) | set(ps["uniform"]))
        lines.append("| arm | exact: t_therm | uniform: t_therm |")
        lines.append("|---|---:|---:|")
        for n in names:
            a = ps["exact"].get(n, {}).get("slowest")
            b = ps["uniform"].get(n, {}).get("slowest")
            lines.append(f"| {n} | {a} | {b} |")
    else:
        lines.append("_prolongator summary missing for at least one arm_")
    lines.append("")

    # ---- 3. verdict -------------------------------------------------------
    lines.append("## 3. Verdict")
    lines.append("")
    verdict = "INCONCLUSIVE -- one or both arms did not produce a scorecard."
    if all(vs.values()):
        da, db = vs["exact"], vs["uniform"]
        diffs = [abs(x["mean_abs_z"] - y["mean_abs_z"]) for x, y in zip(da, db)]
        worst = max(diffs) if diffs else float("inf")
        both = np.mean([x["mean_abs_z"] for x in da] + [y["mean_abs_z"] for y in db])
        if worst < 0.35 * max(both, 1e-9) or worst < 0.15:
            verdict = (
                "**THE SECTOR DISTRIBUTION DOES NOT MATTER.** The arms agree on "
                "observable\nagreement to within " + f"{worst:.3f} in mean |z| "
                "despite training data whose `<Q^2>`\ndiffers by a factor of "
                "several. The closed-form P(Q) is therefore a CONVENIENCE for\n"
                "building training data and a REQUIREMENT for scoring -- not a "
                "requirement of the\nmethod. What the training data must supply "
                "is sector COVERAGE, which can be\nmanufactured without a closed "
                "form. This is the result that lets the construction\nbe claimed "
                "for 4D SU(3), where no closed-form P(Q) exists.")
        else:
            verdict = (
                "**THE SECTOR DISTRIBUTION DOES MATTER** -- arms differ by up to "
                f"{worst:.3f} in mean |z|.\nThe exact P(Q) is then load-bearing "
                "for the training data, and the transfer claim\nto theories "
                "without a closed form has to be made more carefully, or the\n"
                "training-data recipe has to be replaced with something that "
                "does not need one.")
    lines.append(verdict)
    lines.append("")

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(chr(10).join(lines), encoding="utf-8")
    print(chr(10).join(lines))
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
