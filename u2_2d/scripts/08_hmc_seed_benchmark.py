"""Stage 08: is a diffusion-generated configuration a good HMC starting point?

This is the study's central practical claim, and it has two halves that have to be
measured separately because they fail for different reasons.

LOCAL OBSERVABLES. A generated configuration is useful as a seed if HMC started
from it is ALREADY at equilibrium -- no burn-in to pay. The yardstick is not
"does it eventually thermalize" (everything does) but the interval a plain chain
needs between independent configurations, 2 tau_int. If a seed costs less than
that, generating is cheaper than continuing a chain. Arms B and C (cold and hot
starts) are the controls: they must visibly relax, or the test has no dynamic
range and proves nothing.

TOPOLOGY. This is where the seed cannot be beaten rather than merely matched. At
these couplings a plain chain never changes sector at all, so its P(Q) is whatever
it started with, forever. Cold-started chains sit in Q = 0; the diffusion seed
arrives with the sector distribution transported from a base coupling where the
dynamics genuinely samples it. The measurement is therefore not "how fast does Q
decorrelate" -- it never does -- but how much of the exact P(Q) each arm covers.

THE SIX ARMS -- the full {plain, instanton} x {diffusion, cold, hot} grid.
    A  diffusion seed + plain HMC           -- the proposal
    B  cold start + plain HMC               -- control, and the honest default
    C  hot start + plain HMC                -- control from the other side
    D  cold start + HMC with winding update -- the strongest CLASSICAL baseline,
       and the one that matters: U(2)'s winding move is free at even charge and
       obstructed at odd, so arm D is expected to reach Q even and nothing else.
    E  diffusion seed + HMC with winding update  -- the fair partner to D
    F  hot start + HMC with winding update       -- the fair partner to C

READ THE GRID BY ROW, NEVER DIAGONALLY. A vs D changes the seed and the sampler
at once; the comparison that supports the claim is A vs B vs C within plain HMC,
and E vs D vs F within instanton HMC. E is also the sharper diagnostic: if the
generated P(Q) is wrong, winding moves drift <Q^2> over the run, whereas arm A
cannot distinguish "correct" from "frozen".

Arm D is the reason this script exists in the form it does. In U(1) the instanton
update is a complete solution and the diffusion ladder has to beat a genuinely
ergodic baseline. In U(2) the SAME update is free only for even charge, because
U(2) = (U(1) x SU(2)) / Z_2 makes an odd-charge shift drag SU(2) across a -1
monodromy at cost O(beta L). Measuring arm D's sector coverage is what turns that
argument into a number.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.exact import (
    det_topological_charge_distribution,
    det_topological_susceptibility,
    plaquette_exact,
    wilson_loop_exact,
)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
)

LOOPS = {"wilson_1x1": (1, 1), "wilson_2x2": (2, 2), "wilson_4x4": (4, 4),
         "wilson_8x8": (8, 8)}


def integrated_autocorrelation(series: np.ndarray, c: float = 5.0) -> float:
    """tau_int of a [n_steps, n_chains] series, averaged over non-constant chains."""
    n = series.shape[0]
    taus = []
    for chain in series.T:
        var = chain.var()
        if var <= 0:
            continue
        x = chain - chain.mean()
        acf = np.correlate(x, x, mode="full")[n - 1:] / (var * n)
        tau = 0.5
        for w in range(1, n):
            tau += acf[w]
            if w >= c * tau:
                break
        taus.append(max(tau, 0.5))
    return float(np.mean(taus)) if taus else float("nan")


def measure(links: torch.Tensor) -> dict:
    """Gauge-invariant observables of one batch, as plain floats/arrays.

    Every loop observable also gets a `<name>_chain` per-chain mean (shape
    [n_chains]), alongside the scalar batch mean. The scalar is what every
    existing consumer of this dict reads; `<name>_chain` exists so a mean can
    be given a chain-aware SEM/z-score downstream (`54_seed_benchmark_topology_stats.py`)
    instead of the batch mean's bare point estimate.
    """
    with torch.no_grad():
        p_chain = half_retr(plaquette(links)).mean(dim=(-2, -1))
        out = {"plaquette": float(p_chain.mean()),
               "plaquette_chain": p_chain.cpu().numpy().copy()}
        for name, (a, b) in LOOPS.items():
            if a < links.shape[-2]:
                w_chain = half_retr(wilson_loop(links, a, b)).mean(dim=(-2, -1))
                out[name] = float(w_chain.mean())
                out[f"{name}_chain"] = w_chain.cpu().numpy().copy()
        out["charge"] = topological_charge(links).cpu().numpy().copy()
        return out


def _arrays_to_lists(d: dict) -> None:
    """In-place JSON-prep: every ndarray value (charge, and now every `_chain`
    array `measure` adds) becomes a plain list."""
    for k, v in list(d.items()):
        if isinstance(v, np.ndarray):
            d[k] = v.tolist()


def _lists_to_arrays(d: dict) -> None:
    """Inverse of `_arrays_to_lists`, applied after a cache load or a fresh run."""
    for k, v in list(d.items()):
        if k == "charge" or k.endswith("_chain"):
            d[k] = np.asarray(v)


def run_arm(name: str, sampler: BatchedHMCU2, start: torch.Tensor,
            n_traj: int, record_every: int) -> dict:
    """Run one arm, recording observables along the trajectory history."""
    links = start.clone().to(sampler.device)
    history, t0 = [], time.time()
    with torch.no_grad():
        for step in range(n_traj + 1):
            if step % record_every == 0:
                rec = measure(links)
                rec["trajectory"] = step
                history.append(rec)
            if step < n_traj:
                links, _ = sampler.metropolis_step(links)
    elapsed = time.time() - t0
    print(f"    {name}: {n_traj} trajectories in {elapsed:.0f}s", flush=True)
    return {"name": name, "history": history, "seconds": elapsed,
            "final": measure(links)}


def sector_coverage(charge: np.ndarray, beta: float, size: int) -> dict:
    """How much of the exact P(Q) an arm's charges actually cover.

    `covered` is the total exact probability of the sectors the arm visits at
    all. It is the right summary for a frozen theory: an arm confined to Q = 0
    covers ~0.5 however long it runs, and no amount of sampling improves it.
    """
    q_values, probs = det_topological_charge_distribution(beta, size)
    visited = set(int(q) for q in np.unique(charge))
    covered = float(sum(p for q, p in zip(q_values, probs) if int(q) in visited))
    exact_q2 = det_topological_susceptibility(beta, size) * size * size
    return {
        "q_squared": float((charge ** 2).mean()),
        "q_squared_exact": float(exact_q2),
        "sectors_visited": sorted(visited),
        "n_sectors_visited": len(visited),
        "exact_probability_covered": covered,
        "odd_sectors_visited": sorted(q for q in visited if q % 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/seed_benchmark")
    parser.add_argument("--n-traj", type=int, default=400)
    parser.add_argument("--record-every", type=int, default=5)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--rung", type=int, default=-1,
                        help="which ladder rung to benchmark (-1 = the top one)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)) + 4241)

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    schedule = [float(b) for b in ladder_cfg["beta_schedule"]]
    sizes = [int(base["lattice_size"]) * 2 ** (i + 1) for i in range(len(schedule))]
    rung = args.rung if args.rung >= 0 else len(schedule) - 1
    beta, size = schedule[rung], sizes[rung]

    ladder_dir = Path(ladder_cfg.get("out_dir", "out/u2_2d/ladder"))
    path = ensemble_path(ladder_dir, size, beta, tag="ladder")
    if not path.exists():
        print(f"missing ladder ensemble {path} -- run stage 03 first")
        return 1
    generated, _ = load_ensemble(path)
    n_chains = min(args.n_chains, generated.shape[0])
    generated = generated[:n_chains]
    print(f"benchmark at L={size} beta={beta:g}, {n_chains} chains, "
          f"{args.n_traj} trajectories per arm")

    action = WilsonU2Action(beta)
    step_size, n_steps = adapted_hmc_params(beta)

    def make(topological: bool) -> BatchedHMCU2:
        return BatchedHMCU2(size, action, n_chains=n_chains, n_steps=n_steps,
                            step_size=step_size, device=device,
                            topological_updates=topological)

    plain, winding = make(False), make(True)
    # charge_step=1 now routes to the marginal odd move (2026-08-20), which
    # is accepted 0.60 at this coupling where the joint route was 0.000.
    odd = BatchedHMCU2(size, action, n_chains=n_chains, n_steps=n_steps,
                       step_size=step_size, device=device,
                       topological_updates=True, winding_charge_step=1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # PER-ARM CHECKPOINTING. An arm is several minutes at the top rung and the
    # whole set was previously written only at the end, so a kill during the third
    # arm discarded the two that had finished -- which is exactly what happened on
    # 2026-08-19, twice, when another job on the machine exhausted system memory.
    # Completed arms are cached on disk and reused, so a rerun resumes rather than
    # restarts. Delete the cache directory to force a clean run.
    # THE FULL 2x3 GRID, {plain, instanton} x {diffusion, cold, hot}.
    #
    # Comparing A (diffusion seed, plain HMC) against D (cold start, instanton
    # HMC) varies the seed AND the sampler at once, so it isolates neither -- and
    # it lets the classical arm repair a wrong sector by winding moves while
    # denying the diffusion arm the same. Report the two samplers separately;
    # within each, only the starting configuration differs.
    #
    # A-D keep their names so the per-arm cache is reused and every previously
    # published number is unchanged: completing the grid costs two arms, not six.
    #
    # Note what the instanton arms can and cannot do here. `winding_update`
    # defaults to charge_step=2 and odd-charge moves are dead above beta ~ 14-20
    # (Part II), so at the top rung these arms move Q by +-2 and never by +-1.
    # They can correct an even-sector error and cannot touch the odd/even
    # balance, which is why the reachability claim is unaffected by this change.
    plan = [
        ("A_diffusion_seed", plain, lambda: generated),
        ("B_cold_start", plain, lambda: plain.initialize(hot=False)),
        ("C_hot_start", plain, lambda: plain.initialize(hot=True)),
        ("D_cold_plus_winding", winding, lambda: winding.initialize(hot=False)),
        ("E_diffusion_plus_winding", winding, lambda: generated),
        ("F_hot_plus_winding", winding, lambda: winding.initialize(hot=True)),
        ("G_cold_plus_odd_winding", odd, lambda: odd.initialize(hot=False)),
        ("H_diffusion_plus_odd_winding", odd, lambda: generated),
    ]
    arms = []
    for name, sampler, start_fn in plan:
        cache = out_dir / f"arm_{name}.json"
        if cache.exists():
            arms.append(json.loads(cache.read_text(encoding="utf-8")))
            print(f"    {name}: reused from {cache.name}")
            continue
        arm = run_arm(name, sampler, start_fn(), args.n_traj, args.record_every)
        _arrays_to_lists(arm["final"])
        for h in arm["history"]:
            _arrays_to_lists(h)
        cache.write_text(json.dumps(arm), encoding="utf-8")
        arms.append(arm)
    for arm in arms:
        _lists_to_arrays(arm["final"])
        for h in arm["history"]:
            _lists_to_arrays(h)

    exact_plaq = plaquette_exact(beta, size)
    # wilson_loop_exact takes the loop AREA -- in 2D the enclosed plaquettes are
    # independent, so only r * t enters, not the shape.
    exact_loops = {n: wilson_loop_exact(beta, a * b) for n, (a, b) in LOOPS.items()
                   if a < size}

    # tau_int comes from the arm that is actually in equilibrium and unaided:
    # the diffusion seed. A relaxing chain's autocorrelation is contaminated by
    # its own drift, which is precisely what arms B and C are doing.
    tau_plaq = integrated_autocorrelation(
        np.array([h["plaquette"] for h in arms[0]["history"]])[:, None]
    )

    records = []
    for arm in arms:
        charge = np.stack([h["charge"] for h in arm["history"]])
        rec = {
            "arm": arm["name"],
            "seconds": arm["seconds"],
            "seconds_per_trajectory": arm["seconds"] / max(args.n_traj, 1),
            "plaquette_initial": arm["history"][0]["plaquette"],
            "plaquette_final": arm["final"]["plaquette"],
            "plaquette_exact": exact_plaq,
            "plaquette_initial_rel": arm["history"][0]["plaquette"] / exact_plaq - 1.0,
            "plaquette_final_rel": arm["final"]["plaquette"] / exact_plaq - 1.0,
            "loops_final": {n: arm["final"][n] for n in exact_loops if n in arm["final"]},
            "loops_exact": exact_loops,
            "topology": sector_coverage(charge, beta, size),
            "topology_initial": sector_coverage(charge[:1], beta, size),
            "history": [
                {"trajectory": h["trajectory"], "plaquette": h["plaquette"],
                 "q_squared": float((h["charge"] ** 2).mean()),
                 "n_sectors": int(len(np.unique(h["charge"])))}
                for h in arm["history"]
            ],
        }
        records.append(rec)

    summary = {"beta": beta, "lattice_size": size, "n_chains": n_chains,
               "n_trajectories": args.n_traj, "plaquette_exact": exact_plaq,
               "tau_int_plaquette_seeded": tau_plaq,
               "independent_interval_trajectories": 2.0 * tau_plaq,
               "arms": records}
    save_json(out_dir / "seed_benchmark.json", summary)

    print(f"\nL={size} beta={beta:g}   exact plaquette {exact_plaq:.6f}   "
          f"2 tau_int = {2 * tau_plaq:.1f} trajectories")
    print(f"{'arm':22s} {'plaq t=0':>12s} {'plaq final':>12s} {'<Q^2>':>8s} "
          f"{'exact':>8s} {'sectors':>8s} {'P(Q) covered':>13s} {'odd':>5s}")
    for r in records:
        t = r["topology"]
        print(f"{r['arm']:22s} {r['plaquette_initial_rel']:+12.2e} "
              f"{r['plaquette_final_rel']:+12.2e} {t['q_squared']:8.3f} "
              f"{t['q_squared_exact']:8.3f} {t['n_sectors_visited']:8d} "
              f"{t['exact_probability_covered']:13.3f} "
              f"{len(t['odd_sectors_visited']):5d}")
    print(f"\nwrote {out_dir / 'seed_benchmark.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
