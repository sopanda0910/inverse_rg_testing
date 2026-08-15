"""The central result, in one figure: observables agree, the density does not.

Every number for this claim already exists, but split across Table S2, Table
S5, Fig. 23 and Fig. 27b, so a reader has to assemble the comparison. The
claim only bites when the two halves sit side by side on the same ensembles:

  (a) every gauge-invariant observable matches the exact character-expansion
      value within its error bar -- mean |z| below the 0.798 a correct sampler
      would give, zero outliers past |z| = 3;
  (b) the per-configuration log weights from the same model spread over
      hundreds of nats, i.e. the density those observables came from is far
      from the target.

The moral is the reporting protocol: observable agreement does not bound the
density, so a sampler validated only on observables is not validated.

Both panels are the DEPLOYED checkpoint (`score_net.pt`), which is what makes
them comparable -- panel (a) is its pipeline validation and panel (b) is its
own ESS probes. The per-site spread here (0.030-0.091 nats/site) is therefore
larger than the 0.018-0.062 quoted for Fig. 27b, which is the rkl2
likelihood-work checkpoint. Different models, not a discrepancy; do not mix
the two ranges.

    .venv/Scripts/python.exe u1_2d/scripts/36_dissociation_figure.py
"""

import json
import math
import re
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.lines as mlines
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "out" / "u1_2d"
INK = "#1a1a1a"
GRID = "#d8d8d8"
GEN = "#2f6fb2"
BAD = "#c1443c"
MUTED = "#8a8a8a"
IDEAL = math.sqrt(2 / math.pi)
USABLE_NATS = 3.0  # log-weight spread at which SNIS weights stay usable


def parse_validation(path: Path) -> dict[str, list[float]]:
    """z_exact per rung from a validation report, enforced rungs only."""
    text = path.read_text(encoding="utf-8")
    out = {}
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        head = head.strip()
        if head.endswith("_RAW_preenforcement"):
            continue
        zs = []
        for line in body.splitlines():
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 5 or cells[0] == "observable":
                continue
            try:
                z = float(cells[4])
            except ValueError:
                continue
            if math.isfinite(z):
                zs.append(z)
        if zs:
            out[head] = zs
    return out


def load_weights() -> list[dict]:
    rows = []
    for path in sorted(OUT.rglob("ess_results.json")):
        for c in json.loads(path.read_text(encoding="utf-8")):
            if not isinstance(c, dict) or "log_weight_std" not in c:
                continue
            rows.append({
                "L": c["fine_L"], "beta": c["fine_beta"],
                "std": c["log_weight_std"], "n": c.get("n"),
                "weights": c.get("log_weights") or [],
                "src": path.parent.name,
            })
    # One row per case, preferring the largest n available.
    best = {}
    for r in rows:
        key = (r["L"], round(r["beta"], 3))
        if key not in best or (r["n"] or 0) > (best[key]["n"] or 0):
            best[key] = r
    return [best[k] for k in sorted(best)]


