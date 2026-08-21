"""Beta scan of thermalization time -- the u2 port of u1's lead-figure scan.

This is `u1_2d/scripts/05_hmc_thermalization.py --generalization` followed by
`35_crossover_window.py`, ported rather than reinvented. What that pair does, and
why each piece is load-bearing:

  * `t_therm` is measured on LOCAL observables (plaquette, W2x2, W4x4) and is the
    SLOWEST of them, using u1's criterion: the first trajectory at which the
    across-chain |z| against the EXACT value stays <= 2 for five consecutive
    records. Topology is deliberately NOT in that list -- it is measured
    separately, because a chain can be perfectly thermalized locally while never
    tunnelling.

  * `interval` = 2 tau_int of the equilibrated plain chain: the number of
    trajectories a working HMC chain needs between two INDEPENDENT
    configurations. This is the yardstick, and the claim only means something
    against it. A seed that thermalizes in fewer trajectories than the chain
    needs to decorrelate is cheaper per independent configuration; a seed that
    thermalizes in more is not, however impressive the ratio against a cold
    start looks.

  * ALL ARMS RUN PLAIN HMC -- no topological updates. Adding a winding move to
    the baseline is a different experiment (that is `26_freezing_arms.py`), and
    mixing them makes the ratio uninterpretable.

  * The three REGIMES matter more than the ratio. u1 found, and u2 inherits,
    that a speedup only means something while the baseline still finishes:
      HMC healthy  fresh chains thermalize AND Q tunnels -- a ratio is honest
      Q frozen     chains thermalize locally, Q never tunnels -- the advantage
                   is partly "HMC cannot do topology", a different claim
      HMC dead     fresh chains never thermalize inside the budget -- the ratio
                   is a bound, not a measurement, and is reported as such

ONE PHYSICS CAVEAT THAT THE FIGURE MUST CARRY. At FIXED L, raising beta shrinks
the exact <Q^2> (approximately V / 4 pi^2 beta): at L = 32 it falls 1.00 at
beta = 105.7 to 0.04 at beta = 800. So the far right of this scan is not "hard
topology" -- it is a theory with almost no topology, where a frozen chain
reproduces P(Q) almost correctly by accident. Holding <Q^2> fixed while raising
beta is the LADDER direction (beta_f = 4 beta_c with L_f = 2 L_c), which is why
the top-rung L = 64 point is carried alongside. `q_squared_exact` is recorded per
coupling so this is visible rather than implied.

    python u2_2d/scripts/28_crossover_scan.py --device cuda
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.validate.stats import integrated_autocorrelation_time
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import topology_matched_fine_beta
from u2_2d.lgt.exact import (
    det_topological_charge_distribution,
    matched_u1_beta,
    plaquette_exact,
    wilson_loop_exact,
)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params
from u2_2d.lgt.lattice import half_retr, plaquette, topological_charge, wilson_loop
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_fine_from_coarse
from u2_2d.utils import (configure_device, load_config, load_ensemble, resolve_device,
                         save_ensemble, save_json, set_seed)

LOCAL = ("plaquette", "wilson_2x2", "wilson_4x4")


def thermalization_time(series: np.ndarray, target: float,
                        z_threshold: float = 2.0, n_consecutive: int = 5) -> float:
    """u1's criterion, verbatim (see 17_prolongator_baseline.thermalization_time)."""
    mean = series.mean(axis=1)
    sem = series.std(axis=1, ddof=1) / math.sqrt(series.shape[1])
    z = np.abs((mean - target) / np.maximum(sem, 1e-12))
    ok = z <= z_threshold
    run_end = min(len(ok), len(ok) - n_consecutive + 1)
    for t in range(max(run_end, 1)):
        if ok[t:t + n_consecutive].all():
            return float(t)
    return float("inf")


def observe(links: torch.Tensor) -> dict:
    with torch.no_grad():
        return {
            # half_retr collapses the group axis, so every observable is
            # [batch, L, L] and the per-configuration mean is over (1, 2).
            "plaquette": half_retr(plaquette(links)).mean(dim=(1, 2)),
            "wilson_2x2": half_retr(wilson_loop(links, 2, 2)).mean(dim=(1, 2)),
            "wilson_4x4": half_retr(wilson_loop(links, 4, 4)).mean(dim=(1, 2)),
            "charge": topological_charge(links),
        }


