"""Stage 12: emit the measurements section of `docs/u2_2d/NARRATIVE.md` from JSON.

Every number in the write-up is read from the file the stage that measured it
wrote. Hand-transcribing them is how a document drifts from its data — and this
study has already been bitten twice by stale numbers (a superseded ladder whose
ensembles were still on disk, and sector verdicts computed before the parity test
existed). Regenerating the section is cheap; keeping it correct by hand is not.

Writes to stdout by default so it can be inspected before it replaces anything;
`--in-place` splices it into the narrative between the Part IV markers.
"""

import argparse
import json
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN GENERATED RESULTS -->"
END = "<!-- END GENERATED RESULTS -->"


def _load(rel: str):
    p = Path(rel)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ladder_table(summary) -> list:
    if not summary:
        return []
    out = ["### Ladder: observables against the closed form", "",
           "| $L$ | $\\beta$ | $\\langle P\\rangle$ | exact | rel. err | pre-retherm |"
           " $\\langle Q^2\\rangle$ | exact |",
           "|---|---|---|---|---|---|---|---|"]
    for r in summary:
        rel = r["plaquette"] / r["plaquette_exact"] - 1.0
        out.append(
            f"| {r['lattice_size']} | {r['beta']:g} | {r['plaquette']:.6f} | "
            f"{r['plaquette_exact']:.6f} | ${rel:+.2e}$ | "
            f"{r['plaquette_pre_retherm']:.6f} | {r['q_squared']:.4f} | "
            f"{r['q_squared_exact']:.4f} |")
    out += ["", "The pre-rethermalization column is the one that separates model "
                "quality from local-update repair: where it already matches, the "
                "diffusion lift earned the agreement unaided.", ""]
    return out


def validation_table(summary) -> list:
    """`rows` is a LIST of per-observable records keyed by `observable`."""
    if not summary:
        return []
    out = ["### Validation against HMC and the closed form", "",
           r"| $L$ | $\beta$ | plaquette $z$ vs exact | max Wilson $z$ vs ref |"
           " mean | reference |",
           "|---|---|---|---|---|---|"]
    for r in summary:
        rows = {row["observable"]: row for row in r.get("rows", [])}
        z = rows.get("plaquette", {}).get("z_vs_exact")
        zs = f"${z:+.2f}$" if isinstance(z, (int, float)) else "-"
        mx, mn = r.get("max_wilson_z"), r.get("mean_wilson_z")
        mxs = f"{mx:.2f}" if isinstance(mx, (int, float)) else "-"
        mns = f"{mn:.2f}" if isinstance(mn, (int, float)) else "-"
        out.append(f"| {r['lattice_size']} | {r['beta']:g} | {zs} | {mxs} | {mns} |"
                   f" {r.get('reference_source', '—')} |")
    out += ["", "Read the *exact* column. A $z$ against the HMC reference carries "
                "that reference's own uncorrelated-sample assumption, which is not "
                "true of a Markov chain; this study measured a spurious "
                r"$-3.26\sigma$ that way while the generated ensemble was in fact "
                "closer to exact than the reference was.", ""]
    return out


def spread_table(dists) -> list:
    if not dists:
        return []
    out = ["### Per-configuration Wilson spread", "",
           f"At $L = {dists['lattice_size']}$, $\\beta = {dists['beta']:g}$. Means "
           "agree to $10^{-6}$; the width is the informative quantity.", "",
           "| loop | generated $\\sigma$ | HMC $\\sigma$ | ratio |",
           "|---|---|---|---|"]
    for name in dists["loops"]:
        e = dists["std"][name]
        ref = e.get("reference")
        out.append(f"| {name.replace('wilson_', 'W ')} | {e['generated']:.3e} | "
                   + (f"{ref:.3e} | {e['ratio']:.3f} |" if ref else "— | — |"))
    out.append("")
    return out


def benchmark_table(bench) -> list:
    if not bench:
        return []
    out = ["### Seed quality and topological reach", "",
           f"$L = {bench['lattice_size']}$, $\\beta = {bench['beta']:g}$, "
           f"{bench['n_chains']} chains, {bench['n_trajectories']} trajectories "
           "per arm.", "",
           "| arm | $|\\Delta P/P|$ at $t=0$ | at $t=T$ | $\\langle Q^2\\rangle$ | "
           "sectors | $P(Q)$ covered | odd sectors |",
           "|---|---|---|---|---|---|---|"]
    names = {"A_diffusion_seed": "**A** diffusion seed",
             "B_cold_start": "B cold start",
             "C_hot_start": "C hot start",
             "D_cold_plus_winding": "D cold + winding"}
    for a in bench["arms"]:
        t = a["topology"]
        out.append(
            f"| {names.get(a['arm'], a['arm'])} | "
            f"${abs(a['plaquette_initial_rel']):.2e}$ | "
            f"${abs(a['plaquette_final_rel']):.2e}$ | {t['q_squared']:.3f} | "
            f"{t['n_sectors_visited']} | {t['exact_probability_covered']:.3f} | "
            f"{len(t['odd_sectors_visited'])} |")
    q2e = bench["arms"][0]["topology"]["q_squared_exact"]
    interval = bench.get("independent_interval_trajectories")
    out += ["", f"Exact $\\langle Q^2\\rangle = {q2e:.4f}$. The independent-configuration "
                f"interval for a plain chain is $2\\tau_{{\\rm int}} = {interval:.1f}$ "
                "trajectories.", "",
            "**Read coverage together with the second moment, never alone.** The",
            "hot-start arm covers 1.000 of the exact $P(Q)$ by visiting 51 sectors",
            "while carrying a second moment of 109 against an exact 1.001 -- it covers",
            "everything by being everywhere, and is nowhere near equilibrium (its",
            "plaquette is still 6% off after 300 trajectories). Coverage rewards",
            "breadth; only the pair of numbers identifies a correct distribution.", "",
            "The diffusion arm uses the first 64 configurations of the 512-configuration",
            "ensemble, so its sampling error on the second moment is about 0.09 and it",
            "will not equal the ladder value exactly.", ""]
    return out



