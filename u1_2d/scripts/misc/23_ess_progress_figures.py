"""Appendix figures for the ESS-gap program: exactness machinery, knob sweep,
fine-tune chain, and the multi-case reverse-KL result.

Reads existing result JSONs (no new simulation) and writes three figures into
out/u1_2d/paper_appendix/figures/.

    python u1_2d/scripts/23_ess_progress_figures.py
"""

import json
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
    "axes.axisbelow": True, "figure.dpi": 228,
})

CASES = [(16, 14.1464), (16, 55.0237), (32, 55.0237), (32, 218.58)]
CASE_LABELS = ["L16\n$\\beta$=14.1", "L16\n$\\beta$=55.0",
               "L32\n$\\beta$=55.0", "L32\n$\\beta$=218.6"]


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _by_case(path):
    out = {}
    for r in _load(path):
        out[(r["fine_L"], r["fine_beta"])] = r
    return out


def fig_progress():
    """Fiber log-weight spread per case for each checkpoint variant: absolute
    (left) and per site in nats (right). One valid-weight verification per
    variant (probability-flow ODE sampling, n = 64, fresh seeds)."""
    variants = [
        ("v2 checkpoint, ladder knobs", MUTED,
         _by_case(OUT / "ode_reweighting" / "reweighting_results.json")),
        ("+ ML fine-tune (negative)", HMC_COLOR,
         _by_case(OUT / "ess_chain" / "verify_mlft" / "reweighting_results.json")),
        ("+ single-case rev-KL (negative)", AMBER,
         _by_case(OUT / "ess_chain" / "verify_rklft" / "reweighting_results.json")),
        ("multi-case rev-KL (rkl2)", GEN_COLOR,
         _by_case(OUT / "ess_chain" / "verify_rkl2" / "reweighting_results.json")),
    ]
    knob_only = _load(OUT / "ode_reweighting_sweep" / "sigmin0.03" /
                      "reweighting_results.json")[0]

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(6.9, 2.76))
    xs = range(len(CASES))
    for label, color, rows in variants:
        stds = [rows[c]["log_weight_std_fiber"] for c in CASES]
        ax_a.plot(xs, stds, marker="o", ms=7, lw=2, color=color, label=label)
        ax_b.plot(xs, [s / (2 * c[0] ** 2) for s, c in zip(stds, CASES)],
                  marker="o", ms=7, lw=2, color=color)
    ax_a.plot([1], [knob_only["log_weight_std_fiber"]], marker="*", ms=15,
              color=GOOD_GREEN, ls="none",
              label="v2 ckpt, $\\sigma_{min}$-coef 0.03 (knob only)")
    ax_b.plot([1], [knob_only["log_weight_std_fiber"] / (2 * 16 ** 2)],
              marker="*", ms=15, color=GOOD_GREEN, ls="none")

    for ax, ylab, title in (
        (ax_a, "fiber log-weight std (total)", "absolute spread"),
        (ax_b, "fiber log-weight std per site (nats)", "per-site density gap"),
    ):
        ax.set_yscale("log")
        ax.set_xticks(list(xs))
        ax.set_xticklabels(CASE_LABELS)
        ax.set_ylabel(ylab)
        ax.set_title(title, fontsize=10)
    ax_a.annotate("2202: single-case training\nwrecks extrapolation",
                  xy=(3, 2202), xytext=(1.65, 700), fontsize=8, color=AMBER,
                  arrowprops={"arrowstyle": "->", "color": AMBER})
    ax_a.legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle("Valid importance-weight spread across couplings: "
                 "multi-case reverse-KL halves the density gap everywhere",
                 fontsize=10.5)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "23_ess_progress.png", bbox_inches="tight")
    plt.close(fig)


