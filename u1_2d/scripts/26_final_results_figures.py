"""Closing figures for the U(1) program: the three-way sampler comparison and
the ESS-program optimum. Reads existing results only (no new simulation).

    python u1_2d/scripts/26_final_results_figures.py
"""

import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("out/u1_2d")
FIG_DIR = OUT / "paper_appendix" / "figures"

GEN_COLOR = "#2a78d6"
HMC_COLOR = "#d64550"
GOOD_GREEN = "#3f9b57"
AMBER = "#d69b2a"
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"
MUTED = "#8f8d86"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": INK, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.grid": True, "grid.color": GRID_COLOR, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "figure.dpi": 280,
})


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_thermalization_table():
    """Rows of the beta-scan summary in thermalization/report.md."""
    rows = []
    pattern = re.compile(r"^\| (\S+) \| (\d+) \| ([\d.]+) \| (\d+) \| ([\d.]+) \| .*? \| (\S+) / (\S+) \| (.+?) \|")
    for line in (OUT / "thermalization" / "report.md").read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if not m:
            continue
        label, l, beta, t_seed, tau2, hot, cold, tauq = m.groups()
        if int(l) != 32:
            continue
        rows.append({
            "beta": float(beta), "t_seed": float(t_seed), "interval": float(tau2),
            "hot": math.inf if hot == "never" else float(hot),
            "cold": math.inf if cold == "never" else float(cold),
            "frozen": tauq.startswith("frozen"),
        })
    return sorted(rows, key=lambda r: r["beta"])


def fig_three_way():
    rows = parse_thermalization_table()
    betas = [r["beta"] for r in rows]
    frozen_from = min(r["beta"] for r in rows if r["frozen"])

    # Height held wider than a strict aspect-preserving rescale would give:
    # two-line panel titles, rotated tick labels, an inline text annotation
    # and a suptitle are all fixed-fontsize text that needs the same number
    # of INCHES regardless of the canvas's overall scale, so shrinking height
    # in step with width (as for a plain data plot) crushed them together.
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(6.9, 4.3), constrained_layout=True)

    top = 3000.0
    ax_a.axvspan(frozen_from, max(betas) * 1.3, color=HMC_COLOR, alpha=0.06)
    # Axes-fraction placement (not data coordinates): safe regardless of how
    # far the pink band extends, and short enough for a ~3.4in-wide panel.
    ax_a.text(0.98, 0.03, "shaded: plain HMC\ntopology frozen", transform=ax_a.transAxes,
              fontsize=7, color=HMC_COLOR, ha="right", va="bottom")
    for key, color, label, marker in (("hot", HMC_COLOR, "plain HMC, hot start", "s"),
                                      ("cold", AMBER, "plain HMC, cold start", "D")):
        xs = [r["beta"] for r in rows]
        ys = [min(r[key], top) for r in rows]
        never = [math.isinf(r[key]) for r in rows]
        ax_a.plot(xs, ys, color=color, lw=1.6, alpha=0.8)
        for x, y, nv in zip(xs, ys, never):
            ax_a.plot([x], [y], marker="^" if nv else marker, ms=7 if nv else 5,
                      color=color, mfc="white" if nv else color, mew=1.5)
        ax_a.plot([], [], marker=marker, ms=5, color=color, lw=1.6, label=label)
    ax_a.plot(betas, [max(r["t_seed"], 0.5) for r in rows], marker="o", ms=6, lw=2,
              color=GEN_COLOR, label="diffusion seed (this pipeline)")
    ax_a.plot([], [], marker="^", ms=7, color=MUTED, mfc="white", lw=0,
              label="open triangle: never thermalizes")
    ax_a.set_xscale("log")
    ax_a.set_yscale("log")
    # A narrow (~3.4in) panel can't hold every log-decade's minor ticks
    # labelled ("6789100200" running together) -- major ticks only.
    ax_a.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, numticks=4))
    ax_a.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax_a.set_xlabel(r"fine coupling $\beta_f$  (L = 32)")
    ax_a.set_ylabel("HMC trajectories until thermalized")
    ax_a.set_title("(a) thermalization cost of\nthree starting points", fontsize=9)
    ax_a.legend(frameon=False, fontsize=8, loc="upper left")

    h2h = _load(OUT / "diffusion_vs_instanton" / "summary.json")

    def quality_ok(arm):
        zs = [abs(arm.get(f"{n}_z", float("nan")))
              for n in ("plaquette", "wilson_2x2", "wilson_4x4", "Q^2")]
        zs = [z for z in zs if math.isfinite(z)]
        return bool(zs) and max(zs) <= 2.5

    for arm_key, color, label in (("instanton_hmc", HMC_COLOR, "instanton HMC (marginal cost)"),
                                  ("diffusion", GEN_COLOR, "diffusion incl. retherm (batch-amortized)")):
        xs = sorted(r["beta"] for r in h2h)
        recs = {r["beta"]: r for r in h2h}
        ys = [recs[b][arm_key]["seconds_per_independent_config"] for b in xs]
        oks = [quality_ok(recs[b][arm_key]) for b in xs]
        ax_b.plot(xs, ys, color=color, lw=2)
        for x, y, ok in zip(xs, ys, oks):
            ax_b.plot([x], [y], marker="o", ms=8, mew=2, color=color,
                      mfc=color if ok else "white")
        ax_b.plot([], [], marker="o", ms=8, mew=2, color=color, mfc=color, lw=2, label=label)
    ax_b.plot([], [], marker="o", ms=8, mew=2, color=MUTED, mfc="white", lw=0,
              label="open: ensemble fails exactness ($|z| > 2.5$)")
    ax_b.set_xscale("log")
    ax_b.set_yscale("log")
    ax_b.set_xlabel(r"fine coupling $\beta_f$  (L = 32)")
    ax_b.set_ylabel("seconds per independent configuration")
    ax_b.set_title("(b) marginal cost where plain HMC\nno longer appears at all", fontsize=9)
    ax_b.legend(frameon=False, fontsize=8, loc="center left")

    # Two lines, fontsize trimmed from this file's usual 10.5: one line at
    # 6.9in canvas width overflows past both edges.
    fig.suptitle("Three-way verdict at L = 32: plain HMC freezes, instanton-HMC\n"
                 "pays an exploding entry cost (Fig. 18), diffusion stays flat", fontsize=9.5)
    fig.savefig(FIG_DIR / "26_three_way.png")
    plt.close(fig)


