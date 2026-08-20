"""Stage 18: how far is the lift from the target measure, in nats per site?

The gap this closes. Every accuracy claim in this study is an OBSERVABLE claim --
plaquettes, Wilson loops, sector histograms, per-configuration spread. u1_2d
established that observable agreement does not constrain the density: there the
plaquette matched to two parts in 10^4 while the measure was ~1 nat/site away.
Until the same quantity is measured here, "the generated density is close to the
target" (NARRATIVE section 20, claim 3) rests on a proxy.

**And here the measurement is of the whole pipeline, exactly.** One inverse-RG
step factorizes as p(psi, q) = p(psi) p(q | psi); the SU(2) conditional is
sampled EXACTLY by `conditional_su2_sweeps`, so it is the same distribution on
both sides of the KL and cancels identically:

    KL( m(psi) p(q|psi) || p(psi) p(q|psi) ) = KL( m(psi) || p(psi) ).

The determinant sector's density gap IS the U(2) pipeline's density gap. No
inequality, no residual term. u1_2d could not make that statement about any of
its sectors, and it is worth stating in exactly those words.

The instrument is the probability-flow ODE with Hutchinson divergence, validated
the way u1_2d validated it -- on a case easy enough that the ESS is usable and
the free-energy certificate closes. Read the cases in order: if the easy case's
`gap` is not small, nothing below it is readable.

THE CERTIFICATE NEEDS AN HMC COARSE ENSEMBLE, not a generated one. The identity
prices the proposal joint pi_c(psi_c) q(psi_f | psi_c) against the target, and
pi_c has to actually be exp(-S_det(beta_c))/Z. Feeding it rung 0's own output
would price the model against itself. Every case below therefore starts from a
stage-01 ensemble, which is also why the fine couplings are the ladder's own but
the coarse ones are the HMC rungs beside them.

    python u2_2d/scripts/18_density_gap.py --n-configs 64
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from u1_2d.model.schedule import GeometricNoiseSchedule
from u2_2d.lgt.exact import plaquette_exact
from u2_2d.lgt.lattice import det_links
from u2_2d.model.det_lift import model_beta
from u2_2d.model.det_likelihood import (
    conditional_ode_sample,
    det_free_energy_certificate,
    det_log_weights,
    ess_per_n,
)
from u2_2d.utils import (
    configure_device,
    ensemble_path,
    load_config,
    load_ensemble,
    resolve_device,
    save_json,
    set_seed,
)

# coarse (L, beta) from stage 01  ->  fine beta. The first is the instrument
# validation: small, weakly coupled, comfortably inside the training range.
DEFAULT_CASES = [
    "8:3.5:14",
    "8:7:28",
    "16:28:105.651",
    "32:105.651:416.524",
]


def load_model(checkpoint: str, device: str):
    from u1_2d.model.score_net import GaugeCovariantScoreNet

    ckpt = torch.load(checkpoint, map_location=device, weights_only=False)
    model = GaugeCovariantScoreNet(**ckpt["model_kwargs"]).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    schedule = GeometricNoiseSchedule(
        sigma_min=float(ckpt.get("sigma_min", 0.02)),
        sigma_max=float(ckpt.get("sigma_max", 6.0)),
        sigma_min_beta_coef=ckpt.get("sigma_min_beta_coef"),
    )
    return model, schedule


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="u2_2d/configs/default.yaml")
    parser.add_argument("--cases", nargs="+", default=DEFAULT_CASES,
                        help="coarse_L:coarse_beta:fine_beta")
    parser.add_argument("--n-configs", type=int, default=64)
    parser.add_argument("--ode-steps", type=int, default=120)
    parser.add_argument("--n-probes", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--consistency-weight", type=float, default=1.0)
    parser.add_argument("--physics-blend", type=float, default=0.0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--seed", type=int, default=1818)
    parser.add_argument("--out-dir", default="out/u2_2d/density_gap")
    parser.add_argument("--checkpoint", default=None,
                        help="override the config checkpoint; required to A/B two "
                             "trained nets, since --out-dir alone silently reruns "
                             "the same weights into a new directory")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.device:
        config["device"] = args.device
    device = resolve_device(config)
    print(configure_device(device))
    set_seed(args.seed)

    checkpoint = args.checkpoint or config["train"].get(
        "checkpoint_path", "out/u2_2d/checkpoints/det_score_net.pt")
    if not Path(checkpoint).exists():
        print(f"missing {checkpoint} -- run stage 02 first")
        return 1
    print(f"checkpoint {checkpoint}")
    model, schedule = load_model(checkpoint, device)

    data_dir = config["data"].get("out_dir", "out/u2_2d/data")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in args.cases:
        cl, cb, fb = case.split(":")
        coarse_L, beta_c, beta_f = int(cl), float(cb), float(fb)
        fine_L = 2 * coarse_L
        path = ensemble_path(data_dir, coarse_L, beta_c)
        if not path.exists():
            print(f"[skip] {case}: missing {path}")
            continue
        coarse, _ = load_ensemble(path)
        coarse = coarse[: args.n_configs]
        psi_c = det_links(coarse)

        print(f"\n=== {case}  (L {coarse_L} -> {fine_L}, "
              f"beta {beta_c:g} -> {beta_f:g}, model beta "
              f"{model_beta(beta_f):.3f}, n={psi_c.shape[0]}) ===", flush=True)
        t0 = time.time()
        psi_f, log_q = conditional_ode_sample(
            model, schedule, psi_c, beta_f,
            n_steps=args.ode_steps, n_probes=args.n_probes,
            consistency_weight=args.consistency_weight,
            physics_blend_coef=args.physics_blend,
            batch_size=args.batch_size, device=device, seed=args.seed,
        )
        seconds = time.time() - t0

        log_w = det_log_weights(psi_f, log_q, beta_f, psi_c, beta_c)
        cert = det_free_energy_certificate(log_w, fine_L, beta_f, beta_c)
        row = {
            "case": case,
            "coarse_lattice_size": coarse_L,
            "fine_lattice_size": fine_L,
            "coarse_beta": beta_c,
            "fine_beta": beta_f,
            "model_beta": model_beta(beta_f),
            "n": int(psi_f.shape[0]),
            "ode_steps": args.ode_steps,
            "n_probes": args.n_probes,
            "ess_per_n": ess_per_n(log_w),
            "seconds": seconds,
            "free_energy_certificate": cert,
            "plaquette_exact": plaquette_exact(beta_f, fine_L),
        }
        results.append(row)
        print(f"  KL = {cert['kl_from_mean_log_w']:.1f} +- {cert['kl_sem']:.1f} nats "
              f"= {cert['kl_per_site']:.3f} nats/site   "
              f"gap {cert['gap']:+.2f}   ESS/N {row['ess_per_n']:.4f}   "
              f"[{seconds:.0f}s]", flush=True)
        save_json(out_dir / "density_gap.json", results)

    if results:
        _write_report(out_dir / "report.md", results)
        print(f"\nwrote {out_dir / 'density_gap.json'} and report.md")
    return 0


def _write_report(path: Path, rows: list) -> None:
    lines = [
        "# The determinant lift's density gap, in nats per site",
        "",
        "Because the SU(2) conditional is sampled EXACTLY, it is the same "
        "distribution on both sides of the KL and cancels identically:",
        "",
        "$$\\mathrm{KL}\\big(m(\\psi)\\,p(q|\\psi)\\,\\|\\,p(\\psi)\\,p(q|\\psi)\\big)"
        " = \\mathrm{KL}\\big(m(\\psi)\\,\\|\\,p(\\psi)\\big).$$",
        "",
        "So the number below is **the whole pipeline's** density gap, not one "
        "sector's -- with no inequality and no residual term.",
        "",
        "| case | $L$ | $\\beta_f$ | model $\\beta$ | KL (nats) | **nats/site** | "
        "certificate gap | ESS/$N$ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        c = r["free_energy_certificate"]
        lines.append(
            f"| {r['case']} | {r['fine_lattice_size']} | {r['fine_beta']:g} | "
            f"{r['model_beta']:.2f} | {c['kl_from_mean_log_w']:.1f} $\\pm$ "
            f"{c['kl_sem']:.1f} | **{c['kl_per_site']:.3f}** | {c['gap']:+.2f} | "
            f"{r['ess_per_n']:.4f} |")

    easy = rows[0]
    lines += [
        "",
        "## How to read it",
        "",
        "**Read the first row first.** It is the instrument validation: the "
        "smallest, most weakly coupled case, comfortably inside the training "
        f"range. Its certificate gap is {easy['free_energy_certificate']['gap']:+.2f} "
        f"nats at ESS/$N$ = {easy['ess_per_n']:.4f}. The `gap` is the "
        "certificate and must go to zero as the ESS goes to one; where the ESS "
        "has collapsed the log-mean-exp sits near $\\max \\log w$ and the gap "
        "reads roughly $-$KL, which is a diagnostic of weight degeneracy and "
        "not a defect of the free energy.",
        "",
        "**The KL column is the measurement and survives ESS collapse.** The "
        "identity $E[\\log w] - \\Delta F_{\\rm exact} = -\\mathrm{KL}$ holds "
        "whatever the weights do, so `nats/site` stays quantitative long after "
        "`ESS/N` has bottomed out. That is why this replaces ESS as the reported "
        "quantity -- a saturated ESS says only \"too small to measure\".",
        "",
        "**Charge projection is absent from the sampler here, deliberately.** It "
        "is not a diffeomorphism, so including it would invalidate the density "
        "the ODE reports. The configurations priced here are therefore the "
        "model's raw output, which is the thing whose density one wants to know.",
        "",
        "Source: `u2_2d/scripts/18_density_gap.py`, "
        "`u2_2d/model/det_likelihood.py`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
