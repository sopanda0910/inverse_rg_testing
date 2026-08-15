"""Generalization diagnostic for the inverse-RG conditional diffusion model.

PARALLELISM (--shard) -- read this before a long rerun
------------------------------------------------------
Why: this stage is latency-bound, not throughput-bound. One case alternates
16-chain reference HMC with batch-32 ladder sampling at L=32-64; measured on
the RTX 5060 that holds the GPU at ~32% and the CPU at ~3%. Neither processor
is saturated and no per-case setting can fix that -- the batches are small
because the physics says so. The only way to use the machine is to run several
cases at once.

Recipe (N = 3 or 4 on an 8 GiB card; each shard holds its own CUDA context and
model, ~0.5-0.7 GiB, and the win flattens once the GPU actually saturates):

    for i in 0 1 2 3:  06_generalization_study.py --shard i/4 --out-dir DIR ...
    wait for all four
    06_generalization_study.py --merge-shards --out-dir DIR ...

Why it is safe, precisely:
  * cases are independent -- each derives its own seed from `seed + crc32(run_id)`,
    so a case computes the same thing regardless of which shard runs it or what
    order it runs in. Sharding is a scheduling change, not a numerical one.
  * shards never share a summary file. Each writes summary.shard<I>.json;
    --merge-shards folds them into summary.json. Without this the shards would
    race: save_json is atomic, so no file is ever corrupt, but last-writer-wins
    would silently drop the other shards' cases.
  * a shard reads summary.json first, so it still skips cases an earlier
    unsharded run completed. Resume works across a change of shard count.
  * figures/tables are DEFERRED in a shard. A shard sees only its slice, and
    the scan figures built from a fraction of the cases would look perfectly
    valid. Only --merge-shards draws them.

The one genuine race is benign: two shards can generate the same cached base
ensemble at once (bases/ is keyed by (L, beta), which several cases share).
save_ensemble writes to a temp file and renames, so the loser just wastes the
work; nothing is corrupted. Pre-populating bases/ avoids even that.

Expected: cases cost ~160 s (E/F, burn_in 600) to ~500 s (D, burn_in 2000), so
round-robin interleaving -- not contiguous blocks -- is what keeps shards even.
This mirrors 01_generate_data.py --shard, which took data generation from
21.7 min to 3.2.

As of the v6 checkpoint (u1_2d/configs/demo_v6.yaml), training couplings
are drawn continuously (log-uniform, `data.random_rungs`, see
`diffusion.utils.expand_rungs`), not from a fixed discrete grid: 64 rungs at
L=16 spanning beta in [1.0, 57.2], 12 at L=32 spanning [2.2, 52.6], 6 at L=8
spanning [1.4, 2.5], plus 4 fixed sector-augmented anchors at L=16 (beta =
14.1464, 25, 40, 55.0237). Inside that coverage, "off-grid" no longer exists
in the old sense -- any beta in ~[1, 60] sits close to some training draw.
Genuine generalization now means either beta > ~60 (past every training
draw) or a lattice size never trained on at all (L=64, L=128). Below, "in
range" means beta_f is inside the trained L=16 span; it does NOT mean the
target lattice size was densely trained -- L=32 only got 12 rungs vs L=16's
64.

  Part A -- matched-pair beta scan at fixed geometry L=16 -> L=32: base HMC at
            coarse beta_c, generate at beta_f = approx_matched_fine_beta(beta_c).
            beta_f in [1.49, 30.4] here -- fully inside the training range, so
            this is interpolation, useful as a baseline rather than a
            generalization claim.
  Part B -- target-beta mismatch scan from a fixed base (L=16, beta=4): generate
            at betas above/below the matched value 14.1464 to find where the
            conditional model degrades (includes the tree-level beta=2 -> 8 case).
            Targets stay inside the training range throughout; this probes an
            intentionally wrong coarse/fine pairing, not an unseen coupling.
  Part C -- lattice-size scan at the fixed coupling pair 4 -> 14.1464: base
            lattices 16, 32, 64 generating 32, 64, 128. The coupling pair is
            in-range, but L=64/L=128 were never trained on at any coupling --
            this is the volume-extrapolation track, orthogonal to beta.
  Part D -- upper-coupling continuation of Part A, ending at beta_c = 55.0237 ->
            beta_f = 218.58: the first point (beta_f=55.0) is still inside the
            training range, the rest (78.5 upward) cross fully outside it.
  Part E -- originally designed as an off-grid probe between the OLD discrete
            training anchors; under continuous training the lower couplings
            here (beta_f up to ~45.6) are now redundant with Part A
            (interpolation, not off-grid). The upper couplings (bc=18/35/45 ->
            beta_f = 70.5/138.5/178.5) do sit past the training edge, in the
            same regime as Part D.
  Part F -- the one-model demonstration: matched pairs far beyond any training
            coupling (beta_f ~ 398.5 and ~872.8, i.e. ~7x and ~15x the training
            maximum) plus a rung that is simultaneously large-beta and
            large-volume (beta_f=218.6 at L=64). This is the only track built
            to demonstrate generalization well past anything trained.

Unlike 04_validate.py (whose reference HMC is deliberately topology-frozen to
demonstrate freezing), every reference ensemble here runs WITH instanton Q-hop
updates: the point is an unbiased ground truth for all observables including
<Q^2>. Validation reuses diffusion.validate.report.validate_ensemble (plaquette,
Wilson loops up to 12x12, Creutz ratios, Q, Q^2, chi_top, exact P(Q) chi^2, KS
tests vs reference).

    .venv/Scripts/python.exe u1_2d/scripts/06_generalization_study.py
    .venv/Scripts/python.exe u1_2d/scripts/06_generalization_study.py --smoke
    .venv/Scripts/python.exe u1_2d/scripts/06_generalization_study.py --report-only
"""

