"""Raw seed quality: the pre-registered endpoint, for BOTH studies.

`docs/u1_2d/COVERAGE_TEST_PREREG.md` records why this replaces the binary
"does the diffusion seed resolve a finite relaxation time?" indicator. Short
version: that indicator is inverted for good seeds. A seed FAR from the exact
value relaxes visibly, so the exponential fit succeeds and returns a finite
tau -- scored a success. A seed ALREADY AT the exact value has no decay to
resolve, so the fit returns inf or is rejected -- scored a failure. It also
cannot distinguish tau=0 (already correct, the best case) from tau=483
(correct only after 483 records, a bad one).

The endpoint here is the thing the coverage claim is actually about: how far
the delivered seed is from the truth, BEFORE any trajectory.

    Z   = max over {plaquette, W(2x2), W(4x4)} of |mean - exact| / SEM
    PPM = max over the same of |mean - exact| / |exact| * 1e6

both at record 0 of the saved series. Fit-free, so it inherits none of the
relaxation estimator's failure modes (local minima, the chi2/dof veto, the
chain-order dependence fixed 2026-09-08).

REPORT BOTH. `Z` alone is misleading across checkpoints, because
`z = sqrt(N) * bias / sigma`: a checkpoint whose seeds are NOISIER scores a
smaller z at the same bias. That is the same trap as the retracted N* finding
in CLAUDE.md, and it was hit once while building this script -- a first pass
on Z alone appeared to show a full inversion in U(2) that PPM did not support.

This is deliberately ONE script for both theories: u1 and u2 are evaluated by
the same method unless a difference is justified in writing (CLAUDE.md).
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon, binomtest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OBS = ("plaquette", "wilson_2x2", "wilson_4x4")
U2_STEMS = ("crossover", "crossover_topo", "crossover_L64", "crossover_L64_topo")


def u2_targets(beta: float, size: int) -> dict[str, float]:
    from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact
    return {"plaquette": plaquette_exact(beta, size),
            "wilson_2x2": wilson_loop_exact(beta, 4),
            "wilson_4x4": wilson_loop_exact(beta, 16)}


def u1_targets(beta: float, size: int) -> dict[str, float]:
    from u1_2d.lgt import exact
    return {"plaquette": exact.plaquette_exact(beta, "wilson", size),
            "wilson_2x2": exact.wilson_loop_exact(beta, 4, "wilson", size),
            "wilson_4x4": exact.wilson_loop_exact(beta, 16, "wilson", size)}


def score(series: dict, targets: dict) -> tuple[float, float] | None:
    zs, ppms = [], []
    for name in OBS:
        if name not in series:
            return None
        s = np.asarray(series[name], dtype=np.float64)[0]
        sem = s.std(ddof=1) / math.sqrt(len(s))
        bias = abs(float(s.mean()) - targets[name])
        zs.append(bias / sem if sem > 0 else float("inf"))
        ppms.append(bias / abs(targets[name]) * 1e6)
    return max(zs), max(ppms)


def load_u2(tag: str, base: Path) -> dict:
    out = {}
    for stem in U2_STEMS:
        pj = base / tag / f"{stem}.json"
        if not pj.exists():
            continue
        for rec in json.loads(pj.read_text()):
            f = base / tag / "series" / f"{stem}_beta{rec['beta']:g}.npz"
            if not f.exists():
                continue
            d = np.load(f, allow_pickle=True)
            ser = {n: d[f"diffusion seed__{n}"] for n in OBS
                   if f"diffusion seed__{n}" in d.files}
            got = score(ser, u2_targets(rec["beta"], rec["lattice_size"]))
            if got is None:
                continue
            # Use t_therm["diffusion seed"], matching 81_paper_numbers.py and the
            # published table. NOTE the binary indicator is not even well defined:
            # rec["seed"] and rec["t_therm"]["diffusion seed"] disagree on 3 of
            # cov60's 28 L=32 records (seed=0.0 "already at target" against
            # t_therm=inf "never converges") -- the same 0-vs-inf conflation that
            # motivates replacing it. Which field you read moves the count by 3.
            t = rec["t_therm"]["diffusion seed"]
            out[(stem, round(rec["beta"], 3))] = {
                "Z": got[0], "PPM": got[1], "beta": rec["beta"],
                "L": rec["lattice_size"],
                "res": isinstance(t, (int, float)) and math.isfinite(t)}
    return out


def load_u1(arm: Path) -> dict:
    out = {}
    for case in sorted((arm / "thermalization").glob("L*_beta*")):
        sf = sorted(case.glob("*_summary.json"))
        nf = sorted(case.glob("*_series.npz"))
        if not sf or not nf:
            continue
        summ = json.loads(sf[0].read_text())
        d = np.load(nf[0], allow_pickle=True)
        ser = {n: d[f"diffusion seed|{n}"] for n in OBS
               if f"diffusion seed|{n}" in d.files}
        got = score(ser, u1_targets(summ["beta"], summ["lattice_size"]))
        if got is None:
            continue
        tw = [summ["t_therm"]["diffusion seed"].get(n) for n in OBS]
        res = all(isinstance(v, (int, float)) and math.isfinite(v) for v in tw)
        out[round(summ["beta"], 3)] = {
            "Z": got[0], "PPM": got[1], "beta": summ["beta"],
            "L": summ["lattice_size"], "res": res}
    return out


def median_ratio_ci(num, den, n_boot=20000, seed=0):
    """Median of the paired ratio, with a percentile bootstrap CI over COUPLINGS.

    The pairing is exact -- both arms are evaluated on identical cases -- so the
    resampling unit is the coupling, not the configuration.
    """
    r = np.asarray(num, dtype=np.float64) / np.maximum(np.asarray(den, np.float64), 1e-12)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(r), size=(n_boot, len(r)))
    boot = np.median(r[idx], axis=1)
    return float(np.median(r)), float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def report_pair(a, b, arms, keys, label):
    """One paired comparison on one set of couplings.

    Z is the PRE-REGISTERED primary (docs/u1_2d/COVERAGE_TEST_PREREG.md); PPM is
    reported alongside because z = sqrt(N)*bias/sigma rewards a noisier
    checkpoint at equal bias. Both are printed always, so the choice cannot be
    made after seeing them.
    """
    za = np.array([arms[a][k]["Z"] for k in keys])
    zb = np.array([arms[b][k]["Z"] for k in keys])
    pa = np.array([arms[a][k]["PPM"] for k in keys])
    pb = np.array([arms[b][k]["PPM"] for k in keys])
    zr, zlo, zhi = median_ratio_ci(za, zb)
    pr, plo, phi = median_ratio_ci(pa, pb)
    print(f"\n{a} vs {b}  [{label}]  (n={len(keys)} paired)")
    print(f"   Z   (PRIMARY, pre-registered): {b} better at {int((zb < za).sum())}/{len(keys)}, "
          f"median ratio {zr:.1f}x CI [{zlo:.1f}, {zhi:.1f}], "
          f"Wilcoxon p={wilcoxon(np.log(za), np.log(zb)).pvalue:.4f}")
    print(f"   PPM (reported alongside)     : {b} better at {int((pb < pa).sum())}/{len(keys)}, "
          f"median ratio {pr:.1f}x CI [{plo:.1f}, {phi:.1f}], "
          f"Wilcoxon p={wilcoxon(np.log(pa), np.log(pb)).pvalue:.4f}")
    da = sum(1 for k in keys if arms[a][k]["res"] and not arms[b][k]["res"])
    db = sum(1 for k in keys if arms[b][k]["res"] and not arms[a][k]["res"])
    pbin = binomtest(db, da + db).pvalue if da + db else 1.0
    print(f"   binary (secondary): {sum(arms[a][k]['res'] for k in keys)}"
          f" vs {sum(arms[b][k]['res'] for k in keys)}, "
          f"discordant {da}/{db}, p={pbin:.4f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theory", choices=("u1", "u2"), required=True)
    ap.add_argument("--tags", nargs="+", required=True,
                    help="u2: checkpoint tags under coverage_scan_relaxation/. "
                         "u1: 'name=path' arm directories.")
    ap.add_argument("--base", default="out/u2_2d/coverage_scan_relaxation")
    ap.add_argument("--per-coupling", action="store_true")
    ap.add_argument("--subgroup-betas", default=None,
                    help="Comma-separated FINE betas forming a pre-specified "
                         "subgroup, reported separately (u1: the 8 off-rung "
                         "couplings). Matched to 0.5%% relative tolerance.")
    ap.add_argument("--subgroup-label", default="subgroup")
    args = ap.parse_args()

    arms: dict[str, dict] = {}
    if args.theory == "u2":
        for t in args.tags:
            arms[t] = load_u2(t, Path(args.base))
    else:
        for spec in args.tags:
            name, _, path = spec.partition("=")
            arms[name] = load_u1(Path(path))

    print("RAW SEED QUALITY at record 0 (lower is better)")
    print(f"{'checkpoint':<16}{'n':>4}{'median Z':>11}{'median PPM':>13}"
          f"{'binary resolves':>18}")
    for t, d in arms.items():
        if not d:
            print(f"{t:<16}   0   (no series found)")
            continue
        print(f"{t:<16}{len(d):>4}{np.median([v['Z'] for v in d.values()]):>11.2f}"
              f"{np.median([v['PPM'] for v in d.values()]):>13.1f}"
              f"{sum(v['res'] for v in d.values())}/{len(d):>3}")

    if args.per_coupling:
        for t, d in arms.items():
            print(f"\n-- {t}")
            for k in sorted(d, key=lambda k: d[k]["beta"]):
                v = d[k]
                print(f"   L={v['L']:<4} beta={v['beta']:>9.2f}  Z={v['Z']:>8.2f}"
                      f"  PPM={v['PPM']:>10.1f}  resolves={v['res']}")

    print("\nPAIRED TESTS over identical couplings")
    print("   primary endpoint Z, per docs/u1_2d/COVERAGE_TEST_PREREG.md")

    sub = None
    if args.subgroup_betas:
        want = [float(x) for x in args.subgroup_betas.split(",")]
        sub = lambda v: any(abs(v["beta"] - w) <= 0.005 * w for w in want)

    for a, b in combinations(arms, 2):
        keys = sorted(set(arms[a]) & set(arms[b]))
        if len(keys) < 4:
            continue
        report_pair(a, b, arms, keys, "all couplings")
        if sub is not None:
            sk = [k for k in keys if sub(arms[a][k])]
            if len(sk) >= 4:
                report_pair(a, b, arms, sk, args.subgroup_label)
            else:
                print(f"   [{args.subgroup_label}: only {len(sk)} matched, not tested]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
