"""Regenerate Table S3 (sector-mode comparison) from the ensembles of record.

Table S3 and the Figure 20 caption were transcribed from a generalization run
that has since been regenerated (GPU verification, 2026-08). Two of the five
transport chi^2 failures they list no longer fail on the current ensembles --
including C_L128, whose recorded transport p is 0.8663, not the 0.005 the
caption quotes. Since section 21.5 leans on that specific case to argue the
large-volume result depends on the abelian exact-P(Q) crutch, the numbers are
recomputed here from `summary.json` rather than hand-corrected.

Restricted to the case set the two modes share. The transport run gained six
Part-G rungs that were never run in exact-sector mode, and including them on
one side only would flatter or penalise that column for no reason.

    .venv/Scripts/python.exe u1_2d/scripts/42_sector_mode_table.py
"""

import argparse
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def rows_by_obs(rec: dict) -> dict:
    return {r["observable"]: r for r in rec.get("rows", [])}


def stats(summary: dict, cases: list[str]) -> dict:
    chi_tested, chi_fail, chi_fail_b = [], [], []
    z_q2, z_q2_inf, z_q, plaq = [], 0, [], []
    for k in cases:
        obs = rows_by_obs(summary[k])
        hist = obs.get("Q histogram vs exact P(Q)")
        if hist is not None and hist.get("chi2_p") is not None:
            chi_tested.append(k)
            if hist["chi2_p"] < 0.05:
                chi_fail.append((k, hist["chi2_p"]))
                if k.startswith("B"):
                    chi_fail_b.append(k)
        q2 = obs.get("Q^2")
        if q2 is not None and q2.get("z_exact") is not None:
            z = q2["z_exact"]
            if math.isfinite(z):
                z_q2.append((k, abs(z)))
            else:
                z_q2_inf += 1
        q = obs.get("Q")
        if q is not None and math.isfinite(q.get("z_exact", float("nan"))):
            z_q.append(abs(q["z_exact"]))
        p = obs.get("plaquette")
        if p is not None and math.isfinite(p.get("z_exact", float("nan"))):
            plaq.append(abs(p["z_exact"]))
    worst = max(z_q2, key=lambda t: t[1]) if z_q2 else ("--", float("nan"))
    return {
        "n_cases": len(cases),
        "chi_tested": len(chi_tested),
        "chi_fail": chi_fail,
        "chi_fail_b": chi_fail_b,
        "worst_z_q2": worst,
        "n_z_q2_gt2": sum(1 for _, z in z_q2 if z > 2),
        "n_z_q2_inf": z_q2_inf,
        "n_zq_gt2": sum(1 for z in z_q if z > 2),
        "mean_abs_plaq_z": sum(plaq) / len(plaq) if plaq else float("nan"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", default="out/u1_2d/generalization")
    ap.add_argument("--exact", default="out/u1_2d/generalization_exact_sectors")
    ap.add_argument("--out", default="out/u1_2d/sector_mode_table")
    args = ap.parse_args()

    tr = json.loads((REPO / args.transport / "summary.json").read_text(encoding="utf-8"))
    ex = json.loads((REPO / args.exact / "summary.json").read_text(encoding="utf-8"))
    common = sorted(set(tr) & set(ex))
    only_tr = sorted(set(tr) - set(ex))

    st, se = stats(tr, common), stats(ex, common)

    L = ["# Table S3 (regenerated) — sector-mode comparison", "",
         f"Common case set: {len(common)} cases. Excluded as transport-only: "
         f"{', '.join(only_tr) if only_tr else 'none'}.", "",
         "| metric | transport | exact-sector |", "|---|---|---|",
         f"| exact-P(Q) χ² failures (p < 0.05) | {len(st['chi_fail'])}/{st['chi_tested']} "
         f"| {len(se['chi_fail'])}/{se['chi_tested']} |",
         f"| … of which mismatch track (B) | {len(st['chi_fail_b'])} | {len(se['chi_fail_b'])} |",
         f"| worst \\|z(⟨Q²⟩ vs exact)\\| | {st['worst_z_q2'][1]:.1f} ({st['worst_z_q2'][0]}) "
         f"| {se['worst_z_q2'][1]:.1f} ({se['worst_z_q2'][0]}) |",
         f"| cases with \\|z(⟨Q²⟩)\\| > 2 | {st['n_z_q2_gt2']} | {se['n_z_q2_gt2']} |",
         f"| … non-finite z excluded | {st['n_z_q2_inf']} | {se['n_z_q2_inf']} |",
         f"| significant ⟨Q⟩ asymmetry (\\|z\\| > 2) | {st['n_zq_gt2']} | {se['n_zq_gt2']} |",
         f"| mean \\|plaquette z\\| | {st['mean_abs_plaq_z']:.2f} | {se['mean_abs_plaq_z']:.2f} |",
         ""]

    L += ["## χ² failures, listed", ""]
    for name, s in (("transport", st), ("exact-sector", se)):
        if s["chi_fail"]:
            L.append(f"* {name}: " + ", ".join(f"{k} (p = {p:.2g})" for k, p in s["chi_fail"]))
        else:
            L.append(f"* {name}: none")
    L.append("")

    # The specific case section 21.5 rests on.
    for k in ("C_L128", "C_L64"):
        if k in common:
            a = rows_by_obs(tr[k]).get("Q histogram vs exact P(Q)", {}).get("chi2_p")
            b = rows_by_obs(ex[k]).get("Q histogram vs exact P(Q)", {}).get("chi2_p")
            L.append(f"* **{k}**: transport χ² p = {a:.4g}, exact-sector p = {b:.4g} "
                     + ("— transport passes; the crutch is not what rescues this case."
                        if a is not None and a >= 0.05 else ""))
    L.append("")

    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "table_s3.md").write_text("\n".join(L), encoding="utf-8")
    (out / "table_s3.json").write_text(json.dumps(
        {"common_cases": common, "transport_only": only_tr,
         "transport": st, "exact_sector": se}, indent=2, default=str), encoding="utf-8")
    print("\n".join(L))
    print(f"wrote {(out / 'table_s3.md').relative_to(REPO)}")


if __name__ == "__main__":
    main()