def main() -> None:
    rungs = parse_validation(OUT / "validation" / "report.md")
    cases = load_weights()
    if not rungs or not cases:
        raise SystemExit("need out/u1_2d/validation/report.md and an ess_results.json")

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(11.4, 4.5))

    # (a) observables
    labels, allz = [], []
    for name, zs in rungs.items():
        m = re.search(r"L(\d+)_beta([\d.]+)", name)
        labels.append(f"L={m.group(1)}\nβ={float(m.group(2)):g}" if m else name)
        allz.append(zs)
    for i, zs in enumerate(allz):
        x = [i + (j - len(zs) / 2) * 0.012 for j in range(len(zs))]
        ax_a.plot(x, [abs(z) for z in zs], "o", ms=4, color=GEN, alpha=0.65,
                  mec="none")
    flat = [abs(z) for zs in allz for z in zs]
    ax_a.axhline(IDEAL, color=INK, lw=1.2, ls="--")
    ax_a.text(0.985, IDEAL, f" ideal mean |z| = {IDEAL:.2f} ", ha="right",
              va="bottom", fontsize=8, color=INK, transform=ax_a.get_yaxis_transform(),
              bbox=dict(fc="white", ec="none", pad=1.0))
    ax_a.axhline(3.0, color=BAD, lw=1.0, ls=":")
    ax_a.text(0.985, 3.0, " |z| = 3 (outlier bar) ", ha="right", va="bottom",
              fontsize=8, color=BAD, transform=ax_a.get_yaxis_transform(),
              bbox=dict(fc="white", ec="none", pad=1.0))
    ax_a.set_xticks(range(len(labels)))
    ax_a.set_xticklabels(labels, fontsize=8.5)
    ax_a.set_ylabel("|z| vs exact character expansion", fontsize=9.5)
    ax_a.set_ylim(0, max(3.6, max(flat) * 1.15))
    n_out = sum(1 for z in flat if z > 3)
    ax_a.set_title(f"(a) every observable agrees\n"
                   f"mean |z| = {statistics.fmean(flat):.2f}, "
                   f"{n_out} of {len(flat)} past |z| = 3",
                   fontsize=10, color=INK)

    # (b) the density those same observables came from
    for r in cases:
        ax_b.plot([r["beta"]], [r["std"]], "o", ms=8, color=BAD, mec="none")
        ax_b.annotate(f"L={r['L']}", (r["beta"], r["std"]), xytext=(6, -3),
                      textcoords="offset points", fontsize=7.5, color=MUTED)
    ax_b.axhspan(0.5, USABLE_NATS, color=GEN, alpha=0.13)
    ax_b.text(0.02, USABLE_NATS, f" usable weights (spread ≲ {USABLE_NATS:.0f} nats) ",
              ha="left", va="bottom", fontsize=8, color=GEN,
              transform=ax_b.get_yaxis_transform())
    ax_b.set_xscale("log")
    ax_b.set_yscale("log")
    ax_b.set_ylim(0.5, max(r["std"] for r in cases) * 2.2)
    ax_b.xaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax_b.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax_b.set_xticks([r["beta"] for r in cases])
    ax_b.set_xlabel(r"fine coupling $\beta_f$", fontsize=9.5)
    ax_b.set_ylabel("log-weight spread (nats/config)", fontsize=9.5)
    stds = [r["std"] for r in cases]
    per_site = [r["std"] / (2 * r["L"] ** 2) for r in cases]
    ax_b.set_title(f"(b) the density does not\n"
                   f"same ensembles: {min(stds):.0f}–{max(stds):.0f} nats/config "
                   f"({min(per_site):.3f}–{max(per_site):.3f} nats/site), "
                   f"{min(stds) / USABLE_NATS:.0f}–{max(stds) / USABLE_NATS:.0f}× "
                   f"above usable", fontsize=10, color=INK)

    for ax in (ax_a, ax_b):
        ax.grid(color=GRID, lw=0.7)
        ax.set_axisbelow(True)
        for s in ax.spines.values():
            s.set_color(GRID)
        ax.tick_params(labelsize=8)

    handles = [
        mlines.Line2D([], [], color=GEN, marker="o", ls="none",
                      label="one gauge-invariant observable"),
        mlines.Line2D([], [], color=BAD, marker="o", ls="none",
                      label="one (L, β) case, fiber log-weight spread"),
    ]
    fig.legend(handles=handles, fontsize=8.5, frameon=False, loc="lower center",
               bbox_to_anchor=(0.5, -0.02), ncol=2)
    fig.suptitle("Observable agreement does not bound the density",
                 fontsize=12.5, color=INK)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    dest = OUT / "paper_appendix" / "dissociation.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(dest, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"observables: mean |z| = {statistics.fmean(flat):.3f} "
          f"(ideal {IDEAL:.3f}), {n_out}/{len(flat)} past |z|=3")
    print(f"density:     {min(stds):.1f}-{max(stds):.1f} nats over {len(cases)} cases")
    print(f"wrote {dest.relative_to(REPO)}")


if __name__ == "__main__":
    main()
