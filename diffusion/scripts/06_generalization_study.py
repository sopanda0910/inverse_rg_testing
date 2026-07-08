"""Generalization diagnostic for the inverse-RG conditional diffusion model.

Probes whether the demo checkpoint (trained only on L=16 Wilson ensembles at
beta in {1, 2, 4, 8, 14.1464, 55.0237}) transfers across coupling scale and
lattice size:

  Part A -- matched-pair beta scan at fixed geometry L=16 -> L=32: base HMC at
            coarse beta_c, generate at beta_f = approx_matched_fine_beta(beta_c).
  Part B -- target-beta mismatch scan from a fixed base (L=16, beta=4): generate
            at betas above/below the matched value 14.1464 to find where the
            conditional model degrades (includes the tree-level beta=2 -> 8 case).
  Part C -- lattice-size scan at the fixed coupling pair 4 -> 14.1464: base
            lattices 16, 32, 64 generating 32, 64, 128.
  Part D -- upper-coupling continuation of Part A, ending at beta_c = 55.0237 ->
            beta_f = 218.58, fully outside the training coupling range.

Unlike 04_validate.py (whose reference HMC is deliberately topology-frozen to
demonstrate freezing), every reference ensemble here runs WITH instanton Q-hop
updates: the point is an unbiased ground truth for all observables including
<Q^2>. Validation reuses diffusion.validate.report.validate_ensemble (plaquette,
Wilson loops up to 12x12, Creutz ratios, Q, Q^2, chi_top, exact P(Q) chi^2, KS
tests vs reference).

    .venv/Scripts/python.exe diffusion/scripts/06_generalization_study.py
    .venv/Scripts/python.exe diffusion/scripts/06_generalization_study.py --smoke
    .venv/Scripts/python.exe diffusion/scripts/06_generalization_study.py --report-only
"""

import argparse
import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.lgt import make_action, run_hmc_ensemble
from diffusion.lgt.hmc import adapted_hmc_params
from diffusion.lgt.blocking import approx_matched_fine_beta
from diffusion.lgt.lattice import mean_plaquette, topological_charge
from diffusion.lgt.local_updates import retherm_sweeps
from diffusion.model.train import load_checkpoint
from diffusion.pipeline.ladder import generate_fine_from_coarse
from diffusion.validate.report import validate_ensemble, GEN_COLOR, REF_COLOR, INK, MUTED, GRID_COLOR
from diffusion.utils import set_seed, save_ensemble, load_ensemble, save_json

CHECKPOINT = "out/diffusion/demo/checkpoints/score_net.pt"
OUT_DIR = Path("out/diffusion/demo/generalization")
ACTION_TYPE = "wilson"

A_COARSE_BETAS = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0]
D_COARSE_BETAS = [14.1464, 55.0237]
B_TARGET_BETAS = [6.0, 10.0, 16.0, 20.0, 30.0, 55.0237]
MATCHED_PAIR = (4.0, 14.1464)


@dataclass
class Case:
    run_id: str
    part: str
    base_size: int
    base_beta: float
    target_beta: float
    n_configs: int
    n_reference: int
    note: str = ""


def build_cases(smoke: bool) -> list[Case]:
    n32, nref32 = (8, 16) if smoke else (128, 192)
    cases = []
    for bc in A_COARSE_BETAS:
        bf = approx_matched_fine_beta(bc, ACTION_TYPE)
        cases.append(Case(f"A_bc{bc:g}", "A", 16, bc, bf, n32, nref32,
                          f"matched pair {bc:g} -> {bf:.4f}"))
    for bc in D_COARSE_BETAS:
        bf = approx_matched_fine_beta(bc, ACTION_TYPE)
        cases.append(Case(f"D_bc{bc:g}", "D", 16, bc, bf, n32, nref32,
                          f"matched pair {bc:g} -> {bf:.4f}"
                          + (" (beyond training range)" if bf > 56 else "")))
    for bf in B_TARGET_BETAS:
        cases.append(Case(f"B_bt{bf:g}", "B", 16, 4.0, bf, n32, nref32,
                          f"mismatch: matched target is {MATCHED_PAIR[1]:g}"))
    cases.append(Case("B_bc2_bt8", "B", 16, 2.0, 8.0, n32, nref32,
                      "tree-level beta_f = 4 beta_c; matched target is 6.1052"))
    bc, bf = MATCHED_PAIR
    if smoke:
        cases.append(Case("C_L64", "C", 32, bc, bf, 8, 8, "size scan rung"))
    else:
        cases.append(Case("C_L64", "C", 32, bc, bf, 96, 96, "size scan rung"))
        cases.append(Case("C_L128", "C", 64, bc, bf, 64, 64, "size scan rung"))
    if smoke:
        keep = {"A_bc1", "A_bc4", "D_bc55.0237", "B_bt6", "B_bc2_bt8", "C_L64"}
        cases = [c for c in cases if c.run_id in keep]
    return cases