import argparse
import json
import math
import time
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from u1_2d.lgt import make_action, run_hmc_ensemble
from u1_2d.lgt.hmc import adapted_hmc_params
from u1_2d.lgt.blocking import approx_matched_fine_beta
from u1_2d.lgt.lattice import mean_plaquette, topological_charge
from u1_2d.lgt.local_updates import retherm_sweeps
from u1_2d.model.train import load_checkpoint
from u1_2d.pipeline.ladder import (
    generate_fine_from_coarse,
    apply_coarse_charge,
    conjugate_symmetrize,
    resample_exact_sectors,
)
from u1_2d.validate.report import validate_ensemble, GEN_COLOR, REF_COLOR, INK, MUTED, GRID_COLOR
from u1_2d.utils import set_seed, save_ensemble, load_ensemble, save_json

CHECKPOINT = "out/u1_2d/checkpoints/score_net.pt"
# Chain counts of every HMC ensemble this study builds. Named rather than
# inlined because validate_ensemble needs them too: without them the study
# reports fixed 20-bin errors instead of the per-chain tau_int errors the
# honesty conventions describe, which is review item M4. The generated
# ensemble inherits the base's chain-major layout (charge enforcement,
# exact-sector resampling and retherm sweeps are all per-configuration and
# order-preserving), so the same count applies to it.
HMC_N_CHAINS = 16
SMOKE_N_CHAINS = 8
OUT_DIR = Path("out/u1_2d/demo/generalization")
ACTION_TYPE = "wilson"

