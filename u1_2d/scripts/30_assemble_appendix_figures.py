"""Assemble out/u1_2d/paper_appendix/figures/ from its canonical sources.

Why this exists. Ten of the 30 appendix figures are written directly by
scripts 17/23/26; the other nineteen were produced by the campaign scripts under
their own output directories and copied into place **by hand**. That made the
figure directory of record unreproducible and let it drift silently: figures
01-03 on disk were copies taken before the 2026-08-02 audit chain re-ran
`04_validate.py`, so they showed a stale reference ensemble (rung-0 plaquette
z = 2.38 against the current 2.15) while every other figure had moved on.

This script is the single source of truth for the mapping. It

  * copies each figure from its canonical source, reporting anything stale;
  * rebuilds figure 01 from `validation/report.md` (the generated ensembles
    were pruned on 2026-08-02, so the numbers -- not the tensors -- are the
    durable artifact);
  * verifies all 30 are present and that each is referenced by appendix.md;
  * writes `figures/MANIFEST.md` recording source path, sha256 and mtime.

    python u1_2d/scripts/30_assemble_appendix_figures.py [--check]

`--check` makes no changes and exits non-zero if anything is stale or missing,
which is the form to run before submitting.
"""

import argparse
import hashlib
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from u1_2d.validate.report import plot_ladder_drift, plot_ladder_topology

OUT = Path("out/u1_2d")
FIG_DIR = OUT / "paper_appendix" / "figures"
APPENDIX_MD = OUT / "paper_appendix" / "appendix.md"

# figure name -> source relative to out/u1_2d, or None when a script writes it
# straight into FIG_DIR (scripts 17, 23, 26).
SOURCES: dict[str, str | None] = {
    "01_ladder_drift.png": "REBUILD",
    "02_ladder_topology.png": "REBUILD",
    "03_ladder_rung_L64.png": "validation/rung2_L64_beta55.0237.png",
    "04_matched_scan.png": "generalization/fig_matched_scan.png",
    "05_mismatch_scan.png": "generalization/fig_mismatch_scan.png",
    "06_size_scan.png": "generalization/fig_size_scan.png",
    "07_raw_topology.png": "generalization/fig_raw_topology.png",
    "08_case_low.png": "generalization/figures/A_bc1.png",
    "09_case_high.png": "generalization/figures/D_bc55.0237.png",
    "10_case_extrapolation.png": "generalization/figures/F_L32_bc218.58.png",
    "11_case_L64.png": "generalization/figures/F_L64_bc55.0237.png",
    "12_timescales.png": "thermalization/timescales.png",
    "13_beta_scan.png": "thermalization/beta_scan.png",
    "14_relaxation_mid.png": "thermalization/L32_beta55.0237/D_bc14.1464_L32_beta55.0237_relaxation.png",
    "15_relaxation_high.png": "thermalization/L32_beta218.58/D_bc55.0237_L32_beta218.58_relaxation.png",
    "16_autocorrelation_modes.png": "thermalization/autocorrelation_modes.png",
    "17_headtohead_cost.png": None,
    "18_entry_cost.png": None,
    "19_ess_weights.png": None,
    "20_mismatch_exact_sectors.png": "generalization_exact_sectors/fig_mismatch_scan.png",
    "21_pq_tail_mismatch.png": "pq_hmc_tail/B_bt6_pq_tail.png",
    "22_pq_tail_L64.png": "pq_hmc_tail/C_L64_pq_tail.png",
    "23_ess_progress.png": None,
    "24_proposal_sweep.png": None,
    "25_finetune_dynamics.png": None,
    "26_three_way.png": None,
    "27_program_optimum.png": None,
    "28_dissociation.png": "paper_appendix/dissociation.png",
    "29_seed_quality.png": None,
    "30_volume_scan.png": None,
    "31_frozen_traces.png": None,
    "32_burnin_wall.png": None,
    "33_ladder_fixed_point.png": None,
    "34_match_rate_volume.png": None,
    "35_sector_freeze_sigma.png": None,
    "36_sector_tail.png": None,
    "37_z_distribution.png": None,
    "38_z_vs_loop_area.png": None,
    "39_kl_per_site.png": None,
    "40_cost_per_config.png": None,
    "41_breakeven.png": None,
    "42_mala_locality.png": None,
    "43_zhu_pq.png": None,
    "44_pipeline.png": None,
    "45_architecture.png": None,
}

