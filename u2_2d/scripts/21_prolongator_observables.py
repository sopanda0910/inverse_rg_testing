"""Stage 21: do the geometric prolongators match the learned one on the
observables that matter, not just the plaquette?

`17_prolongator_baseline.py` settled the local-observable question and the answer
was uncomfortable: on the plaquette and small Wilson loops the learned lift is
NOT better than a five-line geometric map once the exact conditional SU(2)
sampler has run. `smear` finishes 7x closer to exact at both rungs, `halve` 18x
closer at L=32, and t_therm is 0 for every arm. Worse, sector transport is
imposed by `apply_coarse_charge` and is therefore identical across arms -- at
L=64 every prolongator carries <Q^2> = 1.141 to three decimals -- so topological
reach is a property of the LADDER, not of the model.

That leaves exactly one place for the learned lift to earn its keep: the
observables 30 SU(2) sweeps plus 10 rethermalization sweeps cannot repair.
Local updates fix short-distance structure fast; they move long-distance
correlations slowly, so extended Wilson loops and per-configuration spread are
where a bad lift should still be visible after post-processing. The coverage
retrain is independent evidence that the model has structure there -- it moved
extended-loop mean |z| from 1.14 to 0.34 at the top rung while barely touching
the plaquette.

So this stage runs every arm through the FULL validation observable set, not the
four-loop subset stage 17 used, and reports:

  * extended-loop agreement with the closed form (area >= 64),
  * per-configuration Wilson spread against an HMC reference,
  * P(Q) coverage and <Q^2>.

Two outcomes, both publishable and very different. If diffusion separates on
extended loops, the claim sharpens: local observables do not discriminate the
lift, extended ones do. If every arm ties, the honest paper is about the ladder
and the exact conditional sampler, with the learned lift reported as optional.
This script is written to make either answer legible rather than to find one.

Usage:
    python u2_2d/scripts/21_prolongator_observables.py --rung -1 --n-configs 256
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.lattice import topological_charge as u1_charge
from u2_2d.lgt.exact import det_topological_charge_distribution
from u2_2d.lgt.lattice import det_links
from u2_2d.utils import (configure_device, ensemble_path, load_config,
                         load_ensemble, resolve_device, save_json, set_seed)
from u2_2d.validate.observables import measure_ensemble
from u2_2d.validate.report import compare


def _load_sibling(name: str):
    """Import a sibling script whose module name starts with a digit."""
    path = Path(__file__).resolve().parent / name
    spec = importlib.util.spec_from_file_location(path.stem.lstrip("0123456789_"), path)
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def _extended_stats(summary: dict, min_area: int = 64) -> dict:
    """Mean/max |z| against the closed form over loops of area >= min_area."""
    zs, names = [], []
    for row in summary["rows"]:
        obs = row["observable"]
        if not obs.startswith("wilson_") or "z_vs_exact" not in row:
            continue
        try:
            a, b = obs.rsplit("_", 1)[1].split("x")
            area = int(a) * int(b)
        except (ValueError, IndexError):
            continue
        if area >= min_area:
            zs.append(row["z_vs_exact"])
            names.append(obs)
    if not zs:
        return {"n": 0}
    arr = np.asarray(zs, dtype=float)
    return {
        "n": int(arr.size),
        "mean_z": float(arr.mean()),
        "mean_abs_z": float(np.abs(arr).mean()),
        "max_abs_z": float(np.abs(arr).max()),
        "loops": names,
    }


def _spread_ratios(arm_links, reference, loops=("plaquette", "wilson_2x2",
                                                "wilson_4x4", "wilson_8x8")) -> dict:
    """Per-configuration sigma, arm / reference. Means agree; width is the signal."""
    gen = measure_ensemble(arm_links)
    ref = measure_ensemble(reference)
    out = {}
    for key in loops:
        if key in gen and key in ref:
            g = float(np.std(np.asarray(gen[key], dtype=float), ddof=1))
            r = float(np.std(np.asarray(ref[key], dtype=float), ddof=1))
            out[key] = {"generated": g, "reference": r,
                        "ratio": (g / r) if r > 0 else float("nan")}
    return out


def _pq_coverage(charges: np.ndarray, beta: float, size: int) -> dict:
    """Fraction of exact P(Q) the arm's occupied sectors account for."""
    q_values, probs = det_topological_charge_distribution(beta, size)
    exact = {int(q): float(p) for q, p in zip(q_values, probs)}
    q = np.asarray(charges, dtype=float).round().astype(int)
    occupied = set(int(x) for x in np.unique(q))
    covered = float(sum(exact.get(s, 0.0) for s in occupied))
    return {
        "sectors": len(occupied),
        "odd_sectors": int(sum(1 for s in occupied if s % 2)),
        "p_q_covered": covered,
        "q_squared": float((q.astype(float) ** 2).mean()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/prolongator_observables")
    parser.add_argument("--ladder-dir", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--n-configs", type=int, default=256)
    parser.add_argument("--rung", type=int, default=-1)
    parser.add_argument("--arms", nargs="+",
                        default=["diffusion", "tile", "halve", "flux", "smear"])
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 2121)

    prolong = _load_sibling("17_prolongator_baseline.py")

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]
    ladder_dir = Path(args.ladder_dir or ladder_cfg.get("out_dir", "out/u2_2d/ladder"))
    data_dir = Path(args.data_dir or config["data"].get("out_dir", "out/u2_2d/data"))

    if rung == 0:
        coarse_path = ensemble_path(data_dir, int(base["lattice_size"]),
                                    float(base["beta"]))
    else:
        coarse_path = ensemble_path(ladder_dir, sizes[rung - 1], schedule[rung - 1],
                                    tag="ladder")
    fine_path = ensemble_path(ladder_dir, size, beta, tag="ladder")
    for p in (coarse_path, fine_path):
        if not p.exists():
            print(f"missing {p} -- run stage 03 first")
            return 1

    coarse, _ = load_ensemble(coarse_path)
    generated, _ = load_ensemble(fine_path)
    n = min(args.n_configs, coarse.shape[0], generated.shape[0])
    coarse, generated = coarse[:n], generated[:n]

    # The HMC reference is what the spread comparison needs. Without it the
    # spread column is meaningless -- an ensemble cannot be under-dispersed
    # relative to nothing -- so say so rather than printing ratios against exact.
    ref_path = ensemble_path(data_dir, size, beta)
    reference = None
    if ref_path.exists():
        reference, _ = load_ensemble(ref_path)
        reference = reference[:n]
        print(f"reference: {ref_path.name} ({reference.shape[0]} configs)")
    else:
        print(f"no HMC reference at {ref_path.name} -- spread column omitted")

    print(f"rung {rung}: L={size} beta={beta:g}, {n} configs per arm")
    print(f"  coarse from {coarse_path.name}  ({coarse.shape[-3]}^2)")

    n_su2 = int(ladder_cfg.get("n_su2_sweeps", 30))
    n_retherm = int(ladder_cfg.get("n_retherm_sweeps", 10))
    psi_coarse = det_links(coarse)

    results = []
    for name in args.arms:
        t0 = time.time()
        if name == "diffusion":
            links = generated
        elif name in prolong.GEOMETRIC:
            links, _ = prolong.assemble(prolong.GEOMETRIC[name](psi_coarse), coarse,
                                        beta, n_su2, n_retherm, device)
        elif name == "smear":
            fine, _ = prolong.assemble(prolong.flux(psi_coarse), coarse, beta,
                                       n_su2, n_retherm, device)
            links, count, secs = prolong.tune_smear(fine, beta, device)
            print(f"  smear: {count} tuned sweeps ({secs:.0f}s)")
        else:
            print(f"  unknown arm {name}, skipping")
            continue

        summary = compare(links, reference, beta, size)
        ext = _extended_stats(summary)
        q = np.asarray(measure_ensemble(links)["topological_charge"], dtype=float)
        rec = {
            "arm": name,
            "n_configs": int(links.shape[0]),
            "extended": ext,
            "topology": _pq_coverage(q, beta, size),
            "seconds": time.time() - t0,
        }
        if reference is not None:
            rec["spread"] = _spread_ratios(links, reference)
        plaq = next(r for r in summary["rows"] if r["observable"] == "plaquette")
        rec["plaquette_z_vs_exact"] = plaq.get("z_vs_exact")
        results.append(rec)

        line = (f"  {name:<10} extended mean|z| {ext.get('mean_abs_z', float('nan')):5.2f}"
                f"  max {ext.get('max_abs_z', float('nan')):5.2f}"
                f"  plaq z {rec['plaquette_z_vs_exact']:+6.2f}"
                f"  <Q^2> {rec['topology']['q_squared']:.3f}"
                f"  P(Q) {rec['topology']['p_q_covered']:.3f}")
        if "spread" in rec:
            r8 = rec["spread"].get("wilson_8x8", {}).get("ratio", float("nan"))
            line += f"  sigma8x8 {r8:.3f}"
        print(line)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "lattice_size": size,
        "beta": beta,
        "rung": rung,
        "n_configs": n,
        "n_su2_sweeps": n_su2,
        "n_retherm_sweeps": n_retherm,
        "reference": ref_path.name if reference is not None else None,
        "arms": results,
    }
    save_json(out_dir / "prolongator_observables.json", payload)
    (out_dir / "report.md").write_text(_render(payload), encoding="utf-8")
    print(f"wrote {out_dir / 'prolongator_observables.json'} and report.md")
    return 0


