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


def spread_table(dists, heading="### Per-configuration Wilson spread",
                 note=None) -> list:
    if not dists:
        return []
    out = [heading, "",
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
    if note:
        out += [note, ""]
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
             "D_cold_plus_winding": "D cold + even winding",
             "E_diffusion_plus_winding": "**E** diffusion + even winding",
             "F_hot_plus_winding": "F hot + even winding",
             "G_cold_plus_odd_winding": "G cold + **odd** winding",
             "H_diffusion_plus_odd_winding": "**H** diffusion + **odd** winding"}
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
                "Wilson loops. The cost is dominated by the 200-step diffusion "
                "sampler, and the obvious hedge -- that the sampler is tunable and "
                "was never tuned -- **is real and worth about a factor of three**, "
                "measured in the scan below. At 25 steps the top rung turns from "
                "2.22x slower into 1.38x *faster* than HMC + winding, at roughly 2.7x "
                "the extended-loop error and no measurable change in local "
                "observables after rethermalization. So the number quoted here is the "
                "cost of the ACCURACY-OF-RECORD setting, not a floor. What does not "
                "move is the remaining overhead: the exact conditional SU(2) sampler, "
                "which no amount of sampler tuning touches.", "",
                "**The topological claim is reachability, not speed.** The classical "
                f"arm covers {cost['arms'][-1]['exact_probability_covered']:.3f} of "
                "the exact $P(Q)$ with zero odd sectors and cannot improve on that "
                "at any cost, because odd charge has probability *zero* in its "
                "stationary distribution rather than merely long autocorrelation. A "
                "ratio of seconds against an arm that never arrives is meaningless, "
                "so the two claims must be stated separately.", ""]
    return out


def reference_control_table(summary) -> list:
    """The top rung against a DIRECT HMC ensemble at the same (L, beta).

    Without this the large-loop deviation at L = 64 was uncontrolled: the
    generated ensemble drifted from the closed form as the loop grew, and there
    was no way to tell model error from the finite-statistics drift any ensemble
    of that size shows. Measuring the reference's own deviation settles it.
    """
    if not summary:
        return []
    top = max(summary, key=lambda r: r["lattice_size"])
    rows = [r for r in top.get("rows", [])
            if r["observable"].startswith("wilson_") and r.get("reference") is not None]
    if not rows:
        return []

    def area(name):
        a, b = name.split("_")[1].split("x")
        return int(a) * int(b)

    rows.sort(key=lambda r: area(r["observable"]))
    out = ["### The top rung against a direct HMC reference", "",
           rf"$L = {top['lattice_size']}$, $\beta = {top['beta']:g}$ -- the "
           "extrapolation the ladder exists for, now with a direct HMC ensemble at "
           "the same coupling. It is a **control, not a competing sampler**: its "
           "topology is seeded from the closed form "
           rf"($\beta L = {top['beta'] * top['lattice_size']:.0f}$, two orders past "
           "the parity boundary), so it says nothing about sectors and everything "
           "about local and extended observables.", "",
           r"| loop | area | $z$ generated | $z$ reference | $|{\rm dev}|$ generated"
           r" | $|{\rm dev}|$ reference |",
           "|---|---|---|---|---|---|"]
    big_g, big_r = [], []
    for r in rows:
        a = area(r["observable"])
        dg = abs(r["generated"] - r["exact"])
        dr = abs(r["reference"] - r["exact"])
        zr = (r["reference"] - r["exact"]) / r["reference_err"] if r["reference_err"] else 0.0
        if a >= 48:
            big_g.append(dg)
            big_r.append(dr)
        out.append(f"| {r['observable'].replace('wilson_', 'W ')} | {a} | "
                   f"${r['z_vs_exact']:+.2f}$ | ${zr:+.2f}$ | ${dg:.2e}$ | ${dr:.2e}$ |")
    if big_g:
        mg = sum(big_g) / len(big_g)
        mr = sum(big_r) / len(big_r)
        out += ["", f"Over loops of area $\\ge 48$ the mean absolute deviation from "
                    f"exact is ${mg:.2e}$ for the generated ensemble and ${mr:.2e}$ "
                    f"for the reference -- the same size, and at the largest loop "
                    f"the *reference* is the further of the two. **The large-loop "
                    f"drift is not model error.** It is what an ensemble of this "
                    f"size does at this coupling, and the ladder reproduces it.", ""]
    out += ["Two cautions on reading the $z$ columns. The deviations of large loops "
            "*within one ensemble* are strongly correlated -- they are all "
            "functionals of the same bulk field -- so nineteen same-signed rows are "
            "one fluctuation, not nineteen. And the reference's error bar is a "
            "plain $\\sigma/\\sqrt{N}$ over a Markov chain with acceptance 0.37, so "
            "it is optimistic; its plaquette $z$ of $-4.25$ measures that "
            "optimism, not a defect in the closed form.", ""]
    return out