def fig_sweep():
    """Tier-0 proposal-knob sweep at L = 16, beta = 55: sampling-time knobs
    change the proposal density validly, so ESS can be tuned for free."""
    sweep_dir = OUT / "ode_reweighting_sweep"
    rows = []
    for d in sorted(sweep_dir.iterdir()):
        f = d / "reweighting_results.json"
        if f.is_file():
            rows.append((d.name, _load(f)[0]))
    rows.sort(key=lambda t: t[1]["log_weight_std_fiber"])

    fig, ax = plt.subplots(figsize=(6.9, 4.53))
    for i, (label, r) in enumerate(rows):
        if label == "sigmin0.03":
            color = GOOD_GREEN
        elif "blend" in label:
            color = HMC_COLOR
        elif label in ("probes8", "steps240"):
            color = "#c9c7c0"
        else:
            color = MUTED
        std = r["log_weight_std_fiber"]
        ax.barh(i, std, color=color, height=0.72)
        ax.text(std * 1.03, i, f"ESS/N {r['ess_per_n_fiber']:.3f}",
                va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([label for label, _ in rows], fontsize=8.5)
    ax.set_xscale("log")
    ax.set_xlim(right=max(r["log_weight_std_fiber"] for _, r in rows) * 2.2)
    ax.invert_yaxis()
    ax.set_xlabel("fiber log-weight std (L = 16, $\\beta_f$ = 55.02, n = 64)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in
               (GOOD_GREEN, HMC_COLOR, "#c9c7c0", MUTED)]
    ax.legend(handles, ["winner (lower terminal $\\sigma$ floor)",
                        "stronger exact-score blend (hurts)",
                        "estimator-stability controls", "other knobs"],
              frameon=False, fontsize=8, loc="upper right")
    ax.set_title("Proposal-family sweep: the spread is model density gap, not "
                 "estimator noise", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "24_proposal_sweep.png", dpi=152, bbox_inches="tight")
    plt.close(fig)


def fig_dynamics():
    """Fine-tune dynamics: (a) ML objective improves its own validation metric
    yet degrades deployment (the forward/reverse-KL asymmetry); (b) the guarded
    multi-case reverse-KL run -- saves happen only when the mean training-case
    ESS improves AND the never-trained extrapolation monitor stays sane."""
    mlft = _load(OUT / "checkpoints" / "score_net_mlft.history.json")
    rkl2 = _load(OUT / "checkpoints" / "score_net_rkl2.history.json")

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(6.9, 2.63))

    ml_pts = [(r["step"], r["val_logq_per_dof"]) for r in mlft if "val_logq_per_dof" in r]
    if not any(s == 0 for s, _ in ml_pts):
        # step-0 value predates in-history evals; printed by the trainer before
        # step 1 (ess_chain/chain.log)
        ml_pts.insert(0, (0, -0.8867))
    ml_steps, ml_vals = zip(*ml_pts)
    ax_a.plot(ml_steps, ml_vals, marker="o", ms=6, lw=2, color=GEN_COLOR)
    best_i = max(range(len(ml_vals)), key=lambda i: ml_vals[i])
    ax_a.plot([ml_steps[best_i]], [ml_vals[best_i]], marker="*", ms=16,
              color=GOOD_GREEN, zorder=4)
    ax_a.annotate("saved (best val)\n— still degrades deployed ESS",
                  xy=(ml_steps[best_i], ml_vals[best_i]),
                  xytext=(120, -0.72), fontsize=8,
                  arrowprops={"arrowstyle": "->", "color": INK})
    ax_a.set_xlabel("optimizer step")
    ax_a.set_ylabel("held-out log q / dof (data pairs)")
    ax_a.set_title("(a) ML fine-tune: validation likelihood is the wrong\n"
                   "selection metric for ESS (forward/reverse-KL asymmetry)",
                   fontsize=9.5)

    evs = [r for r in rkl2 if "mean_train_ess" in r]
    steps = [r["step"] for r in evs]

    def monitor_std(r):
        # current schema: plural `monitors` dict (worst monitor governs the
        # guard); legacy on-disk histories have the singular `monitor`.
        if "monitors" in r:
            return max(v["log_w_std"] for v in r["monitors"].values())
        return r["monitor"]["log_w_std"]

    ax_b.plot(steps, [r["mean_train_ess"] for r in evs], marker="o", ms=6,
              lw=2, color=GEN_COLOR, label="mean train-case ESS/N (rotating eval)")
    ax_b.set_xlabel("optimizer step")
    ax_b.set_ylabel("mean train-case ESS/N", color=GEN_COLOR)
    ax_b2 = ax_b.twinx()
    ax_b2.plot(steps, [monitor_std(r) for r in evs], marker="s",
               ms=5, lw=1.6, ls="--", color=HMC_COLOR,
               label="extrapolation monitor log-w std")
    # guard threshold = 1.5x the step-0 monitor std; taken from the history when
    # a step-0 eval exists, else the value the trainer printed before step 1
    # (ess_chain/rkl2.log)
    mon_init = monitor_std(evs[0]) if evs and evs[0].get("step") == 0 else 136.86
    ax_b2.axhline(1.5 * mon_init, color=HMC_COLOR, lw=1, ls=":", alpha=0.7)
    ax_b2.set_ylabel("monitor log-w std (L32, $\\beta$=218.6)", color=HMC_COLOR)
    ax_b2.grid(False)
    for r in evs:
        if r.get("saved"):
            ax_b.plot([r["step"]], [r["mean_train_ess"]], marker="*", ms=15,
                      color=GOOD_GREEN, zorder=4)
        if r.get("monitor_guard_blocked"):
            ax_b.plot([r["step"]], [r["mean_train_ess"]], marker="x", ms=11,
                      mew=2.5, color=HMC_COLOR, zorder=4)
    ax_b.plot([], [], marker="*", ms=12, color=GOOD_GREEN, ls="none", label="saved")
    ax_b.plot([], [], marker="x", ms=9, mew=2.5, color=HMC_COLOR, ls="none",
              label="save blocked by monitor guard")
    ax_b.legend(frameon=False, fontsize=8, loc="upper left")
    ax_b.set_title("(b) multi-case reverse-KL: guarded checkpointing\n"
                   "(dotted line = guard threshold, 1.5$\\times$ initial)",
                   fontsize=9.5)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "25_finetune_dynamics.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig_progress()
    fig_sweep()
    fig_dynamics()
    for name in ("23_ess_progress.png", "24_proposal_sweep.png",
                 "25_finetune_dynamics.png"):
        print(f"wrote {FIG_DIR / name}")


if __name__ == "__main__":
    main()