def _render(p: dict) -> str:
    L, beta = p["lattice_size"], p["beta"]
    lines = [
        "# Do the geometric prolongators match the learned one on extended observables?",
        "",
        f"$L = {L}$, $\\beta = {beta:g}$, {p['n_configs']} configurations per arm, "
        f"identical post-processing ({p['n_su2_sweeps']} conditional SU(2) sweeps "
        f"+ {p['n_retherm_sweeps']} rethermalization sweeps).",
        "",
        "`17_prolongator_baseline.py` showed local observables cannot separate these "
        "arms, and that sector transport is imposed identically on all of them. "
        "Extended loops and per-configuration spread are the remaining places a bad "
        "lift could still be visible after the exact SU(2) sampler has run.",
        "",
        "| arm | extended mean $|z|$ | extended max $|z|$ | plaquette $z$ | "
        "$\\langle Q^2\\rangle$ | $P(Q)$ covered | $\\sigma$ ratio $8\\times8$ |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in p["arms"]:
        e, t = r["extended"], r["topology"]
        s = r.get("spread", {}).get("wilson_8x8", {}).get("ratio")
        bold = "**" if r["arm"] == "diffusion" else ""
        lines.append(
            f"| {bold}{r['arm']}{bold} | {e.get('mean_abs_z', float('nan')):.2f} | "
            f"{e.get('max_abs_z', float('nan')):.2f} | "
            f"{r['plaquette_z_vs_exact']:+.2f} | {t['q_squared']:.3f} | "
            f"{t['p_q_covered']:.3f} | "
            + ("--" if s is None else f"{s:.3f}") + " |")

    arms = {r["arm"]: r for r in p["arms"]}
    lines += ["", "## What to read off it", ""]
    if "diffusion" in arms:
        d = arms["diffusion"]["extended"].get("mean_abs_z")
        others = {k: v["extended"].get("mean_abs_z") for k, v in arms.items()
                  if k != "diffusion" and v["extended"].get("mean_abs_z") is not None}
        if d is not None and others:
            best = min(others, key=others.get)
            if others[best] > 1.3 * d:
                lines.append(
                    f"**The learned lift separates on extended loops.** Its mean "
                    f"$|z|$ over loops of area $\\ge 64$ is {d:.2f} against "
                    f"{others[best]:.2f} for the best geometric arm (`{best}`) -- "
                    f"a factor of {others[best] / d:.1f}. Local observables do not "
                    f"discriminate the lift; extended ones do, and that is the "
                    f"claim the paper should make.")
            elif d > 1.3 * others[best]:
                lines.append(
                    f"**The learned lift is WORSE on extended loops too.** Mean "
                    f"$|z|$ {d:.2f} against `{best}`'s {others[best]:.2f}. There is "
                    f"then no measured observable on which the model beats a "
                    f"geometric map, and the honest claim is about the ladder and "
                    f"the exact conditional sampler, not the lift.")
            else:
                lines.append(
                    f"**The arms tie on extended loops.** Mean $|z|$ {d:.2f} for "
                    f"diffusion against {others[best]:.2f} for the best geometric "
                    f"arm (`{best}`) -- within {abs(d - others[best]) / max(d, 1e-9) * 100:.0f}%. "
                    f"Combined with the local-observable result and the identical "
                    f"sector transport, no measured quantity separates the learned "
                    f"lift from a five-line geometric one at this rung. The "
                    f"defensible paper is then about topology transport up a "
                    f"matched ladder with an exact conditional sampler, with the "
                    f"diffusion lift reported as one option among several.")
    lines += [
        "",
        "Read the $P(Q)$ and $\\langle Q^2\\rangle$ columns as a control, not a result: "
        "`apply_coarse_charge` imposes the coarse charge on every arm, so these are "
        "expected to be identical and a difference would indicate a bug.",
        "",
        "Source: `u2_2d/scripts/21_prolongator_observables.py`.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