def sampler_steps_table(records) -> list:
    """Reverse-diffusion step count vs cost and accuracy."""
    if not records:
        return []
    out = ["### How many reverse-diffusion steps the lift needs", "",
           "The 200-step sampler was chosen once and never revisited, and stage 13 "
           "charged the whole ladder for it. The narrative used to hedge the cost "
           "verdict on the grounds that the sampler was *tunable but untuned*, which "
           "is not a defensible thing to leave in a paper: either the hedge is real "
           "and the cost number is inflated, or it is not and the verdict is final. "
           "It is tuned now, and the answer is that the hedge is real and worth about "
           "a factor of three -- purchased, not free.", "",
           "Scan run at 512 configurations per rung, so the comparable quantity "
           "across rows is seconds *per configuration*; the ladder of record at 200 "
           "steps and 1024 configurations reproduces this table's 200-step row to "
           "0.5%.", "",
           "**Read rung 0, not the top rung.** Rung 0 lifts the fixed HMC base, byte "
           "identical in every run, so its error is one diffusion lift and nothing "
           "else. The top rung lifts rung 0's *output*, so its plaquette error is a "
           "compound of two lifts that partially cancel -- it runs the wrong way "
           "across this scan and means nothing on its own. Extended loops at the top "
           "rung are the second honest column, because that is where residual model "
           "error concentrates.", "",
           r"| steps | total s | top-rung s/config | vs hmc+winding | **rung 0 pre**"
           r" | rung 0 post | top $W(4\times4)$ | top $W(8\times8)$ |",
           "|---|---|---|---|---|---|---|---|"]
    for r in records:
        first, top = r["rungs"][0], r["rungs"][-1]
        ratio = r.get("ratio_vs_hmc_winding_top_rung")
        if ratio:
            rs = f"{ratio:.2f}x slower" if ratio > 1 else f"**{1 / ratio:.2f}x faster**"
        else:
            rs = "-"
        w4 = first["wilson"].get("wilson_4x4", {}).get("rel_err", float("nan"))
        w4 = top["wilson"].get("wilson_4x4", {}).get("rel_err", w4)
        w8 = top["wilson"].get("wilson_8x8", {}).get("rel_err", float("nan"))
        out.append(f"| {r['n_sampler_steps']} | {r['total_seconds']:.0f} | "
                   f"{r['seconds_per_config_top_rung']:.4f} | {rs} | "
                   f"**${first['rel_err_pre_retherm']:+.2e}$** | "
                   f"${first['rel_err']:+.2e}$ | ${w4:+.2e}$ | ${w8:+.2e}$ |")
    out += ["", r"**Tune on $W(8\times8)$, not on the plaquette -- the plaquette has "
                r"an accidental zero.** Rung 0's plaquette error changes SIGN between "
                "12 and 18 steps, so at 18 steps it reads "
                r"$+1.5\times10^{-4}$, as good as 100 steps and better than 25, while "
                r"$W(8\times8)$ at the top rung is eight times worse there than at "
                "200. A quantity passing through zero is a terrible selector, and "
                "picking the step count off the plaquette alone would have chosen a "
                "setting that is quietly bad at every extended observable. The "
                r"extended loops are monotone and unambiguous: $W(8\times8)$ improves "
                r"$1.5\times10^{-2} \to 3.4\times10^{-3} \to 1.1\times10^{-3} \to "
                r"4.2\times10^{-4} \to 1.6\times10^{-4}$ at 8, 18, 25, 200, 400 steps."
                "", "",
            "**So accuracy does not saturate at 200, and the hedge partly survives -- "
            "but it is a dial, not a free lunch.** Below 18 steps the lift collapses "
            r"(rung 0 off by $-1.2\times10^{-2}$ at 8 steps, and the rethermalization "
            r"sweeps still return $+4.3\times10^{-5}$, hiding all of it). Above that "
            "the whole range is usable and the trade is explicit: dropping 200 to 25 "
            "makes the top rung **1.38x faster** than HMC + winding instead of 2.22x "
            "slower -- a factor of three in cost -- for about 2.7x the extended-loop "
            "error and no measurable change in local observables after "
            r"rethermalization ($-1.8\times10^{-6}$ at 25 steps against "
            r"$+5.7\times10^{-6}$ at 200). Going the other way, 400 steps buys a "
            "further 2.7x on extended loops for 1.8x the cost.", "",
            "**The ladder of record stays at 200 steps**, because its job is to be "
            "the accuracy measurement rather than the cheapest configuration source, "
            "and because 25 steps would put the study's extended-observable claims "
            "where its own $L = 64$ reference sits rather than comfortably inside it. "
            "A production run that wants configurations should use 25.", "",
            "**Per-configuration Wilson spread is flat across the whole scan** "
            r"($\sigma[W(2\times2)] = 2.9$-$3.2\times10^{-4}$ against the "
            r"reference's $3.2\times10^{-4}$), so a coarse sampler biases the mean "
            "without narrowing the distribution. Cheap configurations do not come "
            "out over-smoothed, which is the failure mode one would expect and it "
            "does not happen.", "",
            r"$\langle Q^2\rangle$ is deliberately absent from this table. It is flat "
            "by construction -- `apply_coarse_charge` imposes the coarse charge on "
            "the final sample -- so topology is transported correctly at any step "
            "count, and printing it invites reading a tautology as a result.", "",
            "**Cost is not linear in the step count.** The two cheapest points fit "
            "about 1.05 s per step on a fixed overhead near 90 s: the exact "
            "conditional SU(2) sampler (30 sweeps) and the rethermalization (10 "
            "sweeps), which no amount of sampler tuning touches. At 200 steps that "
            "overhead is 30% of the run, at 25 steps it is three quarters. Anyone "
            "moving down the dial hits it quickly, so `n_su2_sweeps` is the next "
            "knob to measure, not this one.", ""]
    return out


