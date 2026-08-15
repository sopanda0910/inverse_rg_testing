"""Is the projection-sigma difference bigger than seed noise?

Reads the nine validation reports from run_proj_seed_sweep.py and compares two
spreads:

  between-arm  -- how far apart the three thresholds sit, averaged over seeds
  between-seed -- how far apart three seeds of the SAME threshold sit

The threshold matters only if the first exceeds the second. Reported as a
one-way ANOVA F on mean|z_exact| plus the raw 3x3 table, because with three
seeds per cell the F is worth less than letting the reader see the numbers.

    .venv/Scripts/python.exe u1_2d/scripts/parse_proj_seed_sweep.py
"""

import json
import math
import re
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AB = REPO / "out" / "u1_2d" / "proj_sigma_ab"
TAGS = {"020": 0.20, "031": 0.31, "050": 0.50}
SEEDS = (11, 12, 13)
TOPO = {"Q", "Q^2", "chi_top ((<Q^2>-<Q>^2)/V)"}


def parse_report(path: Path) -> dict:
    """mean|z_exact|, max|z_exact| and |z|>3 count over the enforced rungs."""
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    out = {}
    for sec in sections:
        head, _, body = sec.partition("\n")
        head = head.strip()
        if head.endswith("_RAW_preenforcement"):
            continue
        zs, topo = [], {}
        for line in body.splitlines():
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 5 or cells[0] == "observable":
                continue
            name, z = cells[0], cells[4]
            try:
                zval = float(z)
            except ValueError:
                continue
            if not math.isfinite(zval):
                continue
            zs.append(zval)
            if name in TOPO:
                topo[name] = zval
        if zs:
            out[head] = {
                "mean_abs_z": statistics.fmean(abs(z) for z in zs),
                "max_abs_z": max(abs(z) for z in zs),
                "n_gt3": sum(1 for z in zs if abs(z) > 3),
                "n_obs": len(zs),
                "topo": topo,
            }
    return out


def main() -> None:
    table, missing = {}, []
    for tag in TAGS:
        for seed in SEEDS:
            rpt = AB / f"s{tag}_seed{seed}" / "report.md"
            if not rpt.exists():
                missing.append(rpt.parent.name)
                continue
            rungs = parse_report(rpt)
            table[(tag, seed)] = {
                "rungs": rungs,
                "mean_abs_z": statistics.fmean(r["mean_abs_z"] for r in rungs.values()),
                "n_gt3": sum(r["n_gt3"] for r in rungs.values()),
                "n_obs": sum(r["n_obs"] for r in rungs.values()),
            }
    if missing:
        print(f"missing: {', '.join(sorted(missing))}\n")
    if not table:
        return

    print("mean|z_exact| over all rungs, all observables\n")
    print("| sigma | seed 11 | seed 12 | seed 13 | arm mean | arm sd |")
    print("|---|---|---|---|---|---|")
    arm_means = {}
    for tag, sig in TAGS.items():
        vals = [table[(tag, s)]["mean_abs_z"] if (tag, s) in table else None for s in SEEDS]
        got = [v for v in vals if v is not None]
        if not got:
            continue
        arm_means[tag] = got
        cells = " | ".join("--" if v is None else f"{v:.4f}" for v in vals)
        sd = statistics.stdev(got) if len(got) > 1 else float("nan")
        print(f"| {sig:.2f} | {cells} | {statistics.fmean(got):.4f} | {sd:.4f} |")

    print("\n| sigma | seed 11 | seed 12 | seed 13 |  (count of |z|>3 out of n) |")
    print("|---|---|---|---|---|")
    for tag, sig in TAGS.items():
        vals = [table[(tag, s)] if (tag, s) in table else None for s in SEEDS]
        cells = " | ".join("--" if v is None else str(v["n_gt3"]) for v in vals)
        n_obs = next((v["n_obs"] for v in vals if v), 0)
        print(f"| {sig:.2f} | {cells} | of {n_obs} |")

    complete = {t: v for t, v in arm_means.items() if len(v) == len(SEEDS)}
    if len(complete) < 2:
        print("\n(spread decomposition needs every seed of >=2 arms)")
        return

    grand = statistics.fmean(v for vals in complete.values() for v in vals)
    k, n = len(complete), len(SEEDS)
    ss_between = n * sum((statistics.fmean(v) - grand) ** 2 for v in complete.values())
    ss_within = sum((x - statistics.fmean(v)) ** 2 for v in complete.values() for x in v)
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (k * (n - 1))
    f_stat = ms_between / ms_within if ms_within else float("inf")

    between_sd = statistics.stdev([statistics.fmean(v) for v in complete.values()])
    within_sd = ms_within ** 0.5
    print(f"\nbetween-arm sd of arm means : {between_sd:.4f}")
    print(f"between-seed sd within arm  : {within_sd:.4f}")
    print(f"F({k - 1}, {k * (n - 1)}) = {f_stat:.3f}   (F_crit ~ 5.14 at p=0.05 for F(2,6))")
    verdict = ("threshold effect EXCEEDS seed noise"
               if f_stat > 5.14 else
               "threshold effect is INSIDE seed noise -- null measured")
    print(f"verdict: {verdict}")

    out = AB / "seed_sweep_summary.json"
    out.write_text(json.dumps({
        "arms": {f"s{t}_seed{s}": v["mean_abs_z"] for (t, s), v in table.items()},
        "n_gt3": {f"s{t}_seed{s}": v["n_gt3"] for (t, s), v in table.items()},
        "between_arm_sd": between_sd,
        "between_seed_sd": within_sd,
        "f_stat": f_stat,
        "f_crit_p05": 5.14,
        "verdict": verdict,
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