def _std_at(path, L, beta):
    for r in _load(path):
        if r["fine_L"] == L and abs(r["fine_beta"] - beta) < 1e-6:
            return r["log_weight_std_fiber"]
    return None


def fig_program_optimum():
    interventions = [
        ("v2 ckpt,\nladder knobs", OUT / "ode_reweighting" / "reweighting_results.json", MUTED, "kept as baseline"),
        ("+$\\sigma_{min}$ knob", OUT / "ode_reweighting_sweep" / "sigmin0.03" / "reweighting_results.json", GOOD_GREEN, "KEPT"),
        ("+ML fine-tune", OUT / "ess_chain" / "verify_mlft" / "reweighting_results.json", HMC_COLOR, "discarded"),
        ("+1-case rev-KL", OUT / "ess_chain" / "verify_rklft" / "reweighting_results.json", HMC_COLOR, "discarded"),
        ("multi-case rev-KL\n(rkl2)", OUT / "ess_chain" / "verify_rkl2" / "reweighting_results.json", GOOD_GREEN, "KEPT (final)"),
        ("big net + data", OUT / "ess_chain" / "verify_big_base" / "reweighting_results.json", HMC_COLOR, "discarded"),
    ]
    # Height held wider than a strict aspect-preserving rescale would give:
    # two-line panel titles, rotated tick labels, an inline text annotation
    # and a suptitle are all fixed-fontsize text that needs the same number
    # of INCHES regardless of the canvas's overall scale, so shrinking height
    # in step with width (as for a plain data plot) crushed them together.
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(6.9, 4.3), constrained_layout=True)
    for i, (label, path, color, note) in enumerate(interventions):
        std = _std_at(path, 16, 55.0237)
        ax_a.bar(i, std, color=color, width=0.7)
        ax_a.text(i, std * 1.04, f"{std:.1f}", ha="center", fontsize=8.5)
        ax_a.text(i, 1.25, note, ha="center", fontsize=7.5, rotation=90, color="white"
                  if color != MUTED else INK)
    ax_a.set_xticks(range(len(interventions)))
    ax_a.set_xticklabels([t[0] for t in interventions], fontsize=7.5, rotation=12)
    ax_a.set_yscale("log")
    ax_a.axhspan(1.0, 3.0, color=GOOD_GREEN, alpha=0.15)
    # Above the bars, not inside the band: bars run from the axis floor upward
    # and the verdict notes occupy the band itself, so anything placed at
    # band height is overdrawn. This is the only band of clear space.
    ax_a.set_ylim(bottom=0.62, top=340)
    ax_a.text((len(interventions) - 1) / 2, 190,
              "shaded: usable-certificate band (total spread O(1-3))",
              fontsize=8, color=GOOD_GREEN, ha="center", va="center", zorder=5)
    ax_a.set_ylabel("fiber log-weight std (L16, $\\beta$=55, fresh seeds)")
    # Derived like panel (b)'s range: the correction head is off-scale here, so
    # its penalty is quoted in the title, computed against the rkl2 checkpoint
    # on the disjoint grid it was judged on rather than written in by hand.
    corr = _load(OUT / "ess_chain" / "verify_correction" / "reweighting_results.json")
    ref = {}
    for src in ("frontier_rkl2", "verify_rkl2_extra"):
        for r in _load(OUT / "ess_chain" / src / "reweighting_results.json"):
            ref[(r["fine_L"], round(r["fine_beta"], 4))] = r["log_weight_std_fiber"]
    factors = [r["log_weight_std_fiber"] / ref[(r["fine_L"], round(r["fine_beta"], 4))]
               for r in corr if (r["fine_L"], round(r["fine_beta"], 4)) in ref]
    penalty = (f"({min(factors):.1f}-{max(factors):.1f}$\\times$ worse on its disjoint grid)"
               if factors else "(off scale on its disjoint grid)")
    ax_a.set_title("(a) every intervention, chronological; correction head\n"
                   f"{penalty} omitted for scale", fontsize=9.5)

    sources = [
        (OUT / "ess_chain" / "frontier_rkl2" / "reweighting_results.json", None),
        (OUT / "ess_chain" / "verify_rkl2" / "reweighting_results.json", None),
        (OUT / "ess_chain" / "verify_rkl2_extra" / "reweighting_results.json", None),
    ]
    markers = {8: "o", 16: "s", 32: "D"}
    seen = set()
    per_sites = []
    for path, _ in sources:
        for r in _load(path):
            key = (r["fine_L"], round(r["fine_beta"], 3))
            if key in seen:
                continue
            seen.add(key)
            per_site = r["log_weight_std_fiber"] / (2 * r["fine_L"] ** 2)
            per_sites.append(per_site)
            ax_b.plot([r["fine_beta"]], [per_site], marker=markers[r["fine_L"]],
                      ms=8, color=GEN_COLOR, mfc=GEN_COLOR, ls="none")
    for L, m in markers.items():
        ax_b.plot([], [], marker=m, ms=8, color=GEN_COLOR, ls="none", label=f"L = {L}")
    ax_b.axhline(0.005, color=GOOD_GREEN, lw=2, ls="--")
    ax_b.text(2.2, 0.0056, "certificate bar (~0.005 nats/site)", fontsize=8, color=GOOD_GREEN)
    ax_b.set_xscale("log")
    ax_b.set_yscale("log")
    ax_b.set_xlabel(r"fine coupling $\beta_f$")
    ax_b.set_ylabel("per-site density gap (nats), rkl2 checkpoint")
    # Derived, never hardcoded: this range moved from 4-10x to 3.7-12.5x when
    # the campaign was regenerated on GPU, and a literal in the title silently
    # outlived the data it described.
    lo, hi = min(per_sites) / 0.005, max(per_sites) / 0.005
    ax_b.set_title(f"(b) the quantified remainder: {lo:.1f}-{hi:.1f}$\\times$\n"
                   "above the bar, everywhere -- the program's endpoint", fontsize=7.3)
    ax_b.legend(frameon=False, fontsize=8, loc="upper left")

    fig.savefig(FIG_DIR / "27_program_optimum.png")
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig_three_way()
    fig_program_optimum()
    for name in ("26_three_way.png", "27_program_optimum.png"):
        print(f"wrote {FIG_DIR / name}")


if __name__ == "__main__":
    main()
