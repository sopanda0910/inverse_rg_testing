"""Stage 17: the non-learned prolongators, and t_therm against them.

The gap this closes. Stage 08 measures the diffusion seed against cold, hot and
cold+winding starts. All three throw the coarse configuration away, while the
seed is handed it -- so any of the measured advantage could in principle be
bought by ANY map from coarse to fine, with no model in it at all. Until that is
tested the baselines are strawmen, and it is the first thing a referee says.

The ablation is exact here in a way it is not in u1_2d. One inverse-RG step
factorizes as p(psi, q) = p(psi) p(q | psi), and only the psi half is learned:
`naive_su2_inverse_block` seeds SU(2) and `conditional_su2_sweeps` is an EXACT
sampler for p(q | psi). So swapping `lift_determinant` for a non-learned map from
coarse psi to fine psi, with every other stage byte-identical, isolates the
learned contribution and nothing else. That is the cleanest form of this
experiment available in either study.

Q is a functional of psi alone, and psi is an honest compact U(1) field in the
[B, 2, L, L] layout, so the three geometric prolongators are `u1_2d`'s verbatim:

  tile    replicate the coarse psi 2x2. NOT blocking-consistent; its determinant
          plaquettes are distributed like the coarse theory.
  halve   the exact deterministic inverse of the determinant blocking rule.
          Blocking-consistent, so it carries the coarse sector exactly, but cold
          in every fine plaquette blocking does not constrain.
  flux    blocking-consistent AND flux-spreading: the coarse cell's determinant
          plaquette angle shared evenly over its four fine plaquettes instead of
          piled onto one. The strongest prolongator with nothing learned in it.
  smear   `flux`, then N extra heatbath + overrelaxation sweeps with N TUNED PER
          COUPLING to match the exact plaquette. This is the U(2) analogue of the
          Endres-style prolong-then-smooth arm, and it is the honest competitor:
          a fixed count would hand it an over- or under-ordered configuration and
          beat a strawman. Its tuning cost is measured and reported, never hidden.

Every arm -- including the diffusion one -- then gets IDENTICAL post-processing:
coarse-charge enforcement on psi, `n_su2_sweeps` conditional SU(2) sweeps, and
`n_retherm_sweeps` rethermalization sweeps. Whatever differs afterwards is the
lift and only the lift.

t_therm is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion, unchanged, so
the numbers drop straight into the same table: the first trajectory at which the
across-chain |z| against the EXACT value is <= 2 for five consecutive
trajectories. A non-converging arm is reported against its own budget, never as
"never".

    python u2_2d/scripts/17_prolongator_baseline.py --n-traj 400
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.lgt.lattice import plaquette_angles as u1_plaquette_angles
from u1_2d.lgt.lattice import topological_charge as u1_charge
from u1_2d.lgt.lattice import wrap as u1_wrap
from u1_2d.pipeline.ladder import apply_coarse_charge
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import det_links, half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.lgt.local_updates import conditional_su2_sweeps, retherm_sweeps
from u2_2d.model.su2_lift import assemble_links, naive_su2_inverse_block
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
)

LOOPS = {"plaquette": (1, 1), "wilson_2x2": (2, 2), "wilson_4x4": (4, 4),
         "wilson_8x8": (8, 8)}


# --------------------------------------------------------------------------
# the three geometric maps, on the determinant field
# --------------------------------------------------------------------------

def tile(psi: torch.Tensor) -> torch.Tensor:
    """[B,2,Lc,Lc] -> [B,2,2Lc,2Lc] by periodic 2x2 replication."""
    return psi.repeat(1, 1, 2, 2).clone()


def halve(psi: torch.Tensor) -> torch.Tensor:
    """Exact inverse of the determinant blocking rule, cold where unconstrained.

    The coarse determinant link is the SUM of the two fine ones it was built
    from (det is a homomorphism, so the abelian rule survives the non-abelian
    group). Splitting it evenly reproduces that sum exactly.
    """
    b, _, lc, _ = psi.shape
    fine = torch.zeros(b, 2, 2 * lc, 2 * lc, dtype=psi.dtype, device=psi.device)
    half = u1_wrap(psi) / 2.0
    fine[:, 0, 0::2, 0::2] = half[:, 0]
    fine[:, 0, 1::2, 0::2] = half[:, 0]
    fine[:, 1, 0::2, 0::2] = half[:, 1]
    fine[:, 1, 0::2, 1::2] = half[:, 1]
    return u1_wrap(fine)


def flux(psi: torch.Tensor) -> torch.Tensor:
    """Blocking-consistent, with the cell's coarse flux spread over its four
    fine plaquettes instead of concentrated on one.

    Adding a constant to the links blocking never reads moves flux between the
    plaquettes of a cell without touching the coarse configuration, so one shift
    per cell equalizes them. Identical to `u1_2d/scripts/37_tiling_baseline.py`,
    which is the point: the determinant sector is the same theory.
    """
    fine = halve(psi)
    with torch.no_grad():
        cell = u1_plaquette_angles(fine)
        want = (cell[:, 0::2, 0::2] + cell[:, 1::2, 0::2]
                + cell[:, 0::2, 1::2] + cell[:, 1::2, 1::2]) / 4.0
        fine[:, 0, 0::2, 1::2] += cell[:, 0::2, 0::2] - want
        fine[:, 0, 1::2, 1::2] += cell[:, 1::2, 0::2] - want
        cell = u1_plaquette_angles(fine)
        fine[:, 1, 1::2, 1::2] += want - cell[:, 0::2, 1::2]
    return u1_wrap(fine)


GEOMETRIC = {"tile": tile, "halve": halve, "flux": flux}


# --------------------------------------------------------------------------
# assembly: identical to the ladder's own, with the lift swapped out
# --------------------------------------------------------------------------

def assemble(psi_fine: torch.Tensor, coarse: torch.Tensor, beta: float,
             n_su2_sweeps: int, n_retherm_sweeps: int, device: str,
             enforce_charge: bool = True) -> tuple[torch.Tensor, float]:
    """psi -> full U(2) configuration, through the ladder's own post-processing.

    Returns the configuration and its PRE-rethermalization mean plaquette. That
    second number is the one NARRATIVE section 22 insists on: the rethermalization
    sweeps are a local-update repair that will look healthy past the point where
    the lift stopped working, so a post-retherm column alone cannot separate a
    good model from a good repair.
    """
    if enforce_charge:
        psi_fine = apply_coarse_charge(psi_fine, u1_charge(det_links(coarse)))
    su2_seed = naive_su2_inverse_block(coarse[..., 1:])
    fine = assemble_links(psi_fine, su2_seed).to(device)
    action = WilsonU2Action(beta)
    with torch.no_grad():
        fine = conditional_su2_sweeps(fine, action, n_su2_sweeps)
        pre = float(half_retr(plaquette(fine)).mean())
        fine = retherm_sweeps(fine, action, n_retherm_sweeps,
                              topological_updates=False)
    return fine.cpu(), pre


def tune_smear(fine: torch.Tensor, beta: float, device: str, max_sweeps: int = 400,
               check_every: int = 5) -> tuple[torch.Tensor, int, float]:
    """Extra heatbath + overrelaxation sweeps until the plaquette crosses exact.

    Stopping on the exact plaquette rather than a fixed count is what makes this
    a competitor instead of a strawman -- and the count it needs, together with
    the seconds it cost, is returned so the arm is charged for its own tuning.
    """
    target = plaquette_exact(beta, fine.shape[-3])
    action = WilsonU2Action(beta)
    links = fine.to(device)
    t0 = time.time()
    best, best_n, best_err = links.clone(), 0, abs(
        float(half_retr(plaquette(links)).mean()) - target)
    with torch.no_grad():
        for n in range(1, max_sweeps + 1):
            links = retherm_sweeps(links, action, 1, topological_updates=False)
            if n % check_every:
                continue
            err = abs(float(half_retr(plaquette(links)).mean()) - target)
            if err < best_err:
                best, best_n, best_err = links.clone(), n, err
            elif err > 3.0 * best_err and best_n:
                break
    return best.cpu(), best_n, time.time() - t0


# --------------------------------------------------------------------------
# t_therm, u1_2d's criterion verbatim
# --------------------------------------------------------------------------

def thermalization_time(series: np.ndarray, target: float,
                        z_threshold: float = 2.0, n_consecutive: int = 5) -> float:
    """First t with |z(across-chain mean)| <= threshold for n_consecutive steps."""
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    z = np.abs((mean - target) / np.maximum(sem, 1e-12))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t:t + n_consecutive].all():
            return float(t)
    return float("inf")


def measure(links: torch.Tensor, size: int) -> dict:
    with torch.no_grad():
        out = {}
        for name, (a, b) in LOOPS.items():
            if a < size:
                loop = plaquette(links) if name == "plaquette" else wilson_loop(links, a, b)
                out[name] = half_retr(loop).mean(dim=(-2, -1)).cpu().numpy().copy()
        out["charge"] = topological_charge(links).cpu().numpy().copy()
        return out


def run_arm(name: str, sampler: BatchedHMCU2, start: torch.Tensor, n_traj: int,
            size: int) -> dict:
    """One trajectory-resolved chain per configuration, recorded every step.

    Every trajectory is recorded rather than every fifth: t_therm for a good seed
    is O(1), and a stride of five cannot resolve the difference between 0 and 4.
    """
    links = start.clone().to(sampler.device)
    series = {k: [] for k in LOOPS if k == "plaquette" or LOOPS[k][0] < size}
    charges, t0 = [], time.time()
    with torch.no_grad():
        for step in range(n_traj + 1):
            rec = measure(links, size)
            for k in series:
                series[k].append(rec[k])
            charges.append(rec["charge"])
            if step < n_traj:
                links, _ = sampler.metropolis_step(links)
    return {
        "name": name,
        "series": {k: np.stack(v) for k, v in series.items()},
        "charge": np.stack(charges),
        "seconds": time.time() - t0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/prolongator")
    parser.add_argument("--n-traj", type=int, default=400)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--rung", type=int, default=-1,
                        help="ladder rung to test (-1 = the top one)")
    parser.add_argument("--arms", nargs="+",
                        default=["diffusion", "tile", "halve", "flux", "smear",
                                 "cold", "hot"])
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 1717)

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]
    ladder_dir = Path(ladder_cfg.get("out_dir", "out/u2_2d/ladder"))

    # the coarse ensemble this rung was lifted FROM -- the base for rung 0, the
    # previous rung's own output above it, exactly as `generate_ladder` chains them
    if rung == 0:
        coarse_path = ensemble_path(config["data"]["out_dir"],
                                    int(base["lattice_size"]), float(base["beta"]))
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
    n_chains = min(args.n_chains, coarse.shape[0], generated.shape[0])
    coarse, generated = coarse[:n_chains], generated[:n_chains]
    print(f"rung {rung}: L={size} beta={beta:g}, {n_chains} chains, "
          f"{args.n_traj} trajectories per arm")
    print(f"  coarse from {coarse_path.name}  ({coarse.shape[-3]}^2)")

    n_su2 = int(ladder_cfg.get("n_su2_sweeps", 30))
    n_retherm = int(ladder_cfg.get("n_retherm_sweeps", 10))
    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)
    sampler = BatchedHMCU2(size, action, n_chains=n_chains, n_steps=n_steps,
                           step_size=step_size, device=device,
                           topological_updates=False)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    psi_coarse = det_links(coarse)
    starts, build_cost, smear_count, pre_plaq = {}, {}, {}, {}
    raw_pre = _load_raw_pre_retherm(ladder_dir, size, beta)
    for name in args.arms:
        t0 = time.time()
        if name == "diffusion":
            starts[name] = generated
            pre_plaq[name] = raw_pre
        elif name in GEOMETRIC:
            starts[name], pre_plaq[name] = assemble(
                GEOMETRIC[name](psi_coarse), coarse, beta, n_su2, n_retherm, device)
        elif name == "smear":
            fine, pre = assemble(flux(psi_coarse), coarse, beta, n_su2, n_retherm,
                                 device)
            smeared, count, secs = tune_smear(fine, beta, device)
            starts[name] = smeared
            smear_count[name] = count
            pre_plaq[name] = pre
            print(f"  smear: {count} tuned sweeps ({secs:.0f}s)")
        elif name == "cold":
            starts[name] = sampler.initialize(hot=False).cpu()
        elif name == "hot":
            starts[name] = sampler.initialize(hot=True).cpu()
        else:
            print(f"  unknown arm {name}, skipping")
            continue
        build_cost[name] = time.time() - t0

    exact = {n: (plaquette_exact(beta, size) if n == "plaquette"
                 else wilson_loop_exact(beta, a * b))
             for n, (a, b) in LOOPS.items() if a < size}

    rows = []
    for name, start in starts.items():
        arm = run_arm(name, sampler, start, args.n_traj, size)
        t_therm = {k: thermalization_time(v, exact[k]) for k, v in arm["series"].items()}
        initial = {k: float(v[0].mean()) for k, v in arm["series"].items()}
        final = {k: float(v[-1].mean()) for k, v in arm["series"].items()}
        row = {
            "arm": name,
            "lattice_size": size,
            "beta": beta,
            "n_chains": n_chains,
            "n_traj": args.n_traj,
            "build_seconds": build_cost.get(name),
            "tuned_sweeps": smear_count.get(name),
            "hmc_seconds": arm["seconds"],
            "t_therm": {k: (v if math.isfinite(v) else None) for k, v in t_therm.items()},
            "t_therm_budget": args.n_traj,
            "t_therm_slowest": (max(t_therm.values()) if all(
                math.isfinite(v) for v in t_therm.values()) else None),
            "rel_err_initial": {k: (initial[k] - exact[k]) / abs(exact[k]) for k in exact},
            "rel_err_final": {k: (final[k] - exact[k]) / abs(exact[k]) for k in exact},
            "plaquette_pre_retherm": pre_plaq.get(name),
            "rel_err_pre_retherm": (
                None if pre_plaq.get(name) is None
                else (pre_plaq[name] - exact["plaquette"]) / abs(exact["plaquette"])),
            "exact": exact,
            "q_squared_initial": float((arm["charge"][0] ** 2).mean()),
            "q_squared_final": float((arm["charge"][-1] ** 2).mean()),
        }
        rows.append(row)
        slow = row["t_therm_slowest"]
        print(f"  {name:10s} t_therm(plaq)="
              f"{_fmt(t_therm['plaquette'], args.n_traj):>7s}"
              f"  slowest={_fmt(slow if slow is not None else float('inf'), args.n_traj):>7s}"
              f"  |dP/P| t=0 {abs(row['rel_err_initial']['plaquette']):.2e}"
              f"  build {build_cost.get(name, 0):.0f}s", flush=True)
        save_json(out_dir / "prolongator.json", rows)

    _write_report(out_dir / "report.md", rows, n_su2, n_retherm)
    print(f"\nwrote {out_dir / 'prolongator.json'} and report.md")
    return 0


def _fmt(v: float, budget: int) -> str:
    return f"> {budget}" if v is None or not math.isfinite(v) else f"{v:.0f}"


def _load_raw_pre_retherm(ladder_dir: Path, size: int, beta: float):
    """The diffusion arm's own pre-retherm plaquette, from stage 03's summary.

    Recomputing it here would mean re-running the lift; stage 03 already recorded
    it, and reading it back keeps the column comparable across arms.
    """
    path = Path(ladder_dir) / "summary.json"
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rows = rows if isinstance(rows, list) else rows.get("rungs", [])
    for r in rows:
        if int(r.get("lattice_size", -1)) == size and abs(
                float(r.get("beta", 0.0)) - beta) < 1e-6:
            return r.get("plaquette_pre_retherm")
    return None


ORDER = ["tile", "halve", "flux", "smear", "hot", "cold", "diffusion"]


def _write_report(path: Path, rows: list, n_su2: int, n_retherm: int) -> None:
    rows = sorted(rows, key=lambda r: ORDER.index(r["arm"]) if r["arm"] in ORDER else 99)
    beta, size = rows[0]["beta"], rows[0]["lattice_size"]
    budget = rows[0]["n_traj"]
    obs = [k for k in LOOPS if k in rows[0]["t_therm"]]

    lines = [
        "# Non-learned prolongators, and t_therm against them",
        "",
        f"$L = {size}$, $\\beta = {beta:g}$, {rows[0]['n_chains']} chains, "
        f"{budget} trajectories per arm.",
        "",
        "Every arm receives IDENTICAL post-processing -- coarse-charge enforcement "
        f"on $\\psi$, {n_su2} conditional SU(2) sweeps, {n_retherm} rethermalization "
        "sweeps -- so what differs is the lift and only the lift. The SU(2) sampler "
        "is exact at frozen $\\psi$, which is what makes this ablation clean: the "
        "only learned object in the pipeline is the map from coarse $\\psi$ to fine "
        "$\\psi$, and it is the only thing being swapped.",
        "",
        "$t_{\\rm therm}$ is `u1_2d/scripts/05_hmc_thermalization.py`'s criterion: "
        "the first trajectory at which the across-chain $|z|$ against the EXACT "
        "value is $\\le 2$ for five consecutive trajectories. An arm that never "
        f"gets there is written `> {budget}`, against its own budget, never "
        "\"never\".",
        "",
        "| arm | " + " | ".join(f"$t$ {o.replace('wilson_', 'W')}" for o in obs)
        + " | slowest | rel err **pre**-retherm | $|\\Delta P/P|$ at $t=0$ | build s |",
        "|---|" + "---|" * (len(obs) + 4),
    ]
    for r in rows:
        cells = [_fmt(r["t_therm"][o], budget) for o in obs]
        slow = r["t_therm_slowest"]
        name = r["arm"] + (f" ({r['tuned_sweeps']} sweeps)" if r.get("tuned_sweeps") else "")
        bold = "**" if r["arm"] == "diffusion" else ""
        pre = r.get("rel_err_pre_retherm")
        lines.append(
            f"| {bold}{name}{bold} | " + " | ".join(f"{bold}{c}{bold}" for c in cells)
            + f" | {bold}{_fmt(slow if slow is not None else float('inf'), budget)}{bold}"
            + f" | {'--' if pre is None else f'{pre:+.2e}'}"
            + f" | {abs(r['rel_err_initial']['plaquette']):.2e}"
            + f" | {r['build_seconds']:.0f} |")

    geo = [r for r in rows if r["arm"] in GEOMETRIC]
    cold = next((r for r in rows if r["arm"] == "cold"), None)
    diff = next((r for r in rows if r["arm"] == "diffusion"), None)
    lines += ["", "## What to read off it", ""]
    if diff is not None and cold is not None:
        lines.append(
            f"The diffusion arm starts at $|\\Delta P/P| = "
            f"{abs(diff['rel_err_initial']['plaquette']):.2e}$ against the cold "
            f"start's ${abs(cold['rel_err_initial']['plaquette']):.2e}$.")
    if geo and cold is not None:
        worse = [r["arm"] for r in geo
                 if (r["t_therm_slowest"] is None
                     or (cold["t_therm_slowest"] is not None
                         and r["t_therm_slowest"] > cold["t_therm_slowest"]))]
        if worse:
            lines.append(
                f"**{', '.join(worse)} are no better than a fresh cold start.** "
                "Prolonging by an obvious deterministic rule satisfies the coarse "
                "constraint while being wrong at short distances, and the chain "
                "then has to undo it -- so the advantage is specific to learning, "
                "not to having been handed the coarse configuration.")
        else:
            lines.append(
                "The geometric prolongators beat a fresh cold start here, so part "
                "of the seed's advantage is available without a model. Quote the "
                "margin over `flux`, not over `cold`.")
    lines += [
        "",
        "`smear` is the arm that matters: `flux` plus heatbath + overrelaxation "
        "sweeps, the count chosen per coupling to match the exact plaquette rather "
        "than fixed. Its build cost is charged in the last column.",
        "",
        "Source: `u2_2d/scripts/17_prolongator_baseline.py`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
