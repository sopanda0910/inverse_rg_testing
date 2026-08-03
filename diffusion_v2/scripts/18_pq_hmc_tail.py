"""P(Q) before/after an instanton-HMC tail: the seeding claim, topologically.

The pipeline's stated purpose is a better STARTING BATCH for HMC. Structural
transport delivers the coarse base's empirical sector histogram (finite-sample,
possibly asymmetric, and wrong for deliberately mismatched targets); an HMC
continuation WITH the instanton Q-hop then re-equilibrates the sectors toward
the exact P(Q) at the target coupling. This script measures exactly that: it
takes the study's transported ensembles, runs an instanton-HMC tail, and plots
P(Q) before / after / exact plus the <Q^2> convergence trajectory.

    python diffusion_v2/scripts/18_pq_hmc_tail.py --gen-dir out/diffusion_v2/generalization
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion_v2.lgt import make_action, exact
from diffusion_v2.lgt.hmc import BatchedHMC, adapted_hmc_params
from diffusion_v2.lgt.lattice import topological_charge
from diffusion_v2.lgt.local_updates import topological_update
from diffusion_v2.utils import load_ensemble, save_json

GEN_COLOR = "#2a78d6"
TAIL_COLOR = "#7a5cc9"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": INK, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.grid": True, "grid.color": GRID_COLOR, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "figure.dpi": 150,
})

DEFAULT_CASES = "B_bt6,A_bc1.5,E_bc11.8,D_bc55.0237,C_L64"


def sector_converged(q, q_values, probs, exact_q2):
    p = chi2_p(q, q_values, probs)
    q2 = float((q.astype(float) ** 2).mean())
    sem = float((q.astype(float) ** 2).std()) / max(len(q), 1) ** 0.5
    tol = max(2.0 * sem, 0.1 * exact_q2 + 5e-3)
    return (p is None or p >= 0.05) and abs(q2 - exact_q2) <= tol


def hmc_tail(configs, beta, action_type, max_traj, device, seed,
             q_values=None, probs=None, exact_q2=None,
             check_every=50, min_traj=100, fixed_traj=None):
    """Instanton-HMC tail; adaptive unless fixed_traj is given.

    Adaptive mode runs in blocks of check_every trajectories and stops once the
    sector convergence criterion (chi^2 p >= 0.05 vs exact P(Q) where testable,
    and ensemble <Q^2> within tolerance of exact) holds on two consecutive
    checks, with a hard cap at max_traj.
    """
    torch.manual_seed(seed)
    action = make_action(action_type, beta)
    step_size, n_steps = adapted_hmc_params(beta, 0.2, 5)
    sampler = BatchedHMC(configs.shape[-1], action, n_chains=configs.shape[0],
                         n_steps=n_steps, step_size=step_size, device=device)
    theta = configs.clone().to(device)
    q_series = [topological_charge(theta).cpu().numpy()]
    target = fixed_traj if fixed_traj is not None else max_traj
    streak = 0
    converged = fixed_traj is not None
    with torch.no_grad():
        for t in range(1, target + 1):
            theta, _ = sampler.metropolis_step(theta)
            theta, _ = topological_update(theta, action)
            q_series.append(topological_charge(theta).cpu().numpy())
            if (fixed_traj is None and t >= min_traj and t % check_every == 0):
                if sector_converged(q_series[-1], q_values, probs, exact_q2):
                    streak += 1
                    if streak >= 2:
                        converged = True
                        break
                else:
                    streak = 0
    return theta.cpu(), np.stack(q_series), converged


def q_hist(q, q_values):
    counts = np.array([(np.round(q) == v).sum() for v in q_values], dtype=float)
    return counts / max(counts.sum(), 1)


def chi2_p(q, q_values, probs):
    from scipy.stats import chisquare
    n = len(q)
    counts = np.array([(np.round(q) == v).sum() for v in q_values], dtype=float)
    keep = probs * n > 2.0
    if keep.sum() < 2:
        return None
    obs, exp = counts[keep], probs[keep] * n
    exp *= obs.sum() / exp.sum()
    return float(chisquare(obs, exp).pvalue)


def run_case(run_id, gen_dir, action_type, args, device, seed, out_dir):
    records = json.loads((gen_dir / "summary.json").read_text(encoding="utf-8"))
    rec = records[run_id]
    beta = float(rec["target_beta"])
    L = 2 * int(rec["base_size"])
    path = gen_dir / "generated" / f"{run_id}_{action_type}_L{L}_beta{beta:g}.pt"
    configs, _ = load_ensemble(path)
    q_before = topological_charge(configs).numpy()
    q_values, probs = exact.topological_charge_distribution(beta, L, action_type)
    exact_q2_early = float((q_values.astype(float) ** 2 * probs).sum())
    t0 = time.time()
    final, q_series, converged = hmc_tail(
        configs, beta, action_type, args.max_traj, device, seed,
        q_values=q_values, probs=probs, exact_q2=exact_q2_early,
        check_every=args.check_every, min_traj=args.min_traj,
        fixed_traj=args.n_traj,
    )
    tail_seconds = time.time() - t0
    n_traj = len(q_series) - 1
    q_after = q_series[-1]
    window = max(3, int(np.ceil(3.5 * math.sqrt(max((q_values.astype(float)**2 * probs).sum(), 0.3)))))
    mask = np.abs(q_values) <= max(window, int(np.abs(q_before).max()), int(np.abs(q_after).max()))
    qv = q_values[mask]
    exact_q2 = float((q_values.astype(float) ** 2 * probs).sum())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.0))
    width = 0.27
    ax1.bar(qv - width, q_hist(q_before, q_values)[mask], width,
            color=GEN_COLOR, label="transported (before tail)")
    ax1.bar(qv, q_hist(q_after, q_values)[mask], width,
            color=TAIL_COLOR, label=f"after {n_traj} instanton-HMC traj")
    ax1.bar(qv + width, probs[mask], width, facecolor="none",
            edgecolor=INK, linewidth=1.4, label="exact P(Q)")
    ax1.set_xlabel("topological charge Q")
    ax1.set_ylabel("probability")
    ax1.grid(axis="x", visible=False)
    ax1.legend(frameon=False, fontsize=8)
    ax1.set_title(f"{run_id}: L={L}, $\\beta_f$={beta:g}", fontsize=10)

    q2_traj = (q_series.astype(float) ** 2).mean(axis=1)
    ax2.plot(np.arange(len(q2_traj)), q2_traj, color=TAIL_COLOR, lw=2,
             label=r"ensemble $\langle Q^2 \rangle$")
    ax2.axhline(exact_q2, color=INK, lw=1.2, ls="--", label="exact")
    ax2.set_xlabel("instanton-HMC trajectory")
    ax2.set_ylabel(r"$\langle Q^2 \rangle$")
    ax2.legend(frameon=False, fontsize=8)
    ax2.set_title("sector re-equilibration", fontsize=10)
    fig.tight_layout()
    fig_path = out_dir / f"{run_id}_pq_tail.png"
    fig.savefig(fig_path, bbox_inches="tight")
    plt.close(fig)

    n = len(q_before)
    result = {
        "run_id": run_id, "beta": beta, "L": L, "n_configs": n,
        "n_traj": n_traj, "converged": converged,
        "max_traj": args.max_traj if args.n_traj is None else args.n_traj,
        "tail_seconds": round(tail_seconds, 1),
        "exact_q2": exact_q2,
        "q2_before": float((q_before**2).mean()),
        "q2_after": float((q_after**2).mean()),
        "q_mean_before": float(q_before.mean()),
        "q_mean_after": float(q_after.mean()),
        "chi2_p_before": chi2_p(q_before, q_values, probs),
        "chi2_p_after": chi2_p(q_after, q_values, probs),
    }
    print(f"  {run_id}: Q^2 {result['q2_before']:.3g} -> {result['q2_after']:.3g} "
          f"(exact {exact_q2:.3g}); chi2 p {result['chi2_p_before']} -> "
          f"{result['chi2_p_after']}; {n_traj} traj"
          f"{'' if converged else ' (NOT CONVERGED at cap)'}; "
          f"{tail_seconds:.0f}s", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gen-dir", default="out/diffusion_v2/generalization")
    parser.add_argument("--cases", default=DEFAULT_CASES)
    parser.add_argument("--n-traj", type=int, default=None,
                        help="fixed trajectory count (disables adaptive stopping)")
    parser.add_argument("--max-traj", type=int, default=2000,
                        help="adaptive mode: hard cap on tail trajectories")
    parser.add_argument("--check-every", type=int, default=50,
                        help="adaptive mode: convergence check interval")
    parser.add_argument("--min-traj", type=int, default=100,
                        help="adaptive mode: minimum trajectories before checks")
    parser.add_argument("--action-type", default="wilson")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    gen_dir = Path(args.gen_dir)
    out_dir = Path(args.out or gen_dir.parent / "pq_hmc_tail")
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for run_id in args.cases.split(","):
        print(f"case {run_id}", flush=True)
        results.append(run_case(run_id.strip(), gen_dir, args.action_type,
                                args, args.device, args.seed, out_dir))
        save_json(out_dir / "summary.json", results)

    mode = (f"a fixed {args.n_traj}-trajectory" if args.n_traj is not None else
            f"an adaptive (cap {args.max_traj}, checked every {args.check_every})")
    lines = [
        "# P(Q): transported batch vs after an instanton-HMC tail",
        "",
        "The pipeline's product is a starting batch for HMC. Structural charge",
        "transport delivers the coarse base's empirical sector histogram;",
        f"{mode} HMC continuation WITH the instanton Q-hop",
        "re-equilibrates sectors toward the exact P(Q) at the target coupling",
        "(the hop's dS ~ 2 pi^2 beta / V keeps acceptance finite at all couplings",
        "studied). Adaptive stopping: chi^2 p >= 0.05 vs exact P(Q) (where",
        "testable) and ensemble <Q^2> within tolerance of exact, on two",
        "consecutive checks. chi^2 p-values are against the exact finite-volume",
        "P(Q).",
        "",
        "| case | L | beta_f | Q^2 before | after | exact | chi2 p before | after | traj | converged | tail s |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        def fp(x):
            return f"{x:.3f}" if isinstance(x, float) else "--"
        lines.append(
            f"| {r['run_id']} | {r['L']} | {r['beta']:g} | {r['q2_before']:.3g} | "
            f"{r['q2_after']:.3g} | {r['exact_q2']:.3g} | {fp(r['chi2_p_before'])} | "
            f"{fp(r['chi2_p_after'])} | {r['n_traj']} | "
            f"{'yes' if r['converged'] else 'NO (cap)'} | {r['tail_seconds']:.0f} |"
        )
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"report: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
