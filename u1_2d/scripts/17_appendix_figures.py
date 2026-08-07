"""Paper-appendix figures for the head-to-head, burn-in scan, and ESS results.

Reads the campaign summaries (no new simulation) and writes three figures into
out/u1_2d/paper_appendix/figures/.

    python u1_2d/scripts/17_appendix_figures.py
"""

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path("out/u1_2d")
FIG_DIR = OUT / "paper_appendix" / "figures"

GEN_COLOR = "#2a78d6"
HMC_COLOR = "#d64550"

# One-time cost of the campaign that produced the deployed checkpoint. The
# head-to-head charges the instanton-HMC arm its burn-in, so the diffusion arm
# must be charged its own entry cost or Fig 18 compares a one-time cost against
# a marginal one.
#
# RTX 5060 Laptop + Ryzen 7 260 (2026-08-06), replacing the Snapdragon numbers
# (21.7 / 125.3 min). Data is the measured sentinel: 3.2 min, 8 single-threaded
# shards. Training is NOT its sentinel (188.9 min) -- that run was interrupted by
# Modern Standby, so its wall clock counts sleep as compute. The figure needs
# compute cost, so this is the measured rate instead: 100 epochs x 728 steps at
# the observed 45 s/epoch.
CAMPAIGN_DATA_SECONDS = 3.2 * 60.0
CAMPAIGN_TRAIN_SECONDS = 100 * 45.0
CAMPAIGN_ONE_TIME_SECONDS = CAMPAIGN_DATA_SECONDS + CAMPAIGN_TRAIN_SECONDS
# 38 study cases x 128 configs: what the single checkpoint actually served.
STUDY_CONFIGS_GENERATED = 38 * 128
INK = "#0b0b0b"
GRID_COLOR = "#e1e0d9"
MUTED = "#8f8d86"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": INK, "axes.labelcolor": INK,
    "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.grid": True, "grid.color": GRID_COLOR, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "figure.dpi": 150,
})


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _quality_ok(arm, threshold=2.5):
    zs = [abs(arm.get(f"{n}_z", float("nan")))
          for n in ("plaquette", "wilson_2x2", "wilson_4x4", "Q^2")]
    zs = [z for z in zs if math.isfinite(z)]
    return bool(zs) and max(zs) <= threshold