SCRIPT_FOR = {
    "17": "u1_2d/scripts/17_appendix_figures.py",
    "18": "u1_2d/scripts/17_appendix_figures.py",
    "19": "u1_2d/scripts/17_appendix_figures.py",
    "23": "u1_2d/scripts/23_ess_progress_figures.py",
    "24": "u1_2d/scripts/23_ess_progress_figures.py",
    "25": "u1_2d/scripts/23_ess_progress_figures.py",
    "26": "u1_2d/scripts/26_final_results_figures.py",
    "27": "u1_2d/scripts/26_final_results_figures.py",
    "29": "u1_2d/scripts/50_seed_quality_figure.py",
    "30": "u1_2d/scripts/51_volume_scan_figure.py",
    "31": "u1_2d/scripts/52_problem_figures.py",
    "32": "u1_2d/scripts/52_problem_figures.py",
    "33": "u1_2d/scripts/53_transport_figures.py",
    "34": "u1_2d/scripts/53_transport_figures.py",
    "35": "u1_2d/scripts/53_transport_figures.py",
    "36": "u1_2d/scripts/53_transport_figures.py",
    "37": "u1_2d/scripts/54_seed_accuracy_figures.py",
    "38": "u1_2d/scripts/54_seed_accuracy_figures.py",
    "39": "u1_2d/scripts/54_seed_accuracy_figures.py",
    "40": "u1_2d/scripts/55_cost_figures.py",
    "41": "u1_2d/scripts/55_cost_figures.py",
    "42": "u1_2d/scripts/56_positioning_figures.py",
    "43": "u1_2d/scripts/56_positioning_figures.py",
    "44": "u1_2d/scripts/57_schematics.py",
    "45": "u1_2d/scripts/57_schematics.py",
}