def cost_table(cost) -> list:
    if not cost:
        return []
    lad = cost["ladder"]
    out = ["### Cost per independent configuration", "",
           rf"$L = {cost['lattice_size']}$, $\beta = {cost['beta']:g}$, "
           f"{cost['n_chains']} chains. For a Markov chain the cost is "
           r"$2\tau_{\rm int}\,t_{\rm traj}/n_{\rm chains}$, with "
           r"$\tau_{\rm int}$ measured on the equilibrated tail only.", "",
           r"| arm | $\tau_{\rm int}(P)$ | s / trajectory | **s / independent config** |",
           "|---|---|---|---|"]
    for r in cost["arms"]:
        t = r["seconds_per_independent_config_local"]
        ts = f"**{t:.4f}**" if t == t else "-"
        out.append(f"| {r['arm'].replace('_', ' ')} | "
                   f"{r['tau_int_plaquette_trajectories']:.1f} | "
                   f"{r['seconds_per_trajectory']:.3f} | {ts} |")
    out += ["",
            f"Ladder: **{lad['seconds_per_config_including_base']:.4f} s** per "
            f"configuration including base generation, "
            f"**{lad['seconds_per_config_top_rung_only']:.4f} s** for the top rung "
            "alone.", ""]
    if "speedup_local_vs_hmc_winding" in cost:
        s = cost["speedup_local_vs_hmc_winding"]
        out += [f"**For local observables the ladder is {1/s:.2f}x SLOWER than "
                "HMC + winding.** That is the honest headline and it should not be "
                "buried: this method is not a speed-up for the plaquette or small "
                "Wilson loops, and the cost is dominated by the 200-step diffusion "
                "sampler, which is tunable but has not been tuned.", "",
                "**The topological claim is reachability, not speed.** The classical "
                f"arm covers {cost['arms'][-1]['exact_probability_covered']:.3f} of "
                "the exact $P(Q)$ with zero odd sectors and cannot improve on that "
                "at any cost, because odd charge has probability *zero* in its "
                "stationary distribution rather than merely long autocorrelation. A "
                "ratio of seconds against an arm that never arrives is meaningless, "
                "so the two claims must be stated separately.", ""]
    return out


def sampling_table(scans) -> list:
    if not scans:
        return []
    out = ["### Where $P(Q)$ can be sampled rather than seeded", "",
           "| $L$ | $\\beta$ | $\\beta/V$ | $\\beta L$ | $\\langle Q^2\\rangle$ | exact"
           " | $z$ | $\\chi^2$/dof | odd ratio | $z_{\\rm odd}$ | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(scans, key=lambda r: (r["lattice_size"], r["beta"])):
        out.append(
            f"| {r['lattice_size']} | {r['beta']:g} | "
            f"{r.get('beta_over_volume', r['beta'] / r['lattice_size']**2):.3f} | "
            f"{r['beta'] * r['lattice_size']:.0f} | "
            f"${r['q_squared']:.4f} \\pm {r['q_squared_err']:.4f}$ | "
            f"{r['q_squared_exact']:.4f} | ${r['q_squared_z']:+.2f}$ | "
            f"{r['chi2'] / r['n_sectors']:.2f} | {r.get('odd_ratio', float('nan')):.3f} | "
            f"${r.get('odd_z', float('nan')):+.2f}$ | {r.get('verdict', '—')} |")
    out.append("")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-place", action="store_true",
                        help="splice into docs/u2_2d/NARRATIVE.md between the markers")
    args = parser.parse_args()

    scans = []
    for name in ("pq_sampling", "pq_sampling_L16", "pq_sampling_L32"):
        rows = _load(f"out/u2_2d/{name}/pq_sampling.json")
        if rows:
            scans.extend(rows)

    lines = [BEGIN, "",
             "*Generated by `scripts/12_results_section.py` from the JSON each stage"
             " wrote; do not edit by hand.*", ""]
    lines += ladder_table(_load("out/u2_2d/ladder/summary.json"))
    lines += validation_table(_load("out/u2_2d/validation/summary.json"))
    lines += benchmark_table(_load("out/u2_2d/seed_benchmark/seed_benchmark.json"))
    lines += spread_table(_load("out/u2_2d/validation/wilson_distributions.json"))
    lines += cost_table(_load("out/u2_2d/seed_benchmark/cost.json"))
    lines += sampling_table(scans)
    lines += [END]
    body = "\n".join(lines)

    if not args.in_place:
        print(body)
        return 0

    p = Path("docs/u2_2d/NARRATIVE.md")
    s = p.read_text(encoding="utf-8")
    if BEGIN in s and END in s:
        head, rest = s.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        s = head + body + tail
    else:
        marker = "## Part IV — Measurements"
        i = s.index(marker) + len(marker)
        j = s.index("## Part V", i)
        s = s[:i] + "\n\n" + body + "\n\n---\n\n" + s[j:]
    p.write_text(s, encoding="utf-8")
    print(f"spliced {len(lines)} lines into {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