A_COARSE_BETAS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
D_COARSE_BETAS = [14.1464, 20.0, 30.0, 40.0, 55.0237]
# Originally an off-grid probe against the OLD discrete training anchors
# {1, 2, 4, 8, 14.1464, 55.0237}. Under v6's continuous-beta training this no
# longer measures off-grid generalization for the lower entries (bc <= 11.8,
# beta_f <= 21.5): the training draws now densely cover that whole span, so
# those cases are interpolation, redundant with Part A. Only the upper entries
# (bc=18/35/45 -> beta_f=70.5/138.5/178.5) sit past the trained beta_f range --
# see the module docstring for the full breakdown.
E_COARSE_BETAS = [1.2, 2.7, 3.4, 4.5, 5.8, 9.0, 11.8, 18.0, 35.0, 45.0]
# Part G: the crossover window, added 2026-08-14 because the headline
# thermalization claim was thin exactly where it needs to be strongest.
#
# The claim is "the diffusion seed costs less than a fresh HMC chain". It is
# only persuasive at couplings where fresh HMC still WORKS -- above the
# freezing coupling (beta_f ~ 8.8 here) HMC never thermalizes at all, so the
# comparison stops being a speedup and becomes a statement that one method
# finishes and the other does not. Before this part, the matched-pair scan had
# exactly four rungs in 4.4 <= beta_f <= 10, of which only two showed a large
# margin with HMC still ergodic (beta_f = 4.44 at 7x, 6.11 at 25x) -- and then
# a gap straight to 8.80, where hot starts already fail. Two points do not
# establish a trend.
#
# These six coarse couplings map to beta_f = 5.41, 6.47, 7.22, 8.00, 8.39,
# 9.61, which fills that gap and brackets the freezing coupling from both
# sides, so the speedup-vs-beta curve is measured through the crossover rather
# than inferred across it.
G_COARSE_BETAS = [1.8, 2.1, 2.3, 2.5, 2.6, 2.9]
# Part F: the one-model demonstration — matched pairs far beyond any training
# coupling (targets ~7x and ~15x the training maximum) plus a rung that is
# simultaneously large-beta and large-volume.
F_CASES = [
    (16, 100.0),
    (16, 218.58),
    (32, 55.0237),
]
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
    for bc in E_COARSE_BETAS:
        bf = approx_matched_fine_beta(bc, ACTION_TYPE)
        cases.append(Case(f"E_bc{bc:g}", "E", 16, bc, bf, n32, nref32,
                          f"out-of-sample matched pair {bc:g} -> {bf:.4f}"))
    for bc in G_COARSE_BETAS:
        bf = approx_matched_fine_beta(bc, ACTION_TYPE)
        cases.append(Case(f"G_bc{bc:g}", "G", 16, bc, bf, n32, nref32,
                          f"crossover-window matched pair {bc:g} -> {bf:.4f}"))
    for base_size, bc in F_CASES:
        bf = approx_matched_fine_beta(bc, ACTION_TYPE)
        n = 8 if smoke else 64
        nref = 8 if smoke else 96
        cases.append(Case(f"F_L{base_size*2}_bc{bc:g}", "F", base_size, bc, bf, n, nref,
                          f"extrapolation demo {bc:g} -> {bf:.4f} at L={base_size*2}"))
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
        n_chains=SMOKE_N_CHAINS if smoke else HMC_N_CHAINS,
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
    # Ensembles are CPU-resident by convention in this codebase: the cache path
    # loads to CPU, and generate_fine_from_coarse moves each chunk to the compute
    # device itself and returns CPU. run_hmc_ensemble is the one function that
    # hands back tensors on its `device`, so normalize here -- otherwise on cuda
    # the base sits on the GPU, the generated fine ensemble on the CPU, and every
    # case dies at the first q_raw - q_base.
    return configs[:n_configs].cpu()