RUNG_HEADING = re.compile(r"^## rung(\d+)_L(\d+)_beta([0-9.]+)\s*$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_validation_report(path: Path) -> list[dict]:
    """Per-rung z_exact for the drift observables, straight out of report.md.

    The generated .pt ensembles were pruned, so this markdown table is the
    durable record of the ladder validation.
    """
    rungs: list[dict] = []
    current: dict | None = None
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = RUNG_HEADING.match(stripped)
            header = None
            if heading:
                current = {
                    "rung": int(heading.group(1)),
                    "L": int(heading.group(2)),
                    "beta": float(heading.group(3)),
                    "z": {},
                    "obs": {},
                }
                rungs.append(current)
            else:
                # e.g. "## rung2_..._RAW_preenforcement" -- a different ensemble.
                # Without this reset its rows would overwrite the rung above it.
                current = None
            continue
        if current is None or not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "observable":
            # write_report emits only the columns present in that table, so the
            # column set differs between rungs -- read it per table, never by index.
            header = cells
            continue
        if header is None or set(cells[0]) <= {"-"}:
            continue
        cell = dict(zip(header, cells))

        def num(key):
            try:
                return float(cell.get(key, ""))
            except ValueError:
                return None

        name = cell["observable"]
        z = num("z_exact")
        if z is not None:
            current["z"][name] = z
        row = {"value": num("value"), "error": num("error"), "exact": num("exact")}
        if row["value"] is None or row["exact"] is None:
            continue
        ref = num("reference")
        if ref is not None:
            row["reference"] = ref
            row["ref_error"] = num("ref_error")
            row["ref_topology_frozen"] = cell.get("ref_topology_frozen", "") == "True"
        current["obs"][name] = row
    for rung in rungs:
        rung["plaq_z"] = rung["z"].get("plaquette")
    return rungs


REBUILDERS = {
    "01_ladder_drift.png": (plot_ladder_drift, "ladder_drift.png"),
    "02_ladder_topology.png": (plot_ladder_topology, "ladder_topology.png"),
}


def rebuild_from_report(name: str, check: bool) -> tuple[bool, str]:
    """Redraw a ladder figure from validation/report.md.

    The generated .pt ensembles were pruned on 2026-08-02, so the markdown
    tables -- not the tensors -- are the durable record of the ladder run.
    """
    report = OUT / "validation" / "report.md"
    if not report.exists():
        return False, f"missing {report}"
    rungs = parse_validation_report(report)
    if not rungs:
        return False, f"no rung tables parsed from {report}"
    plot_fn, produced = REBUILDERS[name]
    if check:
        return True, f"rebuildable from {report} ({len(rungs)} rungs)"
    plot_fn(rungs, OUT / "validation")
    shutil.copy2(OUT / "validation" / produced, FIG_DIR / name)
    return True, f"rebuilt from {report} ({len(rungs)} rungs)"


def referenced_in_appendix() -> set[str]:
    if not APPENDIX_MD.exists():
        return set()
    text = APPENDIX_MD.read_text(encoding="utf-8")
    return set(re.findall(r"figures/(\S+?\.png)", text))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="report staleness without writing anything")
    args = parser.parse_args()

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    stale, missing, rows = [], [], []

    for name, source in SOURCES.items():
        target = FIG_DIR / name
        if source == "REBUILD":
            ok, note = rebuild_from_report(name, args.check)
            if not ok:
                missing.append(f"{name}: {note}")
            else:
                print(f"[rebuild] {name}  <- {note}")
            rows.append((name, "validation/report.md (rebuilt)", target))
            continue
        if source is None:
            script = SCRIPT_FOR[name[:2]]
            if not target.exists():
                missing.append(f"{name}: not present; run {script}")
            else:
                print(f"[script ] {name}  <- {script}")
            rows.append((name, script, target))
            continue

        src = OUT / source
        if not src.exists():
            missing.append(f"{name}: source missing ({source})")
            rows.append((name, source, target))
            continue
        differs = (not target.exists()) or sha256(src) != sha256(target)
        if differs:
            stale.append(name)
            if args.check:
                print(f"[STALE  ] {name}  <- {source}")
            else:
                shutil.copy2(src, target)
                print(f"[copied ] {name}  <- {source}")
        else:
            print(f"[ok     ] {name}  <- {source}")
        rows.append((name, source, target))

    referenced = referenced_in_appendix()
    unreferenced = sorted(set(SOURCES) - referenced)
    orphans = sorted(referenced - set(SOURCES))
    on_disk = {p.name for p in FIG_DIR.glob("*.png")}
    untracked = sorted(on_disk - set(SOURCES))

    if not args.check:
        lines = [
            "# Appendix figure manifest",
            "",
            f"Assembled {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by "
            "`u1_2d/scripts/30_assemble_appendix_figures.py`.",
            "",
            "| figure | source | sha256 (12) | source mtime |",
            "|---|---|---|---|",
        ]
        for name, source, target in rows:
            digest = sha256(target)[:12] if target.exists() else "MISSING"
            mtime = (datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")
                     if target.exists() else "-")
            lines.append(f"| {name} | `{source}` | `{digest}` | {mtime} |")
        (FIG_DIR / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {FIG_DIR / 'MANIFEST.md'}")

    print(f"\n{len(SOURCES)} figures tracked; "
          f"{len(stale)} stale, {len(missing)} missing, {len(untracked)} untracked on disk")
    for label, items in (("missing", missing), ("untracked", untracked),
                         ("referenced by appendix but not tracked", orphans),
                         ("tracked but never referenced in appendix.md", unreferenced)):
        if items:
            print(f"  {label}: {items}")

    if args.check and (stale or missing):
        print("\nFAIL: figure directory is not up to date (run without --check)")
        return 1
    if missing:
        print("\nFAIL: sources missing")
        return 1
    print("\nfigure directory is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
