"""Re-validate the cached generalization ensembles with the M3/M4 fixes applied.

Two review items changed what `validate_ensemble` reports, and both change
numbers already transcribed into the appendix:

  M4  The 38-case study called `validate_ensemble` without `n_chains` /
      `ref_n_chains`, so every error bar was the fixed 20-bin estimate rather
      than the per-chain tau_int estimate the honesty conventions describe.
      Error bars feed z-scores, so the case tables inherited the wrong ones.

  M3  The P(Q) chi^2 row was emitted only when >= 2 bins had expected > 2 and
      observed counts landed in them, so it VANISHED - rendering as "-",
      indistinguishable from "not applicable" - exactly when P(Q) was most
      wrong. It now pools tails into overflow bins and always emits a verdict.

This script does not regenerate anything. It reloads the cached generated and
reference ensembles a study directory already holds and re-runs validation over
them, writing to a NEW directory so the record of the original run stays intact
and the two can be diffed. It needs no checkpoint and no GPU.

The report at the end is the point: which z-scores moved, and how many chi^2
verdicts existed only because M3 was fixed.

    .venv/Scripts/python.exe u1_2d/scripts/48_revalidate_tau_aware.py \
        --study out/u1_2d/generalization
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np

from u1_2d.utils import load_ensemble, save_json
from u1_2d.validate.report import validate_ensemble

REPO = Path(__file__).resolve().parents[2]
ACTION_TYPE = "wilson"
N_CHAINS = 16


def _rows_by_obs(rows) -> dict:
    return {r["observable"]: r for r in rows or []}


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="out/u1_2d/generalization")
    ap.add_argument("--out", default=None,
                    help="defaults to <study>_tau_aware")
    ap.add_argument("--n-chains", type=int, default=N_CHAINS)
    ap.add_argument("--cases", default=None, help="comma-separated run_ids")
    args = ap.parse_args()

    study = REPO / args.study
    out_dir = Path(args.out) if args.out else Path(str(study) + "_tau_aware")
    out_dir = out_dir if out_dir.is_absolute() else REPO / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = json.loads((study / "summary.json").read_text(encoding="utf-8"))
    wanted = set(args.cases.split(",")) if args.cases else None

    new_records, deltas = {}, []
    missing = []
    for run_id, rec in records.items():
        if wanted and run_id not in wanted:
            continue
        base_size = rec.get("base_size")
        beta = rec.get("target_beta")
        if base_size is None or beta is None:
            missing.append((run_id, "no base_size/target_beta"))
            continue
        fine_size = base_size * 2
        gen_p = study / "generated" / f"{run_id}_{ACTION_TYPE}_L{fine_size}_beta{beta:g}.pt"
        ref_p = study / "reference" / f"{ACTION_TYPE}_L{fine_size}_beta{beta:g}.pt"
        if not gen_p.exists() or not ref_p.exists():
            missing.append((run_id, f"cache miss ({gen_p.name})"))
            continue

        fine, _ = load_ensemble(gen_p)
        ref, _ = load_ensemble(ref_p)
        ref = ref[:rec.get("n_reference", ref.shape[0])]
        rows = validate_ensemble(
            fine, beta, ACTION_TYPE, reference_configs=ref, label=run_id,
            output_dir=None, make_plots=False,
            n_chains=args.n_chains, ref_n_chains=args.n_chains,
        )
        new = dict(rec)
        new["rows"] = rows
        new["revalidated"] = {"n_chains": args.n_chains,
                              "source_study": str(study.relative_to(REPO))}
        new_records[run_id] = new

        old_by, new_by = _rows_by_obs(rec.get("rows")), _rows_by_obs(rows)
        oz = [r["z_exact"] for r in old_by.values() if _finite(r.get("z_exact"))]
        nz = [r["z_exact"] for r in new_by.values() if _finite(r.get("z_exact"))]
        chi_old = old_by.get("Q histogram vs exact P(Q)", {}).get("chi2_p")
        chi_new = new_by.get("Q histogram vs exact P(Q)", {}).get("chi2_p")
        deltas.append({
            "run_id": run_id, "beta": beta, "L": fine_size,
            "mean_abs_z_old": float(np.mean(np.abs(oz))) if oz else None,
            "mean_abs_z_new": float(np.mean(np.abs(nz))) if nz else None,
            "n_z_gt3_old": int(sum(abs(z) > 3 for z in oz)),
            "n_z_gt3_new": int(sum(abs(z) > 3 for z in nz)),
            "chi2_p_old": chi_old, "chi2_p_new": chi_new,
            "chi2_row_is_new": chi_old is None and chi_new is not None,
            "chi2_note": new_by.get("Q histogram vs exact P(Q)", {}).get("chi2_note"),
        })
        print(f"  {run_id:24s} L={fine_size:<4d} beta={beta:<9g} "
              f"|z| {deltas[-1]['mean_abs_z_old'] or float('nan'):.3f} -> "
              f"{deltas[-1]['mean_abs_z_new'] or float('nan'):.3f}   "
              f"chi2_p {chi_old if chi_old is None else round(chi_old, 4)} -> "
              f"{chi_new if chi_new is None else round(chi_new, 4)}", flush=True)

    save_json(out_dir / "summary.json", new_records)
    save_json(out_dir / "revalidation_deltas.json", deltas)

    if missing:
        print(f"\nskipped {len(missing)} case(s) with no cached ensemble:")
        for run_id, why in missing[:10]:
            print(f"  {run_id}: {why}")

    ok = [d for d in deltas if d["mean_abs_z_old"] and d["mean_abs_z_new"]]
    print("\n=== what the fixes changed ===")
    print(f"cases re-validated: {len(deltas)}")
    if ok:
        om = float(np.mean([d["mean_abs_z_old"] for d in ok]))
        nm = float(np.mean([d["mean_abs_z_new"] for d in ok]))
        print(f"mean |z_exact| over cases: {om:.4f} -> {nm:.4f}")
        print(f"total |z| > 3 flags:       "
              f"{sum(d['n_z_gt3_old'] for d in ok)} -> "
              f"{sum(d['n_z_gt3_new'] for d in ok)}")
    newly = [d for d in deltas if d["chi2_row_is_new"]]
    print(f"chi2 verdicts that previously VANISHED (M3): {len(newly)}")
    for d in newly:
        print(f"    {d['run_id']:24s} beta={d['beta']:<9g} p={d['chi2_p_new']:.3g}"
              f"  {d['chi2_note'] or ''}")
    moved = [d for d in deltas
             if _finite(d["chi2_p_old"]) and _finite(d["chi2_p_new"])
             and abs(d["chi2_p_old"] - d["chi2_p_new"]) > 0.01]
    print(f"chi2 p-values that moved by > 0.01 (M3 pooling + M4 tau): {len(moved)}")
    for d in moved[:15]:
        print(f"    {d['run_id']:24s} {d['chi2_p_old']:.4f} -> {d['chi2_p_new']:.4f}")
    print(f"\nwrote {(out_dir / 'summary.json').relative_to(REPO)}")


if __name__ == "__main__":
    main()
