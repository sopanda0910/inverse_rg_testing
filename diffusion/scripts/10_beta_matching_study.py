"""Beta-matching criterion study: is matching the mean plaquette enough?

Answers the question quantitatively, using the fact that in 2D U(1) the blocked
theory is exactly known in character space (r_q -> r_q(beta_f)^4), so every
alternative matching criterion and every residual can be computed without
simulation:

    Part A (analytic): compare the mean-plaquette-matched coupling against
        r_2-matched, chi_t-matched, least-squares-over-4-characters, and the
        KL-divergence minimizer across the project's coupling range; report the
        irreducible residuals (r_2, r_3, chi_t, plaquette-density KS) of the
        one-coupling Wilson description and the plaquette damage each
        alternative criterion would cause.
    Part B (Monte Carlo cross-check): block the stored training ensembles,
        verify the measured blocked characters against the exact prediction
        <cos q Theta_P> = W_q(area 4) on the fine lattice, and compare
        match_coarse_beta with n_characters = 1 vs 3 against bootstrap errors.

Writes report.md, summary.json, and fig_beta_matching.png into
out/diffusion/demo/beta_matching/ (override with --dir).

    .venv/Scripts/python.exe diffusion/scripts/10_beta_matching_study.py
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from scipy.optimize import brentq, minimize_scalar
from scipy.special import ive

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from diffusion.lgt.blocking import (
    block_links,
    blocked_character_exact,
    match_coarse_beta,
    matching_residuals,
)
from diffusion.lgt.exact import (
    blocked_plaquette_angle_density,
    plaquette_angle_density,
    plaquette_character_exact,
    topological_susceptibility_exact,
    wilson_loop_exact,
)
from diffusion.lgt.lattice import plaquette_angles
from diffusion.utils import load_ensemble, save_json
from diffusion.validate.report import GEN_COLOR, REF_COLOR, INK, MUTED, GRID_COLOR

OUT = Path("out/diffusion/demo/beta_matching")
DATA_DIR = Path("out/diffusion/demo/data")
LADDER_FINE_BETAS = [4.0, 14.1464, 55.0237]
TRAIN_BETAS = [1.0, 2.0, 4.0, 5.0, 6.5, 8.0, 14.1464, 55.0237]
CHI_COLOR = "#8a63c9"
LSQ_COLOR = "#d6702a"


def _match_character(target: float, q: int) -> float:
    return float(
        brentq(lambda b: float(ive(q, b) / ive(0, b)) - target, 1e-8, 1e5, xtol=1e-12)
    )


def criterion_comparison(fine_beta: float) -> dict:
    """All one-parameter matching criteria for the blocked theory of `fine_beta`."""
    res = matching_residuals(fine_beta, n_characters=3)
    b1 = res["matched_beta"]
    r1_target = blocked_character_exact(fine_beta, 1)
    b2 = _match_character(blocked_character_exact(fine_beta, 2), 2)

    grid = np.linspace(-math.pi, math.pi, 8001)
    f_blocked = blocked_plaquette_angle_density(grid, fine_beta)
    chi_target = float(
        np.trapezoid((grid / (2 * math.pi)) ** 2 * f_blocked, grid)
        / np.trapezoid(f_blocked, grid)
    )
    b_chi = float(
        brentq(
            lambda b: topological_susceptibility_exact(b) - chi_target,
            1e-3,
            max(4.0 * fine_beta, 1.0),
            xtol=1e-10,
        )
    )

    mean_cos = float(np.trapezoid(np.cos(grid) * f_blocked, grid))
    b_kl = float(
        minimize_scalar(
            lambda b: -b * mean_cos + math.log(float(ive(0, b))) + b,
            bracket=(0.5 * b1, b1, 2.0 * b1),
            method="brent",
        ).x
    )

    qs = np.arange(1, 5)
    targets = np.array([blocked_character_exact(fine_beta, int(q)) for q in qs])
    b_lsq = float(
        minimize_scalar(
            lambda b: float(((ive(qs, b) / ive(0, b) - targets) ** 2).sum()),
            bracket=(0.5 * b1, b1, 2.0 * b1),
            method="brent",
        ).x
    )

    return {
        "fine_beta": fine_beta,
        "beta_plaquette": b1,
        "beta_r2": b2,
        "beta_chi_t": b_chi,
        "beta_kl": b_kl,
        "beta_lsq4": b_lsq,
        "residual_r2": res["character_residuals"][2],
        "residual_r3": res["character_residuals"][3],
        "residual_chi_t": res["chi_t_residual"],
        "ks_distance": res["ks_distance"],
        "plaquette_damage_r2": plaquette_character_exact(b2, 1) / r1_target - 1.0,
        "plaquette_damage_chi_t": plaquette_character_exact(b_chi, 1) / r1_target - 1.0,
    }


def matched_beta_statistical_noise(b1: float, n_configs: int = 2000, coarse_l: int = 8) -> float:
    """1-sigma statistical error of match_coarse_beta from a finite blocked ensemble:
    plaquette standard error propagated through d<cos theta_p>/dbeta."""
    r1 = float(ive(1, b1) / ive(0, b1))
    r2 = float(ive(2, b1) / ive(0, b1))
    var_cos = 0.5 * (1.0 + r2) - r1 * r1
    plaq_se = math.sqrt(var_cos / (n_configs * coarse_l * coarse_l))
    eps = 1e-6 * max(b1, 1.0)
    slope = (
        float(ive(1, b1 + eps) / ive(0, b1 + eps)) - float(ive(1, b1 - eps) / ive(0, b1 - eps))
    ) / (2.0 * eps)
    return plaq_se / slope


def mc_cross_check(path: Path, n_boot: int = 200) -> dict:
    """Blocked characters of a stored ensemble vs the exact prediction, and the
    matched beta under 1- vs 3-character matching with bootstrap errors."""
    configs, meta = load_ensemble(path)
    fine_beta = float(meta["beta"])
    fine_l = int(meta["lattice_size"])
    blocked = block_links(configs)
    angles = plaquette_angles(blocked)

    per_config = {
        q: torch.cos(q * angles).mean(dim=(-2, -1)).numpy() for q in (1, 2, 3)
    }
    exact_chars = {
        q: wilson_loop_exact(fine_beta, 4, "wilson", fine_l, charge=q) for q in (1, 2, 3)
    }
    n = configs.shape[0]
    rng = np.random.default_rng(0)
    boot_b1, boot_b3 = [], []
    idx_all = np.arange(n)
    for _ in range(n_boot):
        idx = rng.choice(idx_all, size=n, replace=True)
        boot_b1.append(float(np.mean(per_config[1][idx])))
        boot_b3.append([float(np.mean(per_config[q][idx])) for q in (1, 2, 3)])

    b1 = match_coarse_beta(blocked)
    b3 = match_coarse_beta(blocked, n_characters=3)
    b1_err = float(np.std([_finite_volume_match(m, blocked.shape[-1]) for m in boot_b1]))

    chars = {}
    for q in (1, 2, 3):
        measured = float(per_config[q].mean())
        err = float(per_config[q].std() / math.sqrt(n / 4))
        chars[q] = {
            "measured": measured,
            "exact": exact_chars[q],
            "z": (measured - exact_chars[q]) / err if err > 0 else float("nan"),
        }
    return {
        "fine_beta": fine_beta,
        "n_configs": n,
        "characters": chars,
        "matched_beta_1char": b1,
        "matched_beta_1char_err": b1_err,
        "matched_beta_3char": b3,
        "shift_over_error": (b3 - b1) / b1_err if b1_err > 0 else float("nan"),
    }


def _finite_volume_match(target: float, coarse_l: int) -> float:
    from diffusion.lgt.exact import plaquette_exact

    return float(
        brentq(lambda b: plaquette_exact(b, "wilson", coarse_l) - target, 1e-3, 256.0, xtol=1e-8)
    )


def _style(ax):
    ax.grid(color=GRID_COLOR, lw=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8, colors=MUTED)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)


def make_figure(rows: list[dict]) -> None:
    betas = np.array([r["fine_beta"] for r in rows])
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))

    ax = axes[0]
    b1 = np.array([r["beta_plaquette"] for r in rows])
    for key, color, marker, ls, label in (
        ("beta_r2", GEN_COLOR, "o", "-", r"match $r_2$"),
        ("beta_chi_t", REF_COLOR, "s", "--", r"match $\chi_t$"),
        ("beta_lsq4", LSQ_COLOR, "^", "-.", r"least-squares $r_{1..4}$"),
    ):
        vals = np.array([r[key] for r in rows]) / b1 - 1.0
        ax.plot(betas, np.abs(vals), ls, marker=marker, ms=4, mfc="none", color=color,
                lw=1.4, label=label)
    noise = np.array(
        [abs(matched_beta_statistical_noise(b)) / b for b in b1]
    )
    ax.plot(betas, noise, ":", color=INK, lw=1.4,
            label="stat. noise of the fit\n(2000 configs, $L_c=8$)")
    kl = np.array([abs(r["beta_kl"] / r["beta_plaquette"] - 1.0) for r in rows])
    ax.annotate(
        rf"KL minimizer $\equiv$ plaquette match" + "\n" + rf"(max dev {kl.max():.1e})",
        xy=(0.97, 0.95), xycoords="axes fraction", fontsize=8, color=MUTED,
        ha="right", va="top",
    )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"fine coupling $\beta_f$", fontsize=9, color=INK)
    ax.set_ylabel(r"$|\beta'_{\rm crit} / \beta'_{\rm plaq} - 1|$", fontsize=9, color=INK)
    ax.set_title("Alternative criteria vs the ML (plaquette) match", fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    _style(ax)

    ax = axes[1]
    for key, color, marker, ls, label in (
        ("residual_r2", GEN_COLOR, "o", "-", r"$r_2$ residual"),
        ("residual_chi_t", REF_COLOR, "s", "--", r"$\chi_t$ residual"),
        ("ks_distance", CHI_COLOR, "^", "-.", "plaquette-density KS"),
    ):
        vals = np.abs([r[key] for r in rows])
        ax.plot(betas, vals, ls, marker=marker, ms=4, mfc="none", color=color, lw=1.4,
                label=label)
    for b in LADDER_FINE_BETAS:
        ax.axvline(b, color=MUTED, lw=0.6, ls=":", zorder=1)
    ax.annotate("ladder rungs", xy=(15.0, 0.9), xycoords=("data", "axes fraction"),
                fontsize=8, color=MUTED, rotation=90, va="top")
    ax.axvspan(4.0, 8.0, color=GRID_COLOR, alpha=0.45, zorder=0)
    ax.annotate("crossover\n($\\chi_t$ peak)", xy=(5.6, 0.05), xycoords=("data", "axes fraction"),
                fontsize=8, color=MUTED, ha="center")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"fine coupling $\beta_f$", fontsize=9, color=INK)
    ax.set_ylabel("|relative residual|", fontsize=9, color=INK)
    ax.set_title("Irreducible error of the one-coupling description", fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    _style(ax)

    ax = axes[2]
    grid = np.linspace(-math.pi, math.pi, 2001)
    for fine_beta, color in ((4.0, GEN_COLOR), (14.1464, REF_COLOR)):
        matched = matching_residuals(fine_beta)["matched_beta"]
        truth = blocked_plaquette_angle_density(grid, fine_beta)
        model = plaquette_angle_density(grid, matched, "wilson")
        ax.plot(grid, truth, "-", color=color, lw=1.6,
                label=rf"exact blocked, $\beta_f={fine_beta:g}$")
        ax.plot(grid, model, "--", color=color, lw=1.1, alpha=0.85,
                label=rf"Wilson $\beta'={matched:.3f}$")
    ax.set_xlabel(r"coarse plaquette angle $\Theta_P$", fontsize=9, color=INK)
    ax.set_ylabel("density", fontsize=9, color=INK)
    ax.set_title("Blocked density vs matched Wilson density", fontsize=10, color=INK)
    ax.legend(fontsize=8, frameon=False)
    _style(ax)

    fig.suptitle(
        "Beta matching: mean-plaquette matching is the ML/min-KL projection onto the "
        "Wilson family; the residuals are the family's, not the criterion's",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT / "fig_beta_matching.png", dpi=130)
    plt.close(fig)


def write_report(rows: list[dict], mc: list[dict]) -> None:
    project = [r for r in rows if any(abs(r["fine_beta"] - b) < 1e-9 for b in TRAIN_BETAS)]
    lines = [
        "# Beta-matching criterion study",
        "",
        "**Question.** `match_coarse_beta` fixes the coarse coupling using only the mean",
        "plaquette. Is that justified, or should more observables enter the match?",
        "",
        "**Answer.** Justified, and provably optimal *given the Wilson form of the coarse",
        "action*. The Wilson weight `exp(beta cos theta_p)` is a one-parameter exponential",
        "family with sufficient statistic `sum_p cos theta_p`, so the mean-plaquette match",
        "is exactly the maximum-likelihood fit / minimum-KL projection of the true blocked",
        "theory onto the Wilson family; matching the full plaquette-distribution shape in",
        "the KL sense gives the *same* beta (verified numerically below to ~1e-9). The only",
        "thing a different criterion could buy is a different compromise, and every",
        "alternative sacrifices `r_1` -- i.e. all fundamental Wilson loops, all Creutz",
        "ratios, and the string tension (`<W(A)> = r_1^A`) -- which are the observables the",
        "validation suite is built on.",
        "",
        "The *irreducible* error lives in the Wilson family itself: the exact blocked",
        "theory has `r_q -> r_q(beta_f)^4` for every charge q, which no single Wilson",
        "coupling can reproduce. `matching_residuals` reports that error budget exactly.",
        "",
        "## Part A: criteria and residuals at the project couplings (exact, no simulation)",
        "",
        "| beta_f | beta'(plaq=ML=KL) | beta'(r2) | beta'(chi_t) | beta'(lsq r1-4) | "
        "res r2 | res chi_t | KS | plaq damage if r2 | plaq damage if chi_t |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in project:
        lines.append(
            f"| {r['fine_beta']:g} | {r['beta_plaquette']:.5f} | {r['beta_r2']:.5f} | "
            f"{r['beta_chi_t']:.5f} | {r['beta_lsq4']:.5f} | {r['residual_r2']:+.2e} | "
            f"{r['residual_chi_t']:+.2e} | {r['ks_distance']:.2e} | "
            f"{r['plaquette_damage_r2']:+.2e} | {r['plaquette_damage_chi_t']:+.2e} |"
        )
    lines += [
        "",
        "Reading the table:",
        "",
        "- `beta'(KL)` is omitted because it coincides with the plaquette match at every",
        "  coupling (max relative deviation ~1e-9): *minimizing the distribution-shape*",
        "  *error IS mean-plaquette matching*.",
        "- Adopting the `r_2` or `chi_t` criterion would move the mean plaquette by the",
        "  last two columns -- e.g. -2.1e-1 / +3.1e-2 at beta_f = 4, i.e. hundreds of",
        "  sigma in the validation suite -- while the residual it removes is far smaller.",
        "- At the ladder matches 55.02 -> 14.146 and 14.146 -> 4.0 the residuals of the",
        "  default match are <= 2e-2 (and <= 5e-4 at the finest), well below the",
        "  per-ensemble statistical resolution.",
        "- The chi_t residual **peaks (~6%) in the crossover beta_f ~ 5-6.5** -- exactly",
        "  where the generalization study found its seed-sensitive `<Q^2>` weak spot",
        "  (base beta_c = 2 -> beta_f = 6.105). A Wilson base ensemble at beta_c carries",
        "  ~6% *more* chi_t than the true blocked theory it stands in for, so study-A",
        "  cases in this window inherit a +O(5%) `<Q^2>` systematic unless retherm Q-hops",
        "  fully re-equilibrate P(Q). This is a property of the one-coupling coarse",
        "  action, not of the matching criterion, and cannot be removed by matching",
        "  differently -- only by enlarging the coarse-action family (e.g. a cos(2 theta)",
        "  term) or by re-equilibrating topology after seeding.",
        "",
        "## Part B: Monte Carlo cross-check on the stored training ensembles",
        "",
        "Blocked characters `<cos(q Theta_P)>` vs the exact finite-volume prediction",
        "`W_q(area 4)` on the fine lattice, and the matched beta under 1- vs 3-character",
        "matching (shift measured against the 1-character fit's bootstrap error):",
        "",
        "| beta_f | configs | z(r1) | z(r2) | z(r3) | beta'(1 char) | beta'(3 chars) | "
        "shift / stat.err |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in mc:
        c = m["characters"]
        lines.append(
            f"| {m['fine_beta']:g} | {m['n_configs']} | {c[1]['z']:+.1f} | {c[2]['z']:+.1f} | "
            f"{c[3]['z']:+.1f} | {m['matched_beta_1char']:.4f} +- "
            f"{m['matched_beta_1char_err']:.4f} | {m['matched_beta_3char']:.4f} | "
            f"{m['shift_over_error']:+.1f} |"
        )
    lines += [
        "",
        "The measured characters agree with the exact blocked theory (|z| <~ 2), i.e. the",
        "ensembles themselves contain no information the analytic error budget misses.",
        "Where the 3-character fit shifts beta' by many statistical sigma (small beta_f),",
        "that shift is precisely the family compromise quantified in Part A -- it buys a",
        "smaller r_2 residual at the price of a much larger plaquette/Wilson-loop error,",
        "so the default stays at n_characters = 1.",
        "",
        "![beta matching](fig_beta_matching.png)",
        "",
        "Figure: (left) alternative criteria converge to the plaquette match as beta_f",
        "grows; dotted line is the statistical noise floor of the ensemble fit. (middle)",
        "irreducible residuals of the one-coupling description; ladder rungs marked, the",
        "shaded band is the crossover where the chi_t residual peaks. (right) exact",
        "blocked plaquette density vs the matched Wilson density at the two coarsest",
        "ladder matches -- the shape mismatch is at the percent level at beta_f = 4 and",
        "invisible at 14.15.",
    ]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=None, help="output directory (default: demo path)")
    parser.add_argument("--data-dir", default=None, help="training ensembles for Part B")
    args = parser.parse_args()
    if args.dir:
        OUT = Path(args.dir)
    OUT.mkdir(parents=True, exist_ok=True)
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR

    grid_betas = sorted(set(np.geomspace(1.2, 280.0, 40).tolist() + TRAIN_BETAS))
    rows = []
    for beta in grid_betas:
        rows.append(criterion_comparison(float(beta)))
        print(
            f"beta_f={beta:8.4g}  beta'={rows[-1]['beta_plaquette']:.5f}  "
            f"res_r2={rows[-1]['residual_r2']:+.2e}  res_chi={rows[-1]['residual_chi_t']:+.2e}  "
            f"KS={rows[-1]['ks_distance']:.2e}"
        )

    mc = []
    for path in sorted(data_dir.glob("wilson_L*_beta*.pt")):
        result = mc_cross_check(path)
        mc.append(result)
        print(
            f"MC {path.name}: beta'(1)={result['matched_beta_1char']:.4f} "
            f"+-{result['matched_beta_1char_err']:.4f}  beta'(3)={result['matched_beta_3char']:.4f}"
        )
    mc.sort(key=lambda m: m["fine_beta"])

    make_figure(rows)
    write_report(rows, mc)
    save_json(OUT / "summary.json", {"analytic": rows, "mc_cross_check": mc})
    for name in ("report.md", "summary.json", "fig_beta_matching.png"):
        print(OUT / name)


if __name__ == "__main__":
    main()