def run_case(case: Case, model, schedule, out: Path, device: str, smoke: bool,
             seed: int = 1234, physics_blend: float = 0.0,
             physics_blend_beta_min: float = 0.0, retherm_qhops: bool = False,
             symmetrize_base: bool = False, sector_mode: str = "transport") -> dict:
    record: dict = asdict(case)
    record["matched_target_beta"] = approx_matched_fine_beta(case.base_beta, ACTION_TYPE)
    record["mismatch_ratio"] = case.target_beta / record["matched_target_beta"]
    fine_size = case.base_size * 2

    base = hmc_ensemble_cached(
        out / "bases" / f"{ACTION_TYPE}_L{case.base_size}_beta{case.base_beta:g}.pt",
        case.base_size, case.base_beta, case.n_configs, device, smoke,
    )
    if symmetrize_base:
        sym_gen = torch.Generator().manual_seed(
            (seed + zlib.crc32((case.run_id + "_sym").encode())) % (2**31))
        base = conjugate_symmetrize(base, generator=sym_gen)
        record["symmetrize_base"] = True
    record["base_plaquette"] = float(mean_plaquette(base))
    record["base_q_squared"] = float(topological_charge(base).square().mean())

    gen_path = out / "generated" / f"{case.run_id}_{ACTION_TYPE}_L{fine_size}_beta{case.target_beta:g}.pt"
    if gen_path.exists():
        fine, meta = load_ensemble(gen_path)
        record.update(meta.get("timings", {}))
        record.update(meta.get("pre_retherm", {}))
        record.update(meta.get("raw_topology", {}))
        print(f"    loaded cached generation {gen_path.name}", flush=True)
    else:
        # Per-case seed: results do not depend on case order or subsetting, and
        # different --seed values give genuinely independent sampler noise (a fixed
        # global seed lets identical retherm RNG synchronously couple two runs at
        # high beta, hiding model differences).
        case_seed = (seed + zlib.crc32(case.run_id.encode())) % (2**31)
        record["seed"] = case_seed
        set_seed(case_seed)
        t0 = time.time()
        fine = generate_fine_from_coarse(
            model, schedule, base, case.target_beta,
            n_sampler_steps=24 if smoke else 200,
            n_corrector_steps=1,
            batch_size=8 if smoke else (16 if fine_size >= 128 else 32),
            device=device,
            consistency_weight=1.0,
            enforce_coarse_charge=False,
            physics_blend_coef=physics_blend,
            physics_blend_beta_min=physics_blend_beta_min,
        )
        record["sample_seconds"] = time.time() - t0
        record["physics_blend_coef"] = physics_blend
        record["physics_blend_beta_min"] = physics_blend_beta_min
        record["retherm_qhops"] = retherm_qhops
        # Model-level topology transport, measured before the deterministic charge
        # map hides it (ideal transport: Q_fine == Q_base, since blocking preserves Q).
        q_base = topological_charge(base)
        q_raw = topological_charge(fine)
        dq = (q_raw - q_base).abs()
        record["q_match_rate_raw"] = float((dq == 0).float().mean())
        record["mean_abs_dq_raw"] = float(dq.mean())
        record["q_squared_raw"] = float(q_raw.square().mean())
        record["sector_mode"] = sector_mode
        if sector_mode == "exact":
            sec_gen = torch.Generator().manual_seed(
                (seed + zlib.crc32((case.run_id + "_sector").encode())) % (2**31))
            fine = resample_exact_sectors(fine, case.target_beta, ACTION_TYPE,
                                          generator=sec_gen)
        else:
            fine = apply_coarse_charge(fine, q_base)
        record["plaquette_pre_retherm"] = float(mean_plaquette(fine))
        record["q_squared_pre_retherm"] = float(topological_charge(fine).square().mean())
        t0 = time.time()
        # Honest default: no Q-hops during retherm, so rethermalization cannot
        # manufacture topology -- the model + structural charge transport must
        # carry it (the README's recommended test setting). --retherm-qhops
        # restores the v6 behavior for A/B comparisons.
        fine = retherm_sweeps(fine, make_action(ACTION_TYPE, case.target_beta),
                              4 if smoke else 16, topological_updates=retherm_qhops)
        record["retherm_seconds"] = time.time() - t0
        save_ensemble(gen_path, fine, {
            "beta": case.target_beta, "lattice_size": fine_size, "action_type": ACTION_TYPE,
            "provenance": f"generalization study {case.run_id}: base L={case.base_size} "
                          f"beta={case.base_beta:g}"
                          f"{' (C-symmetrized)' if symmetrize_base else ''}, "
                          f"diffusion (case seed {case_seed}) + "
                          f"{'exact-sector resampling' if sector_mode == 'exact' else 'charge enforcement'}"
                          f" + retherm sweeps (Q-hops {'on' if retherm_qhops else 'off'})",
            "timings": {k: record[k] for k in ("sample_seconds", "retherm_seconds")},
            "pre_retherm": {k: record[k] for k in ("plaquette_pre_retherm", "q_squared_pre_retherm")},
            "raw_topology": {k: record[k] for k in
                             ("q_match_rate_raw", "mean_abs_dq_raw", "q_squared_raw", "seed")},
        })
        print(f"    generated {fine.shape[0]} configs L={fine_size} beta={case.target_beta:g} "
              f"in {record['sample_seconds']:.0f}s", flush=True)
    record["plaquette_generated"] = float(mean_plaquette(fine))
    record["q_squared_generated"] = float(topological_charge(fine).square().mean())

    reference = hmc_ensemble_cached(
        out / "reference" / f"{ACTION_TYPE}_L{fine_size}_beta{case.target_beta:g}.pt",
        fine_size, case.target_beta, case.n_reference, device, smoke,
    )

    n_chains = SMOKE_N_CHAINS if smoke else HMC_N_CHAINS
    rows = validate_ensemble(
        fine, case.target_beta, ACTION_TYPE,
        reference_configs=reference,
        label=case.run_id,
        output_dir=out / "figures",
        n_chains=n_chains,
        ref_n_chains=n_chains,
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

    raw = sorted(
        (r for r in records.values()
         if r["part"] in ("A", "D") and r.get("q_match_rate_raw") is not None),
        key=lambda r: r["base_beta"],
    )
    if raw:
        x = [r["base_beta"] for r in raw]
        fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.0))
        axes[0].plot(x, [r["q_match_rate_raw"] for r in raw], "o-", color=GEN_COLOR, ms=6, lw=1.6)
        axes[0].set_ylim(0, 1)
        axes[0].set_title("P(Q_fine = Q_base) before enforcement", fontsize=10, color=INK)
        axes[0].set_ylabel("match rate", fontsize=9, color=INK)
        axes[1].plot(x, [r["q_squared_raw"] for r in raw], "o-", color=GEN_COLOR, ms=6, lw=1.6,
                     label="raw sampler")
        axes[1].plot(x, [r["base_q_squared"] for r in raw], "s--", color=REF_COLOR, ms=5, lw=1.2,
                     mfc="none", label="base (ideal transport)")
        axes[1].set_yscale("log")
        axes[1].set_title(r"$\langle Q^2 \rangle$ of the raw sampler output", fontsize=10, color=INK)
        axes[1].legend(fontsize=8, frameon=False)
        for ax in axes:
            ax.set_xscale("log")
            ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.set_xticks(x)
            ax.set_xticklabels([f"{v:.3g}" for v in x], fontsize=7)
            ax.set_xlabel(r"coarse $\beta_c$", fontsize=9, color=INK)
            _style_axis(ax)
        fig.suptitle("Model-level topology transport (pre-enforcement, pre-retherm)", fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        fig.savefig(out / "fig_raw_topology.png", dpi=130)
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
              "W(2x2) z | W(4x4) z | W(8x8) z | Q z | Q^2 z | chi_top z | P(Q) chi2 p | min KS p | "
              "raw Q match | raw Q^2 (base) |")
    for part, title in [("A", "Part A: matched-pair beta scan (L=16 -> L=32)"),
                        ("D", "Part D: upper-coupling matched pairs (L=16 -> L=32)"),
                        ("E", "Part E: out-of-sample matched pairs (bases and targets mid-gap between training couplings)"),
                        ("G", "Part G: crossover window (beta_f 5.4-9.6, where fresh HMC still thermalizes)"),
                        ("F", "Part F: extrapolation demo (targets far beyond the training range, incl. large volume)"),
                        ("B", "Part B: target-coupling mismatch (base L=16)"),
                        ("C", "Part C: lattice-size scan (pair 4 -> 14.1464)")]:
        rows = sorted((r for r in records.values() if r["part"] == part),
                      key=lambda r: (r["base_size"], r["base_beta"], r["target_beta"]))
        if not rows:
            continue
        lines += [f"## {title}", "", header, "|" + "---|" * 16]
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
            match = r.get("q_match_rate_raw")
            cells.append(f"{match:.2f}" if match is not None else "-")
            q2r = r.get("q_squared_raw")
            cells.append(f"{q2r:.2f} ({r['base_q_squared']:.2f})" if q2r is not None else "-")
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
    parser.add_argument("--physics-blend", type=float, default=0.0, dest="physics_blend",
                        help="exact-score blend coefficient at sampling time (0 = off)")
    parser.add_argument("--physics-blend-beta-min", type=float, default=0.0,
                        dest="physics_blend_beta_min",
                        help="gate the exact-score blend off below this beta (0 = ungated)")
    parser.add_argument("--retherm-qhops", action="store_true", dest="retherm_qhops",
                        help="include instanton Q-hop proposals in rethermalization "
                        "(v6 behavior); default OFF -- the honest topology test")
    parser.add_argument("--symmetrize-base", action="store_true", dest="symmetrize_base",
                        help="charge-conjugate a random half of each coarse base "
                        "(exact antithetic symmetrization: enforces P(Q) = P(-Q))")
    parser.add_argument("--sector-mode", choices=("transport", "exact"),
                        default="transport",
                        help="'transport' (default): fine sector = coarse config's "
                        "sector; 'exact': resample sectors from the exact P(Q) at "
                        "the TARGET coupling (correct by construction, incl. "
                        "mismatched targets)")
    parser.add_argument("--sigma-floor-coef", type=float, default=None, dest="sigma_floor_coef",
                        help="override the checkpoint schedule's beta-aware noise floor "
                        "coefficient at sampling time (safe when --physics-blend > 0)")
    parser.add_argument("--device", default="cpu",
                        help="torch device for the sampler. Defaults to cpu, which is "
                             "what every published run of this script used -- pass cuda "
                             "to put the ladder sampling on a GPU (this stage is "
                             "sampler-dominated, so it is the one that benefits).")
    parser.add_argument("--seed", type=int, default=1234,
                        help="base seed; each case derives its own seed from this + run_id, "
                        "so different values give independent sampler noise")
    parser.add_argument("--shard", default=None, metavar="I/N",
                        help="run only cases with index %% N == I, writing "
                        "summary.shard<I>.json instead of summary.json. Cases are "
                        "independent and each derives its own seed from run_id, so "
                        "sharding changes nothing about the results -- see the "
                        "PARALLELISM note in this file's header for the recipe. "
                        "Combine the shards with --merge-shards.")
    parser.add_argument("--merge-shards", action="store_true",
                        help="fold summary.shard*.json into summary.json, delete "
                        "them, and build the figures/tables from the merged set "
                        "(run once after a sharded run)")
    args = parser.parse_args()
    shard_index = shard_count = None
    if args.shard is not None:
        shard_index, shard_count = (int(x) for x in args.shard.split("/"))
        if not 0 <= shard_index < shard_count:
            parser.error(f"--shard {args.shard}: need 0 <= I < N")
    out = Path(args.out_dir) if args.out_dir else (OUT_DIR / "smoke" if args.smoke else OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    records: dict = {}
    if summary_path.exists():
        records = json.loads(summary_path.read_text(encoding="utf-8"))
    # A shard writes its own file so concurrent shards cannot clobber each
    # other's results (save_json is atomic, but last-writer-wins would still
    # drop the other shards' cases). It still READS summary.json above, so a
    # sharded rerun skips work an earlier unsharded run already finished.
    if shard_count is not None:
        summary_path = out / f"summary.shard{shard_index}.json"
        if summary_path.exists():
            records.update(json.loads(summary_path.read_text(encoding="utf-8")))
    if args.merge_shards:
        for shard_file in sorted(out.glob("summary.shard*.json")):
            records.update(json.loads(shard_file.read_text(encoding="utf-8")))
            shard_file.unlink()
            print(f"merged {shard_file.name}", flush=True)
        summary_path = out / "summary.json"
        save_json(summary_path, records)

    if not args.report_only:
        set_seed(args.seed)
        from u1_2d.utils import configure_device

        device = args.device
        print(f"device: {configure_device(device)}", flush=True)
        model, schedule = load_checkpoint(args.checkpoint or CHECKPOINT, device)
        if args.sigma_floor_coef is not None:
            from u1_2d.model.schedule import GeometricNoiseSchedule

            schedule = GeometricNoiseSchedule(
                schedule.sigma_min, schedule.sigma_max,
                sigma_min_beta_coef=args.sigma_floor_coef,
            )
        cases = build_cases(args.smoke)
        if args.cases:
            wanted = {v.strip() for v in args.cases.split(",")}
            missing = wanted - {c.run_id for c in cases}
            if missing:
                raise SystemExit(f"unknown case ids: {sorted(missing)}")
            cases = [c for c in cases if c.run_id in wanted]
        if shard_count is not None:
            # Round-robin, not contiguous blocks: the expensive cases cluster by
            # family (the D_* set carries burn_in 2000 and costs ~500 s against
            # ~160 s for E_*), so interleaving spreads them evenly instead of
            # loading one shard with all of them.
            cases = [c for i, c in enumerate(cases) if i % shard_count == shard_index]
            print(f"shard {shard_index}/{shard_count}: {len(cases)} cases", flush=True)
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
                records[case.run_id] = _json_clean(
                    run_case(case, model, schedule, out, device, args.smoke,
                             seed=args.seed, physics_blend=args.physics_blend,
                             physics_blend_beta_min=args.physics_blend_beta_min,
                             retherm_qhops=args.retherm_qhops,
                             symmetrize_base=args.symmetrize_base,
                             sector_mode=args.sector_mode)
                )
            except Exception as exc:
                records[case.run_id] = {**asdict(case), "error": f"{type(exc).__name__}: {exc}"}
                print(f"    FAILED: {exc}", flush=True)
            records[case.run_id]["total_seconds"] = time.time() - t0
            save_json(summary_path, records)
            print(f"    case done in {time.time()-t0:.0f}s", flush=True)

    if shard_count is not None:
        # A shard only holds its own slice, so the scan figures would be built
        # from a fraction of the cases and silently look fine. --merge-shards
        # makes them once the full set is back together.
        print(f"shard summary: {summary_path}", flush=True)
        print("figures/tables deferred -- rerun with --merge-shards", flush=True)
        return

    complete = {k: v for k, v in records.items() if "rows" in v}
    make_summary_figures(complete, out)
    write_summary_tables(complete, out)
    print(f"summary: {summary_path}")
    print(f"tables:  {out / 'summary_tables.md'}")


if __name__ == "__main__":
    main()
