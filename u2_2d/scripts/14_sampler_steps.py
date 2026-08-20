"""Stage 14: how many reverse-diffusion steps does the lift actually need?

WHY THIS EXISTS. Stage 13 measured the ladder at 3.87x the cost of HMC + winding
per independent configuration for LOCAL observables, and attributed almost all of
that cost to the 200-step ancestral sampler -- a number that was chosen once, on
no evidence, and never revisited. The narrative then hedged the cost verdict on
the grounds that the sampler was "tunable but untuned", which is not a defensible
thing to leave in a paper. Either the hedge is real and the cost number is
inflated, or it is not and the verdict is final; only a scan decides which.

Two assumptions that motivated this scan turned out to be false, and both matter.
Cost is NOT linear in the step count -- there is a large fixed overhead from the
SU(2) sweeps that no sampler tuning touches -- and accuracy does NOT saturate
early. See the generated results section for the measured numbers.

WHAT DEGRADES AND WHAT CANNOT. Three of the pipeline's outputs respond to the step
count in completely different ways, and conflating them hides the effect:

  * PRE-RETHERMALIZATION observables are the real measurement. They are what the
    diffusion lift produced, unaided, and a coarser sampler shows up here first.
  * POST-RETHERMALIZATION observables are repaired by 10 local sweeps at the fine
    coupling. Local sweeps fix local damage, so this column will keep looking
    healthy well past the point where the model has stopped doing the work. Read
    it as a floor, never as evidence.
  * <Q^2> CANNOT degrade at all. `apply_coarse_charge` imposes the coarse charge
    on the final sample by construction, so topology is transported no matter how
    few steps were taken. A flat <Q^2> column across this scan is a tautology, and
    it is included only so nobody reads it as a result.

So the informative quantity is the pre-retherm plaquette against the closed form,
and the per-configuration Wilson spread, which is where residual model error
concentrates.

THE CHARGE-PROJECTION INTERVAL IS SCALED WITH THE STEP COUNT. In-trajectory
projection fires every `charge_projection_interval` steps below sigma = 0.5; held
fixed at 10, a 25-step run would fire it a couple of times and a 400-step run
forty, which would confound sampler resolution with projection frequency. It is
held at the same FRACTION of the trajectory instead.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u2_2d.lgt.exact import (
    det_topological_susceptibility,
    plaquette_exact,
    wilson_loop_exact,
)
from u2_2d.lgt.lattice import half_retr, wilson_loop
from u2_2d.model.det_lift import load_det_model
from u2_2d.pipeline.ladder import generate_ladder
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
)

LOOPS = {"wilson_2x2": (2, 2), "wilson_4x4": (4, 4), "wilson_8x8": (8, 8)}


def loop_stats(links: torch.Tensor, a: int, b: int) -> tuple[float, float]:
    with torch.no_grad():
        w = half_retr(wilson_loop(links, a, b))
        per_config = w.mean(dim=tuple(range(1, w.dim())))
        return float(per_config.mean()), float(per_config.std())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-dir", default="out/u2_2d/sampler_steps")
    parser.add_argument("--steps", default="25,50,100,200,400")
    parser.add_argument("--n-configs", type=int, default=None,
                        help="default: the ladder's configured n_configs")
    parser.add_argument("--classical-seconds", type=float, default=None,
                        help="s per independent config for hmc+winding; default "
                             "reads it from the stage-13 cost.json")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(int(config.get("seed", 0)))

    ladder_cfg = config["ladder"]
    base = ladder_cfg["base"]
    data_dir = Path(config["data"].get("out_dir", "out/u2_2d/data"))
    base_path = ensemble_path(data_dir, int(base["lattice_size"]), float(base["beta"]))
    if not base_path.exists():
        print(f"missing base ensemble {base_path} -- run stage 01 first")
        return 1
    coarse, _ = load_ensemble(base_path)
    n_configs = int(args.n_configs or ladder_cfg.get("n_configs", coarse.shape[0]))
    coarse = coarse[:n_configs]

    checkpoint = config["train"].get("checkpoint_path",
                                     "out/u2_2d/checkpoints/det_score_net.pt")
    model, schedule = load_det_model(checkpoint, device=device)
    beta_schedule = [float(b) for b in ladder_cfg["beta_schedule"]]

    classical = args.classical_seconds
    if classical is None:
        cost_path = Path("out/u2_2d/seed_benchmark/cost.json")
        if cost_path.exists():
            cost = json.loads(cost_path.read_text(encoding="utf-8"))
            row = next((r for r in cost["arms"] if r["arm"] == "D_cold_plus_winding"), None)
            if row:
                classical = row["seconds_per_independent_config_local"]

    base_interval = int(ladder_cfg.get("charge_projection_interval", 10))
    reference_steps = int(ladder_cfg.get("n_sampler_steps", 200))

    records = []
    for n_steps in [int(s) for s in args.steps.split(",")]:
        interval = max(1, round(base_interval * n_steps / reference_steps))
        set_seed(int(config.get("seed", 0)))
        timings = []
        t0 = time.time()
        results = generate_ladder(
            coarse, beta_schedule, model, schedule,
            n_su2_sweeps=int(ladder_cfg.get("n_su2_sweeps", 30)),
            n_retherm_sweeps=int(ladder_cfg.get("n_retherm_sweeps", 10)),
            batch_size=int(ladder_cfg.get("batch_size", 64)),
            device=device,
            verbose=False,
            n_sampler_steps=n_steps,
            n_corrector_steps=int(ladder_cfg.get("n_corrector_steps", 1)),
            consistency_weight=float(ladder_cfg.get("consistency_weight", 1.0)),
            enforce_coarse_charge=bool(ladder_cfg.get("enforce_coarse_charge", True)),
            charge_projection_interval=interval,
            physics_blend_coef=float(ladder_cfg.get("physics_blend_coef", 0.0)),
            on_rung=lambda r, t=timings: t.append(time.time()),
        )
        wall = time.time() - t0
        # on_rung fires as each rung lands, so successive differences are the
        # per-rung wall clock -- the top rung is what the cost claim is about.
        marks = [t0] + timings
        rung_seconds = [marks[i + 1] - marks[i] for i in range(len(timings))]

        rungs = []
        for res, secs in zip(results, rung_seconds):
            size, beta = res.lattice_size, res.beta
            exact_p = plaquette_exact(beta, size)
            obs = res.observables
            entry = {
                "lattice_size": size, "beta": beta, "seconds": secs,
                "plaquette": obs["plaquette"],
                "plaquette_pre_retherm": obs["plaquette_pre_retherm"],
                "plaquette_exact": exact_p,
                "rel_err": obs["plaquette"] / exact_p - 1.0,
                "rel_err_pre_retherm": obs["plaquette_pre_retherm"] / exact_p - 1.0,
                "q_squared": obs["q_squared"],
                "q_squared_exact": det_topological_susceptibility(beta, size) * size * size,
                "wilson": {},
            }
            for name, (a, b) in LOOPS.items():
                if a >= size:
                    continue
                mean, std = loop_stats(res.configs, a, b)
                ex = wilson_loop_exact(beta, a * b)
                entry["wilson"][name] = {"mean": mean, "std": std, "exact": ex,
                                         "rel_err": mean / ex - 1.0 if ex else float("nan")}
            rungs.append(entry)

        top = rungs[-1]
        rec = {
            "n_sampler_steps": n_steps,
            "charge_projection_interval": interval,
            "n_configs": n_configs,
            "total_seconds": wall,
            "rungs": rungs,
            "seconds_per_config_top_rung": top["seconds"] / n_configs,
            "seconds_per_config_all_rungs": wall / n_configs,
        }
        if classical:
            rec["ratio_vs_hmc_winding_top_rung"] = top["seconds"] / n_configs / classical
            rec["ratio_vs_hmc_winding_all_rungs"] = wall / n_configs / classical
        records.append(rec)
        print(f"steps={n_steps:4d}  {wall:7.1f}s total  top rung "
              f"{top['seconds'] / n_configs:.4f} s/config  "
              f"rel_err(pre) {top['rel_err_pre_retherm']:+.2e}  "
              f"rel_err(post) {top['rel_err']:+.2e}", flush=True)
        del results
        if str(device).startswith("cuda"):
            torch.cuda.empty_cache()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    save_json(out_dir / "sampler_steps.json", records)

    lines = ["# How many sampler steps does the lift need?", "",
             f"Base L = {base['lattice_size']}, beta = {base['beta']:g}; "
             f"{n_configs} configurations up the full schedule "
             + " -> ".join(f"{b:g}" for b in beta_schedule) + ".", "",
             "RUNG 0 is the clean measurement: its input is the fixed HMC base, so its",
             "error is one diffusion lift and nothing else. The top rung lifts rung 0's",
             "output, so its plaquette error is two lifts that partially cancel and it",
             "moves the wrong way across the scan. Extended loops at the top rung are",
             "the other honest column.", "",
             "The post-rethermalization columns are repaired by 10 local sweeps and stay",
             "healthy long past the point where the model has stopped working -- at 8",
             "steps the lift is 1% off and the sweeps hide all of it.", "",
             "| steps | top-rung s | s/config | vs hmc+winding | r0 pre | r0 post | r1 pre | top W(8x8) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in records:
        first, top = r["rungs"][0], r["rungs"][-1]
        ratio = r.get("ratio_vs_hmc_winding_top_rung")
        rs = f"{ratio:.2f}x" if ratio else "-"
        w8 = top["wilson"].get("wilson_8x8", {}).get("rel_err", float("nan"))
        lines.append(
            f"| {r['n_sampler_steps']} | {top['seconds']:.1f} | "
            f"{r['seconds_per_config_top_rung']:.4f} | {rs} | "
            f"{first['rel_err_pre_retherm']:+.2e} | {first['rel_err']:+.2e} | "
            f"{top['rel_err_pre_retherm']:+.2e} | {w8:+.2e} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