def hmc_ensemble_cached(path: Path, lattice_size: int, beta: float, n_configs: int,
                        device: str, smoke: bool) -> torch.Tensor:
    if path.exists():
        configs, _ = load_ensemble(path)
        if configs.shape[0] >= n_configs:
            return configs[:n_configs]
    step_size, n_steps = adapted_hmc_params(beta)
    # Hot starts at beta >= 8 leave a metastable local-defect plaquette deficit
    # (~ -0.002 to -0.01, tens of sigma) that Q-hops do not anneal and that
    # persists far beyond any affordable burn-in; a cold start with a longer
    # burn-in reproduces exact plaquette/Wilson values at every beta tested
    # (verified up to beta = 218.6 on L = 32). Burn 600 still left a few x 1e-4
    # positive residual (up to +7.5 sigma on the plaquette) at beta >= 20, so
    # those get 2000.
    hot = beta < 8.0
    burn_in = 30 if smoke else (200 if hot else (2000 if beta >= 20 else 600))
    t0 = time.time()
    configs, stats = run_hmc_ensemble(
        lattice_size,
        make_action(ACTION_TYPE, beta),
        n_configs=n_configs,
        n_chains=8 if smoke else 16,
        burn_in=burn_in,
        thin=2 if smoke else 5,
        n_steps=n_steps,
        step_size=step_size,
        device=device,
        topological_updates=True,
        hot_start=hot,
    )
    print(f"    HMC L={lattice_size} beta={beta:g}: {configs.shape[0]} configs, "
          f"acc {stats.acceptance_rate:.3f}, {'hot' if hot else 'cold'} start, "
          f"burn {burn_in}, {time.time()-t0:.0f}s", flush=True)
    save_ensemble(path, configs, {
        "beta": beta, "lattice_size": lattice_size, "action_type": ACTION_TYPE,
        "provenance": f"HMC with instanton Q-hop updates, {'hot' if hot else 'cold'} start, "
                      f"burn-in {burn_in} (unbiased topology and UV)",
    })
    return configs[:n_configs]