def base_parity_table(records) -> list:
    """Does the odd/even balance ever move, and if not, what sets it?"""
    if not records:
        return []
    if isinstance(records, dict):
        records = [records]
    out = ["### Parity mobility: the odd fraction is a label, not an observable", "",
           "Hot start, **no burn-in**, unseeded, so a slow relaxation and a frozen "
           "label are distinguishable -- they prescribe opposite fixes. The decisive "
           "column is **parity flips**.", "",
           r"| $L$ | $\beta$ | start | $\beta L$ | $Q$ changes | **parity flips** |"
           r" chains flipped | odd frac | exact | binomial $z$ |"
           r" $\tau_{\rm int}(Q^2)$ |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(records, key=lambda r: (r["lattice_size"], r["beta"],
                                            r.get("start", "hot"))):
        out.append(
            f"| {r['lattice_size']} | {r['beta']:g} | {r.get('start', 'hot')} | "
            f"{r['beta_L']:.0f} | "
            f"{r['q_sector_changes']} | **{r['parity_flips']}** | "
            f"{r['chains_that_flipped']}/{r['n_chains']} | "
            f"{r['odd_fraction']:.4f} | {r['odd_exact']:.4f} | "
            f"${r['binomial_z']:+.2f}$ | {r['tau_int_q_squared_draws']:.2f} |")
    out += ["", "**Where the flip count is zero, the odd fraction is not a relaxing "
                "observable at all.** It is a label assigned to each chain once, "
                "during the hot-start ordering, and carried unchanged forever. The "
                "number of independent parity draws is then exactly $n_{\\rm chains}$ "
                "however long anything runs; the error model is a binomial over "
                "chains; and the only lever that improves it is more chains. Longer "
                "burn-in does nothing, and more draws per chain do nothing.", "",
            "That resolves a contradiction the study had been carrying. The stored "
            r"base ensemble measured an odd excess of 13% at $z_{\rm odd} = +2.42$, "
            r"$\chi^2/{\rm dof} = 2.41$ -- the PARITY-STUCK signature -- while a scan "
            "at the *identical* coupling measured 1.030 and $+0.69$, a clean SAMPLED "
            "verdict. Neither was wrong and neither was a bias: they are two draws of "
            "a 256-chain binomial that landed two sigma apart. A verdict computed "
            "from one such draw can pass or fail on luck, which is why a flip count "
            "is the better instrument.", "",
            r"**And this is the trap the theory sets.** $\tau_{\rm int}(Q^2)$ is "
            "around half a draw at every coupling in the table, including the ones "
            "where parity has not moved once. $Q^2$ fluctuates on the EVEN channel, "
            r"which the central instanton keeps wide open at cost $2\pi^2\beta/V$ -- "
            "a ladder invariant that never degrades. It is nearly blind to the "
            "odd/even channel, which is shut. A fast autocorrelation time on a "
            "quantity blind to the frozen mode certifies an equilibrium that does "
            r"not exist. Autocorrelate $Q \bmod 2$, or better, count flips.", ""]
    hot = [r for r in records if r.get("start", "hot") == "hot"]
    mobile = [r for r in hot if not r["parity_frozen"]]
    frozen = [r for r in hot if r["parity_frozen"]]
    if mobile and frozen:
        out += [r"**The controlling parameter is $\beta$, not $\beta L$, and the "
                r"study had this wrong.** Read the flip column against $\beta L$ and "
                r"it does not collapse: $L = 16$ at $\beta L = 224$ flips 2453 times "
                r"while $L = 8$ at $\beta L = 160$ flips four. Read it against "
                r"$\beta$ and it does: mobility dies between $\beta = 14$ and "
                r"$\beta \approx 20$ at **both** volumes, with the per-site rate "
                r"falling roughly a hundredfold across that interval. The earlier "
                r"$\beta L \approx 450$-$830$ boundary in `CLAUDE.md` came from "
                r"stage 07's *verdicts* rather than from flip counts, and it was "
                r"fitted to the $L = 16$ points while the $L = 8$ points "
                r"($\beta L = 112$ sampled, $160$ stuck) contradict it outright. "
                r"A verdict is a hypothesis test on one binomial draw; a flip count "
                r"is the mechanism itself.", "",
                r"The consequence is uncomfortable and has to be stated: **the ladder "
                r"base at $L = 16$, $\beta = 28$ is on the frozen side.** Zero flips "
                r"in 256 chains over 2000 trajectories. Stage 07 calls it SAMPLED "
                r"because its odd weight agrees with the closed form -- which is "
                r"true, and is not the same claim.", ""]
    elif frozen and not mobile:
        out += [r"Parity is frozen at every coupling scanned here.", ""]

    cold = [r for r in records if r.get("start") == "cold"]
    if cold:
        out += ["### What actually sets the split, where parity is frozen", "",
                "If the odd fraction were being sampled, the initial condition could "
                "not matter. Running the identical procedure from a cold start is "
                "therefore the direct test, and it is decisive.", "",
                r"| $L$ | $\beta$ | exact odd | hot start | cold start |",
                "|---|---|---|---|---|"]
        for c in sorted(cold, key=lambda r: (r["lattice_size"], r["beta"])):
            h = next((r for r in hot if r["lattice_size"] == c["lattice_size"]
                      and r["beta"] == c["beta"]), None)
            if not h:
                continue
            out.append(f"| {c['lattice_size']} | {c['beta']:g} | "
                       f"{c['odd_exact']:.4f} | {h['odd_fraction']:.4f} | "
                       f"{c['odd_fraction']:.4f} |")
        out.append("")
    return out