def run_arm(sampler, links, n_traj: int, record_every: int) -> dict:
    series = {k: [] for k in (*LOCAL, "charge")}
    for step in range(n_traj):
        links, _ = sampler.metropolis_step(links)
        if step % record_every == 0:
            obs = observe(links)
            for k in series:
                series[k].append(obs[k].cpu().numpy())
    return {k: np.asarray(v) for k, v in series.items()}, links


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--data-dir", default="out/u2_2d/data_v2")
    parser.add_argument("--fine-size", type=int, default=32)
    parser.add_argument("--n-chains", type=int, default=64)
    parser.add_argument("--n-traj", type=int, default=400)
    # A UNIFORM budget is unaffordable here: n_steps scales as sqrt(beta), so the
    # top coupling costs 12x the bottom one and a flat 400 trajectories puts a
    # single round at 4.7 h. u1 has the precedent -- its own lead figure carries
    # TWO budget ceilings from two scans and draws each arm's non-convergence
    # against its own ceiling. The same is done here: the budget falls with beta,
    # every coupling records the budget it actually got, and the figure draws it.
    # Nothing is lost, because the arms this shortens are the ones that do not
    # converge at ANY budget in this regime -- shortening turns "> 400" into
    # "> 150", which is a weaker true statement, not a false one.
    parser.add_argument("--traj-schedule", default="100:400,600:200,inf:150",
                        help="beta_f:n_traj breakpoints; 'none' for a flat budget")
    parser.add_argument("--record-every", type=int, default=2)
    parser.add_argument("--n-su2", type=int, default=30)
    parser.add_argument("--sampler-steps", type=int, default=200)
    parser.add_argument("--n-couplings", type=int, default=14)
    parser.add_argument("--betas", default=None,
                        help="comma-separated COARSE betas, overriding the "
                             "log-uniform selection; used to split the scan "
                             "across processes")
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--out-dir", default="out/u2_2d/crossover")
    # THE SECOND ROUND. Every arm above runs PLAIN HMC, because mixing a
    # topological move into the baseline makes the ratio uninterpretable. But
    # plain HMC is not the honest classical baseline either -- that is HMC plus
    # the marginal odd winding move (docs/INSTANTON.md), which is genuinely
    # ergodic. So the scan is run TWICE, once each way, and the figure decides
    # which pair to draw rather than the scan deciding for it. Same seed in both
    # rounds, so the cold and hot initialisations are PAIRED and the difference
    # between the two files is the winding move and nothing else.
    parser.add_argument("--topological-updates", action="store_true",
                        help="run the winding round instead of the plain round")
    parser.add_argument("--winding-charge-step", type=int, default=1, choices=(1, 2))
    parser.add_argument("--winding-interval", type=int, default=5)
    parser.add_argument("--tag", default=None,
                        help="output stem; defaults to crossover / crossover_topo")
    args = parser.parse_args()

    config = load_config(args.config)
    device = resolve_device({"device": args.device or "auto"})
    print(configure_device(device))
    set_seed(args.seed)

    ckpt = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    model, sched = load_det_model(ckpt, device=device)
    print(f"checkpoint {ckpt}")

    # Available coarse bases. The retrain's random-beta training set left 65
    # L = 16 ensembles on disk, so the scan needs NO new base generation -- which
    # is the single reason this costs ~1 h instead of ~4.
    bases = sorted(float(re.search(r"beta([0-9.]+)\.pt", f).group(1))
                   for f in glob.glob(f"{args.data_dir}/u2_L16_*.pt"))
    if not bases:
        print(f"no L=16 ensembles under {args.data_dir}")
        return 1
    # Log-uniform selection across the available range, so the scan spans the
    # crossover instead of clustering where the draws happened to be dense.
    if args.betas:
        chosen = sorted(min(bases, key=lambda b: abs(b - float(t)))
                        for t in args.betas.split(","))
    else:
        targets = np.exp(np.linspace(np.log(min(bases)), np.log(max(bases)),
                                     args.n_couplings))
        chosen = sorted({min(bases, key=lambda b: abs(math.log(b) - math.log(t)))
                         for t in targets})
    print(f"{len(chosen)} couplings: " + ", ".join(f"{b:g}" for b in chosen))
    if args.topological_updates:
        print(f"WINDING round: charge_step={args.winding_charge_step}, "
              f"interval={args.winding_interval}")
    else:
        print("PLAIN round: no topological updates in any arm")

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = args.tag or ("crossover_topo" if args.topological_updates else "crossover")
    size = args.fine_size
    rows = []

    schedule = []
    if args.traj_schedule and args.traj_schedule.lower() != "none":
        for part in args.traj_schedule.split(","):
            cut, n = part.split(":")
            schedule.append((float(cut), int(n)))

    for base_beta in chosen:
        beta = topology_matched_fine_beta(base_beta, 16)
        n_traj = args.n_traj
        for cut, n in schedule:
            if beta <= cut:
                n_traj = n
                break
        t0 = time.time()
        # The lift is ~40% of a coupling's cost and is IDENTICAL in the plain and
        # the winding round -- the seed does not know which sampler will consume
        # it. Cache it, so the second round pays for it once between them and a
        # re-run of either pays nothing.
        cache = out / "seeds" / f"seed_L{size}_beta{beta:g}_n{args.n_chains}.pt"
        if cache.exists():
            fine, _ = load_ensemble(cache)
            build_s = 0.0
        else:
            coarse, _ = load_ensemble(Path(args.data_dir) / f"u2_L16_beta{base_beta:g}.pt")
            coarse = coarse[:args.n_chains]
            # Only n_chains configurations are needed -- the arms run that many
            # chains -- so the lift is 16x cheaper here than stage 03's 1024.
            fine = generate_fine_from_coarse(
                model, sched, coarse, beta, n_su2_sweeps=args.n_su2, device=device,
                n_sampler_steps=args.sampler_steps, n_corrector_steps=1,
                batch_size=args.n_chains, consistency_weight=1.0,
                physics_blend_coef=0.0)
            build_s = time.time() - t0
            cache.parent.mkdir(parents=True, exist_ok=True)
            save_ensemble(cache, fine.cpu(), {"beta": beta, "lattice_size": size,
                                              "base_beta": base_beta})

        action = WilsonU2Action(beta)
        step_size, n_steps = adapted_hmc_params(beta)
        # wilson_loop_exact takes AREA, not extents: <W(A)> = r_fund^A.
        targets_exact = {
            "plaquette": plaquette_exact(beta, size),
            "wilson_2x2": wilson_loop_exact(beta, 4),
            "wilson_4x4": wilson_loop_exact(beta, 16),
        }
        qs, ps = det_topological_charge_distribution(beta, size)
        q2_exact = float((np.asarray(qs) ** 2 * np.asarray(ps)).sum())

        record = {"lattice_size": size, "beta": beta, "base_beta": base_beta,
                  "model_beta": matched_u1_beta(beta), "q_squared_exact": q2_exact,
                  "build_seconds": build_s, "n_traj": n_traj,
                  "t_therm": {}, "q_changes": {},
                  "parity_flips": {},
                  "topological_updates": bool(args.topological_updates),
                  "winding_charge_step": int(args.winding_charge_step),
                  "winding_interval": int(args.winding_interval)}

        # ALL THREE ARMS IN ONE BATCH -- the single biggest speed-up available
        # here, and it is free. U(2) batched HMC on this GPU is KERNEL-LAUNCH
        # bound, not compute bound: CLAUDE.md measures throughput FLAT at ~5
        # traj/s from L = 16 to L = 64, and nvidia-smi reports 77% "utilization"
        # at 54 W on a card that pulls twice that, which is what a GPU idling
        # between tiny launches looks like. Three arms run sequentially at 64
        # chains issue 3x the launches for the same arithmetic; concatenated into
        # one 192-chain batch they issue the launches ONCE and the extra work
        # rides along in kernels that were mostly empty.
        #
        # This is EXACT, not an approximation. `BatchedHMCU2` draws momenta
        # per chain and accepts/rejects per chain, and `winding_update` proposes
        # per chain, so a chain's trajectory does not depend on which other
        # chains share its batch. The arms stay statistically independent; only
        # the RNG interleaving differs, and that is not a physical difference.
        arms = ("diffusion seed", "cold start", "hot start")
        n = args.n_chains
        sampler = BatchedHMCU2(size, action, n_chains=len(arms) * n,
                               n_steps=n_steps, step_size=step_size,
                               device=device,
                               topological_updates=args.topological_updates,
                               winding_charge_step=args.winding_charge_step,
                               winding_interval=args.winding_interval)
        start = torch.cat([fine.to(device)[:n],
                           sampler.initialize(hot=False)[:n],
                           sampler.initialize(hot=True)[:n]], dim=0)
        all_series, _ = run_arm(sampler, start, n_traj, args.record_every)

        for i, arm in enumerate(arms):
            series = {k: v[:, i * n:(i + 1) * n] for k, v in all_series.items()}
            record["t_therm"][arm] = {
                name: thermalization_time(series[name], targets_exact[name])
                for name in LOCAL
            }
            q = np.round(series["charge"])
            record["q_changes"][arm] = int((np.diff(q, axis=0) != 0).sum())
            # Parity flips separately: the even winding move is mobile in charge
            # while being unable to change parity, so q_changes alone reports a
            # sampler as healthy while the odd/even balance is stuck.
            record["parity_flips"][arm] = int(
                (np.diff(q.astype(np.int64) % 2, axis=0) != 0).sum())
            # tau_int on the tail of EVERY arm, not just the cold one. The
            # yardstick is 2 tau_int of an EQUILIBRATED chain, and in the regime
            # this study targets the cold chain is not equilibrated even at the
            # end of its budget -- so its "tail" is a drift, and an
            # autocorrelation time fitted to a drift is not a decorrelation time.
            # tau_int is a property of the SAMPLER at that (L, beta), not of the
            # starting configuration, so the equilibrated diffusion-seeded chain
            # measures the same quantity and is the estimator that survives into
            # the frozen regime. Which one was used is recorded, not assumed.
            tail = series["plaquette"][len(series["plaquette"]) // 2:]
            taus = [integrated_autocorrelation_time(tail[:, c])[0]
                    for c in range(tail.shape[1])]
            finite = [t for t in taus if np.isfinite(t)]
            record.setdefault("tau_int_plaquette", {})[arm] = (
                float(np.median(finite)) * args.record_every if finite else None)

        def slowest(arm):
            return max(record["t_therm"][arm].values())

        seed, cold, hot = (slowest("diffusion seed"), slowest("cold start"),
                           slowest("hot start"))

        taus = record["tau_int_plaquette"]
        # Prefer the cold chain where it genuinely equilibrated with room to
        # spare -- that is u1's estimator and keeps the two studies comparable --
        # and fall back to the seeded chain where it did not.
        cold_ok = math.isfinite(cold) and cold < 0.5 * n_traj and taus.get("cold start")
        source = "cold start" if cold_ok else "diffusion seed"
        tau = taus.get(source)
        record["interval_source"] = source
        record["interval"] = 2.0 * tau if tau else None
        record["q_frozen"] = record["q_changes"]["cold start"] == 0
        # In the winding round the charge moves by construction, so the question
        # that separates a healthy sampler from a stuck one is PARITY, not charge.
        record["parity_frozen"] = record["parity_flips"]["cold start"] == 0
        if math.isinf(hot) and math.isinf(cold):
            record["regime"] = "HMC dead"
        elif record["q_frozen"] or record["parity_frozen"]:
            record["regime"] = "Q frozen" if record["q_frozen"] else "parity frozen"
        else:
            record["regime"] = "HMC healthy"
        best = min(hot, cold)
        record["speedup"] = best / max(seed, 1.0)
        record["speedup_is_bound"] = math.isinf(best)
        record["seed"], record["cold"], record["hot"] = seed, cold, hot
        rows.append(record)

        print(f"  b={beta:8.2f} (model {record['model_beta']:6.2f}) "
              f"<Q^2>ex={q2_exact:5.3f}  seed={seed:6.1f} cold={cold:6.1f} "
              f"hot={hot:6.1f}  n={n_traj:4d}  "
              f"iv={(record['interval'] or float('nan')):5.1f}"
              f"({record['interval_source'][:4]})  "
              f"flips={record['parity_flips']['cold start']:5d}  "
              f"{record['regime']:13s} [{time.time() - t0:.0f}s]", flush=True)
        save_json(out / f"{stem}.json", rows)

    save_json(out / f"{stem}.json", rows)
    print(f"wrote {out / (stem + '.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