def run_case(case: Case, model, schedule, out: Path, device: str, smoke: bool) -> dict:
    record: dict = asdict(case)
    record["matched_target_beta"] = approx_matched_fine_beta(case.base_beta, ACTION_TYPE)
    record["mismatch_ratio"] = case.target_beta / record["matched_target_beta"]
    fine_size = case.base_size * 2

    base = hmc_ensemble_cached(
        out / "bases" / f"{ACTION_TYPE}_L{case.base_size}_beta{case.base_beta:g}.pt",
        case.base_size, case.base_beta, case.n_configs, device, smoke,
    )
    record["base_plaquette"] = float(mean_plaquette(base))
    record["base_q_squared"] = float(topological_charge(base).square().mean())

    gen_path = out / "generated" / f"{case.run_id}_{ACTION_TYPE}_L{fine_size}_beta{case.target_beta:g}.pt"
    if gen_path.exists():
        fine, meta = load_ensemble(gen_path)
        record.update(meta.get("timings", {}))
        record.update(meta.get("pre_retherm", {}))
        print(f"    loaded cached generation {gen_path.name}", flush=True)
    else:
        t0 = time.time()
        fine = generate_fine_from_coarse(
            model, schedule, base, case.target_beta,
            n_sampler_steps=24 if smoke else 200,
            n_corrector_steps=1,
            batch_size=8 if smoke else (16 if fine_size >= 128 else 32),
            device=device,
            consistency_weight=1.0,
            enforce_coarse_charge=True,
        )
        record["sample_seconds"] = time.time() - t0
        record["plaquette_pre_retherm"] = float(mean_plaquette(fine))
        record["q_squared_pre_retherm"] = float(topological_charge(fine).square().mean())
        t0 = time.time()
        fine = retherm_sweeps(fine, make_action(ACTION_TYPE, case.target_beta),
                              4 if smoke else 16, topological_updates=True)
        record["retherm_seconds"] = time.time() - t0
        save_ensemble(gen_path, fine, {
            "beta": case.target_beta, "lattice_size": fine_size, "action_type": ACTION_TYPE,
            "provenance": f"generalization study {case.run_id}: base L={case.base_size} "
                          f"beta={case.base_beta:g}, diffusion + 16 retherm sweeps (Q-hops on)",
            "timings": {k: record[k] for k in ("sample_seconds", "retherm_seconds")},
            "pre_retherm": {k: record[k] for k in ("plaquette_pre_retherm", "q_squared_pre_retherm")},
        })
        print(f"    generated {fine.shape[0]} configs L={fine_size} beta={case.target_beta:g} "
              f"in {record['sample_seconds']:.0f}s", flush=True)
    record["plaquette_generated"] = float(mean_plaquette(fine))
    record["q_squared_generated"] = float(topological_charge(fine).square().mean())

    reference = hmc_ensemble_cached(
        out / "reference" / f"{ACTION_TYPE}_L{fine_size}_beta{case.target_beta:g}.pt",
        fine_size, case.target_beta, case.n_reference, device, smoke,
    )

    rows = validate_ensemble(
        fine, case.target_beta, ACTION_TYPE,
        reference_configs=reference,
        label=case.run_id,
        output_dir=out / "figures",
    )
    record["rows"] = rows
    return record