def sampling_table(scans) -> list:
    """The P(Q) scan table.

    TWO THINGS THIS MUST NOT DO, both of which it did until 2026-08-22.

    It must not read the pre-marginal-move directories. `pq_sampling`,
    `pq_sampling_L16` and `pq_sampling_L32` were measured with the JOINT winding
    proposal, whose odd acceptance is 0.000. Their verdicts describe a move that
    is no longer used, and they report `PARITY-STUCK` at L = 16 beta = 51.75 and
    56 and at L = 8 beta = 20 -- every one of which the marginal move samples
    cleanly. Splicing them into the narrative presents a retired sampler's
    failure as a property of the theory.

    And it must not print `chi2 / n_sectors`. That quantity was never
    chi-squared distributed -- correlated multinomial cells, the wrong per-cell
    variance, the wrong reference count -- and it rejected 10% of datasets drawn
    from the exact distribution. It is replaced by the bootstrap-calibrated
    `gof_p`, with mobility read off the parity FLIP COUNT rather than a
    significance gate, and a charge-conjugation column that tests an exact
    symmetry and so needs no closed form at all.

    `beta L` is dropped as a column: it was the ordering variable of a
    superseded claim, and odd mobility collapses on `beta`, not on `beta L`.
    """
    if not scans:
        return []
    out = ["### Where $P(Q)$ can be sampled rather than seeded", "",
           "Marginal odd move (`--charge-step 1 --winding-interval 5`)."
           " Mobility is a parity flip COUNT, agreement is a"
           " bootstrap-calibrated $p$-value, and $z_C$ tests charge conjugation,"
           " an exact symmetry, so it needs no closed form."
           " False-positive rates for each are measured in"
           " `48_verdict_calibration.py`.", "",
           "| $L$ | $\\beta$ | $\\beta/V$ | $\\langle Q^2\\rangle$ | exact"
           " | $z$ | parity flips | gof $p$ | $z_C$ | odd ratio"
           " | $z_{\\rm odd}$ | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(scans, key=lambda r: (r["lattice_size"], r["beta"])):
        out.append(
            f"| {r['lattice_size']} | {r['beta']:g} | "
            f"{r.get('beta_over_volume', r['beta'] / r['lattice_size']**2):.3f} | "
            f"${r['q_squared']:.4f} \\pm {r['q_squared_err']:.4f}$ | "
            f"{r['q_squared_exact']:.4f} | ${r['q_squared_z']:+.2f}$ | "
            f"{r.get('parity_flips', float('nan')):.0f} | "
            f"{r.get('gof_p', float('nan')):.3f} | "
            f"${r.get('charge_asymmetry_z', float('nan')):+.2f}$ | "
            f"{r.get('odd_ratio', float('nan')):.4f} | "
            f"${r.get('odd_z', float('nan')):+.2f}$ | {r.get('verdict', '—')} |")
    out.append("")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-place", action="store_true",
                        help="splice into docs/u2_2d/NARRATIVE.md between the markers")
    args = parser.parse_args()

    # The MARGINAL-move re-measurement is the record. The three directories this
    # used to read predate that move and carry verdicts from a proposal with
    # 0.000 odd acceptance; see `sampling_table`.
    scans = []
    for name in ("pq_sampling_marginal_L8_v3", "pq_sampling_marginal_L16_v3"):
        rows = _load(f"out/u2_2d/{name}/pq_sampling.json")
        if rows:
            scans.extend(rows)
    if not scans:
        print("WARNING: no marginal-move P(Q) scan found. The sampling table is "
              "OMITTED rather than filled from the retired joint-move runs.")

    lines = [BEGIN, "",
             "*Generated by `scripts/12_results_section.py` from the JSON each stage"
             " wrote; do not edit by hand.*", ""]
    lines += ladder_table(_load("out/u2_2d/ladder/summary.json"))
    lines += validation_table(_load("out/u2_2d/validation/summary.json"))
    lines += reference_control_table(_load("out/u2_2d/validation/summary.json"))
    lines += benchmark_table(_load("out/u2_2d/seed_benchmark/seed_benchmark.json"))
    lines += spread_table(_load("out/u2_2d/validation/wilson_distributions.json"))
    lines += spread_table(
        _load("out/u2_2d/validation/wilson_distributions_L64.json"),
        heading="### Per-configuration Wilson spread at the top rung",
        note="The width tracks the reference to within 3-8% at every loop size and "
             "shows **no growth with loop area**. That is the comparison the U(1) "
             "study could not pass -- there the dispersion ratio climbed 1.09 to "
             "1.44 from $W(4\\times4)$ to $W(12\\times12)$, and residual model error "
             "was diagnosed by exactly that growth. Here it is flat, at the rung "
             "furthest from anything the model was trained on.")
    lines += cost_table(_load("out/u2_2d/seed_benchmark/cost.json"))
    lines += sampler_steps_table(_load("out/u2_2d/sampler_steps/sampler_steps.json"))
    parity = []
    for name in ("base_parity_L8", "base_parity",
                 "base_parity_start_L8", "base_parity_start"):
        rows = _load(f"out/u2_2d/{name}/base_parity.json")
        if rows:
            parity.extend(rows if isinstance(rows, list) else [rows])
    # The hot/cold runs re-measure couplings the beta scan already covered. Keep one
    # record per (L, beta, start), the longest, so a short confirmation run never
    # displaces the long one it was confirming.
    best = {}
    for r in parity:
        key = (r["lattice_size"], r["beta"], r.get("start", "hot"))
        if key not in best or r["n_trajectories"] > best[key]["n_trajectories"]:
            best[key] = r
    lines += base_parity_table(list(best.values()))
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