def fig_headtohead_cost():
    """Seconds per independent config vs beta, both arms, quality encoded by
    marker fill (secondary encoding on top of color)."""
    # One consistent snapshot (burn-in 500, 128 configs) so per-config costs are
    # comparable across beta -- mixing in the 512-config highstats run would make
    # the diffusion cost look beta-dependent when the change is batch size.
    rows = {rec["beta"]: rec for rec in _load(OUT / "diffusion_vs_instanton" / "summary.json")}
    betas = sorted(rows)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for arm_key, color, label in (("instanton_hmc", HMC_COLOR, "instanton HMC (marginal, 2$\\tau_{int}$)"),
                                  ("diffusion", GEN_COLOR, "diffusion (batch-amortized)")):
        xs, ys, oks = [], [], []
        for b in betas:
            arm = rows[b][arm_key]
            xs.append(b)
            ys.append(arm["seconds_per_independent_config"])
            oks.append(_quality_ok(arm))
        ax.plot(xs, ys, color=color, lw=2, zorder=2)
        for x, y, ok in zip(xs, ys, oks):
            ax.plot([x], [y], marker="o", ms=9, mew=2, color=color,
                    mfc=color if ok else "white", zorder=3)
        ax.plot([], [], marker="o", ms=9, mew=2, color=color, mfc=color, lw=2, label=label)
    ax.plot([], [], marker="o", ms=9, mew=2, color=MUTED, mfc="white", lw=0,
            label="open marker: fails exactness ($|z| > 2.5$)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"fine coupling $\beta_f$  (L = 32)")
    ax.set_ylabel("seconds per independent configuration")
    ax.legend(frameon=False, fontsize=9, loc="center left")
    ax.set_title("Marginal cost per configuration: filled = exact-agreeing ensemble", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "17_headtohead_cost.png", bbox_inches="tight")
    plt.close(fig)


def fig_entry_cost():
    """One-time entry cost (burn-in seconds until the ensemble passes) vs beta,
    against the diffusion pipeline's flat per-config cost."""
    scan = _load(OUT / "diffusion_vs_instanton" / "burnin_scan" / "summary.json")
    base = _load(OUT / "diffusion_vs_instanton" / "summary.json")
    points = {}
    for rec in base:
        a = rec["instanton_hmc"]
        zs = [abs(a.get(f"{n}_z", float("nan")))
              for n in ("plaquette", "wilson_2x2", "wilson_4x4")]
        zs = [z for z in zs if math.isfinite(z)]
        points.setdefault(rec["beta"], []).append(
            (500, a["burn_seconds"], max(zs) if zs else float("nan")))
    for rec in scan:
        points.setdefault(rec["beta"], []).append(
            (rec["burn_in"], rec["burn_seconds"], rec["max_wilson_abs_z"]))
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    pass_x, pass_y, fail_last = [], [], None
    for beta in sorted(points):
        trials = sorted(points[beta])
        passing = [(s, z) for _, s, z in trials if math.isfinite(z) and z <= 2.5]
        if passing:
            pass_x.append(beta)
            pass_y.append(passing[0][0])
        else:
            fail_last = (beta, max(s for _, s, _ in trials))
    ax.plot(pass_x, pass_y, marker="o", ms=9, mew=2, color=HMC_COLOR, lw=2,
            label="instanton HMC: burn-in until exact-agreeing (one-time)")
    if fail_last is not None:
        b, s = fail_last
        ax.annotate("never passes\n(> 2500 s tested)", xy=(b, s), xytext=(b * 0.42, s * 5),
                    fontsize=9, color=HMC_COLOR,
                    arrowprops=dict(arrowstyle="->", color=HMC_COLOR))
        ax.plot([b], [s], marker="^", ms=10, color=HMC_COLOR, mfc="white", mew=2)
    diff_costs = []
    for rec in base:
        diff_costs.append((rec["beta"], rec["diffusion"]["seconds_per_independent_config"]))
    xs, ys = zip(*sorted(diff_costs))
    ax.plot(xs, ys, marker="o", ms=9, mew=2, color=GEN_COLOR, lw=2,
            label="diffusion: marginal cost per config (flat)")
    ax.axhline(CAMPAIGN_ONE_TIME_SECONDS, color=GEN_COLOR, lw=2, ls="--", alpha=0.85)
    ax.text(
        xs[0] * 1.02, CAMPAIGN_ONE_TIME_SECONDS * 0.30,
        f"diffusion one-time entry cost: {CAMPAIGN_ONE_TIME_SECONDS/60:.0f} min\n"
        f"(data {CAMPAIGN_DATA_SECONDS/60:.1f} + training {CAMPAIGN_TRAIN_SECONDS/60:.1f} min),\n"
        "paid once for all 38 cases",
        fontsize=8, color=GEN_COLOR, va="top", ha="left",
    )
    amortized = [y + CAMPAIGN_ONE_TIME_SECONDS / STUDY_CONFIGS_GENERATED for y in ys]
    ax.plot(xs, amortized, marker="s", ms=6, color=GEN_COLOR, lw=1.5, ls=":", alpha=0.9,
            label=(f"diffusion: amortized ({CAMPAIGN_ONE_TIME_SECONDS/STUDY_CONFIGS_GENERATED:.1f} s/config "
                   "campaign share added)"))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"fine coupling $\beta_f$  (L = 32)")
    ax.set_ylabel("seconds")
    ax.set_ylim(top=CAMPAIGN_ONE_TIME_SECONDS * 4.0)
    ax.legend(frameon=True, framealpha=0.92, edgecolor="none", fontsize=8, loc="center left")
    ax.set_title(
        "The competitor's entry cost diverges with $\\beta$; the generative cost is a\n"
        "fixed one-time charge plus a flat marginal cost", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "18_entry_cost.png", bbox_inches="tight")
    plt.close(fig)


def fig_ess_weights():
    """Importance-weight log-spread vs degrees of freedom: the honest negative.
    Guidance on/off overlap -> the gap is the model's own density mismatch."""
    with_g = _load(OUT / "model_ess" / "ess_results.json")
    no_g = _load(OUT / "model_ess_noguide" / "ess_results.json")

    def per_site(recs):
        out = {}
        for r in recs:
            key = (r["fine_L"], r["fine_beta"])
            std = r.get("log_weight_std_fiber", r["log_weight_std"])
            out[key] = std / (2 * r["fine_L"] ** 2)
        return out

    on, off = per_site(with_g), per_site(no_g)
    cases = sorted(set(on) & set(off))
    labels = [f"L={L}\n$\\beta$={b:g}" for L, b in cases]
    xs = range(len(cases))
    width = 0.38
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.bar([x - width / 2 for x in xs], [on[c] for c in cases], width,
           color=GEN_COLOR, label="guidance on (production sampler)")
    ax.bar([x + width / 2 for x in xs], [off[c] for c in cases], width,
           color="#7a5cc9", label="guidance off")
    for x, c in zip(xs, cases):
        ax.annotate(f"{on[c]:.3f}", xy=(x - width / 2, on[c]), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8, color=INK)
        ax.annotate(f"{off[c]:.3f}", xy=(x + width / 2, off[c]), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8, color=INK)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(labels)
    ax.set_ylabel("importance-weight spread per site\n" +
                  r"std$(\log w)\,/\,2L^2$  [nats],  $w = e^{-S}/q$")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("A small per-site density mismatch, multiplied by volume,\n"
                 "collapses ESS/N to 1/N -- with or without guidance", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "19_ess_weights.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig_headtohead_cost()
    fig_entry_cost()
    fig_ess_weights()
    for f in ("17_headtohead_cost", "18_entry_cost", "19_ess_weights"):
        print("wrote", FIG_DIR / f"{f}.png")


if __name__ == "__main__":
    main()