def _json_clean(obj):
    if isinstance(obj, dict):
        return {k: _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_clean(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return float(obj)
    return obj


def _row(record: dict, name: str) -> dict:
    return next((r for r in record["rows"] if r["observable"] == name), {})


def _min_wilson_ks(record: dict) -> float:
    ps = [r["ks_p"] for r in record["rows"]
          if r["observable"].startswith("wilson_") and "ks_p" in r]
    return min(ps) if ps else float("nan")


def _style_axis(ax):
    ax.grid(axis="y", color=GRID_COLOR, lw=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)


def _z_panel(ax, x, records, observable, title, xlabel, tick_values=None):
    zs = [_row(r, observable).get("z_exact", float("nan")) for r in records]
    ax.axhspan(-2, 2, color=GRID_COLOR, alpha=0.45, zorder=0)
    ax.axhline(0.0, color=INK, lw=0.8, zorder=1)
    ax.plot(x, zs, "o-", color=GEN_COLOR, ms=6, lw=1.6, zorder=3)
    ax.set_xscale("log")
    if tick_values is not None:
        ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
        ax.set_xticks(tick_values)
        ax.set_xticklabels([f"{v:.3g}" for v in tick_values], fontsize=7)
    ax.set_title(title, fontsize=10, color=INK)
    ax.set_xlabel(xlabel, fontsize=9, color=INK)
    ax.set_ylabel("z vs exact", fontsize=9, color=INK)
    _style_axis(ax)


def make_summary_figures(records: dict, out: Path) -> None:
    matched = sorted(
        (r for r in records.values() if r["part"] in ("A", "D")),
        key=lambda r: r["base_beta"],
    )
    if matched:
        x = [r["base_beta"] for r in matched]
        fig, axes = plt.subplots(2, 2, figsize=(10, 7))
        panels = [("plaquette", "Plaquette"), ("wilson_2x2", r"$W(2\times2)$"),
                  ("wilson_4x4", r"$W(4\times4)$"), ("Q^2", r"$\langle Q^2 \rangle$")]
        for ax, (obs, title) in zip(axes.flat, panels):
            _z_panel(ax, x, matched, obs, title, r"coarse $\beta_c$ (matched $\beta_f$ generated)",
                     tick_values=x)
        extrap = [r for r in matched if r["target_beta"] > 56]
        for r in extrap:
            for ax in axes.flat:
                ax.axvline(r["base_beta"], color=MUTED, lw=0.9, ls=":")
        if extrap:
            axes.flat[0].annotate("beyond training range", fontsize=8, color=MUTED,
                                  xy=(extrap[0]["base_beta"], 0.06),
                                  xycoords=("data", "axes fraction"),
                                  ha="right", va="bottom", rotation=90)
        fig.suptitle("Matched-pair beta scan (L=16 base -> L=32 generated): z-scores vs exact",
                     fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        fig.savefig(out / "fig_matched_scan.png", dpi=130)
        plt.close(fig)

    mism = sorted(
        (r for r in records.values() if r["part"] in ("A", "B", "D") and r["base_beta"] == 4.0),
        key=lambda r: r["target_beta"],
    )
    b2 = [r for r in records.values() if r["run_id"] == "B_bc2_bt8"]
    if mism:
        x = [r["target_beta"] for r in mism]
        fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
        panels = [("plaquette", "Plaquette"), ("wilson_2x2", r"$W(2\times2)$"),
                  ("Q^2", r"$\langle Q^2 \rangle$")]
        ticks = [v for v in x if abs(v - MATCHED_PAIR[1]) > 1.5] + [8.0]
        for ax, (obs, title) in zip(axes, panels):
            _z_panel(ax, x, mism, obs, title, r"target $\beta_f$ (base fixed at $\beta_c=4$)",
                     tick_values=sorted(ticks))
            ax.axvline(MATCHED_PAIR[1], color=INK, lw=1.0, ls="--")
            ax.annotate("matched", fontsize=8, color=INK, rotation=90,
                        xy=(MATCHED_PAIR[1], 0.03), xycoords=("data", "axes fraction"),
                        ha="right", va="bottom")
            if b2:
                z2 = _row(b2[0], obs).get("z_exact", float("nan"))
                ax.plot([8.0], [z2], "s", color=REF_COLOR, ms=7, mfc="none", mew=1.8,
                        label=r"$\beta_c=2 \to 8$ (tree level)")
        axes[0].legend(fontsize=8, frameon=False)
        fig.suptitle("Target-coupling mismatch scan: bias vs how far the target sits from the matched coupling",
                     fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        fig.savefig(out / "fig_mismatch_scan.png", dpi=130)
        plt.close(fig)

    size = sorted(
        (r for r in records.values()
         if r["base_beta"] == MATCHED_PAIR[0]
         and abs(r["target_beta"] - MATCHED_PAIR[1]) < 1e-3
         and r["part"] in ("A", "C")),
        key=lambda r: r["base_size"],
    )
    if len(size) > 1:
        x = [2 * r["base_size"] for r in size]
        fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
        panels = [("plaquette", "Plaquette"), ("wilson_4x4", r"$W(4\times4)$"),
                  ("Q^2", r"$\langle Q^2 \rangle$")]
        for ax, (obs, title) in zip(axes, panels):
            _z_panel(ax, x, size, obs, title, r"generated lattice size $L_f$")
            ax.set_xscale("log", base=2)
            ax.set_xticks(x)
            ax.set_xticklabels([str(v) for v in x])
        fig.suptitle(r"Lattice-size scan at fixed coupling pair $\beta_c=4 \to \beta_f=14.1464$"
                     " (training saw only L=16)", fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        fig.savefig(out / "fig_size_scan.png", dpi=130)
        plt.close(fig)


def write_summary_tables(records: dict, out: Path) -> None:
    lines = ["# Generalization study: summary tables", ""]
    lines.append(
        "All references are HMC with instanton Q-hop updates (unbiased topology). "
        "z columns are z-scores against exact character-expansion values; "
        "`min KS p` is the smallest two-sample KS p-value across all measured Wilson loop sizes."
    )
    lines.append("")
    header = ("| run | base (L, beta) | target beta | matched beta | beta ratio | plaq z | "
              "W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p |")
    for part, title in [("A", "Part A: matched-pair beta scan (L=16 -> L=32)"),
                        ("D", "Part D: upper-coupling matched pairs (L=16 -> L=32)"),
                        ("B", "Part B: target-coupling mismatch (base L=16)"),
                        ("C", "Part C: lattice-size scan (pair 4 -> 14.1464)")]:
        rows = sorted((r for r in records.values() if r["part"] == part),
                      key=lambda r: (r["base_size"], r["base_beta"], r["target_beta"]))
        if not rows:
            continue
        lines += [f"## {title}", "", header, "|" + "---|" * 14]
        for r in rows:
            cells = [
                r["run_id"],
                f"({r['base_size']}, {r['base_beta']:g})",
                f"{r['target_beta']:g}",
                f"{r['matched_target_beta']:.4g}",
                f"{r['mismatch_ratio']:.2f}",
            ]
            for obs in ("plaquette", "wilson_2x2", "wilson_4x4", "wilson_8x8",
                        "Q", "Q^2", "chi_top ((<Q^2>-<Q>^2)/V)"):
                z = _row(r, obs).get("z_exact")
                cells.append(f"{z:+.2f}" if z is not None and not math.isnan(z) else "-")
            chi2 = _row(r, "Q histogram vs exact P(Q)").get("chi2_p")
            cells.append(f"{chi2:.3f}" if chi2 is not None else "-")
            ks = _min_wilson_ks(r)
            cells.append(f"{ks:.3f}" if not math.isnan(ks) else "-")
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    (out / "summary_tables.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="tiny end-to-end plumbing test")
    parser.add_argument("--report-only", action="store_true", help="rebuild figures/tables from summary.json")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--cases", default=None,
                        help="comma-separated run_ids to run (e.g. A_bc4,A_bc2); others left untouched")
    parser.add_argument("--checkpoint", default=None, help="override checkpoint path")
    args = parser.parse_args()
    out = Path(args.out_dir) if args.out_dir else (OUT_DIR / "smoke" if args.smoke else OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    records: dict = {}
    if summary_path.exists():
        records = json.loads(summary_path.read_text(encoding="utf-8"))

    if not args.report_only:
        set_seed(1234)
        device = "cpu"
        model, schedule = load_checkpoint(args.checkpoint or CHECKPOINT, device)
        cases = build_cases(args.smoke)
        if args.cases:
            wanted = {v.strip() for v in args.cases.split(",")}
            missing = wanted - {c.run_id for c in cases}
            if missing:
                raise SystemExit(f"unknown case ids: {sorted(missing)}")
            cases = [c for c in cases if c.run_id in wanted]
        print(f"{len(cases)} cases, output -> {out}", flush=True)
        for i, case in enumerate(cases):
            if case.run_id in records and "rows" in records[case.run_id]:
                print(f"[{i+1}/{len(cases)}] {case.run_id}: already done, skipping", flush=True)
                continue
            print(f"[{i+1}/{len(cases)}] {case.run_id}: base L={case.base_size} "
                  f"beta={case.base_beta:g} -> L={case.base_size*2} beta={case.target_beta:g} "
                  f"({case.note})", flush=True)
            t0 = time.time()
            try:
                records[case.run_id] = _json_clean(run_case(case, model, schedule, out, device, args.smoke))
            except Exception as exc:
                records[case.run_id] = {**asdict(case), "error": f"{type(exc).__name__}: {exc}"}
                print(f"    FAILED: {exc}", flush=True)
            records[case.run_id]["total_seconds"] = time.time() - t0
            save_json(summary_path, records)
            print(f"    case done in {time.time()-t0:.0f}s", flush=True)

    complete = {k: v for k, v in records.items() if "rows" in v}
    make_summary_figures(complete, out)
    write_summary_tables(complete, out)
    print(f"summary: {summary_path}")
    print(f"tables:  {out / 'summary_tables.md'}")


if __name__ == "__main__":
    main()
