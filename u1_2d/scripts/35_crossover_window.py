"""Where does the diffusion seed actually beat a working HMC chain?

The headline thermalization claim is a speedup, and a speedup only means
something while the baseline still finishes. Above the freezing coupling a
fresh HMC chain never thermalizes at all, so those rungs say "one method
finishes and the other does not" -- true, and a different claim. This splits
the scan into the three regimes and reports the speedup only where it is one:

  HMC healthy   -- fresh chains thermalize and Q tunnels; a ratio is honest
  Q frozen      -- fresh chains still thermalize, but Q never tunnels, so the
                   speedup is partly "HMC cannot do topology" rather than
                   "the seed is faster"
  HMC dead      -- fresh chains never thermalize inside the budget

("Crossover window" names the beta RANGE these regimes pass through, which is
what Part G was generated to fill; it is not a label for any one regime.)

    .venv/Scripts/python.exe u1_2d/scripts/35_crossover_window.py
"""

import argparse
import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WILSON = ("plaquette", "wilson_2x2", "wilson_4x4")


def slowest(summary: dict, start: str) -> float:
    return max(summary["t_therm"][start][n] for n in WILSON)


def regime(summary: dict) -> str:
    hot, cold = slowest(summary, "hot start"), slowest(summary, "cold start")
    if math.isinf(hot) and math.isinf(cold):
        return "HMC dead"
    if summary.get("q_freezing", {}).get("frozen"):
        return "Q frozen"
    return "HMC healthy"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="out/u1_2d/thermalization")
    ap.add_argument("--out", default="out/u1_2d/thermalization/crossover_window.json")
    args = ap.parse_args()

    rows = []
    for path in sorted(Path(REPO / args.dir).glob("*/*_summary.json")):
        s = json.loads(path.read_text(encoding="utf-8"))
        if "t_therm" not in s:
            continue
        seed = slowest(s, "diffusion seed")
        hot, cold = slowest(s, "hot start"), slowest(s, "cold start")
        best = min(hot, cold)
        # A seed that thermalizes instantly still costs the one trajectory it
        # takes to check, so the ratio is against max(seed, 1) -- otherwise a
        # t_therm of 0 reports an infinite speedup, which is an artifact of the
        # measurement grid rather than a result.
        ratio = best / max(seed, 1.0)
        rows.append({
            "L": s["lattice_size"], "beta": s["beta"], "regime": regime(s),
            "seed": seed, "hot": hot, "cold": cold,
            "interval": s.get("hmc_interval_trajectories"),
            "speedup": ratio, "q_frozen": bool(s.get("q_freezing", {}).get("frozen")),
            # seed == 0 means "already thermalized at the first measurement",
            # so the ratio is bounded by the measurement grid, not by the model.
            "speedup_is_bound": seed == 0,
        })
    rows.sort(key=lambda r: (r["L"], r["beta"]))
    if not rows:
        print(f"no summaries under {args.dir}")
        return

    def fmt(v):
        return "never" if math.isinf(v) else f"{v:.0f}"

    print(f"{len(rows)} rungs\n")
    print("| L | beta | regime | seed t_therm | hot | cold | 2 tau_int | speedup vs best HMC |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        if math.isinf(r["speedup"]):
            sp = "n/a (HMC never finishes)"
        else:
            sp = f"{'>=' if r['speedup_is_bound'] else ''}{r['speedup']:.1f}x"
        iv = f"{r['interval']:.0f}" if r["interval"] is not None else "--"
        print(f"| {r['L']} | {r['beta']:g} | {r['regime']} | {fmt(r['seed'])} | "
              f"{fmt(r['hot'])} | {fmt(r['cold'])} | {iv} | {sp} |")

    print()
    for name in ("HMC healthy", "Q frozen", "HMC dead"):
        sel = [r for r in rows if r["regime"] == name]
        if not sel:
            continue
        betas = [r["beta"] for r in sel]
        finite = [r["speedup"] for r in sel if math.isfinite(r["speedup"])]
        line = (f"{name:<12}: {len(sel):>2} rungs, beta {min(betas):g}-{max(betas):g}")
        if finite:
            line += (f", speedup {min(finite):.1f}-{max(finite):.1f}x "
                     f"(median {statistics.median(finite):.1f}x)")
        print(line)

    usable = [r for r in rows if r["regime"] != "HMC dead"]
    print(f"\nrungs where a speedup is even defined: {len(usable)} of {len(rows)}")
    healthy = [r for r in rows if r["regime"] == "HMC healthy"]
    if healthy:
        b = [r["beta"] for r in healthy]
        print(f"fully-healthy HMC band: beta {min(b):g}-{max(b):g} ({len(healthy)} rungs)")

    out = REPO / args.out
    out.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
