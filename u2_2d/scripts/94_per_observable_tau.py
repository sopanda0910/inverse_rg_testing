"""Per-observable relaxation times, with the guard the joint fit does not need.

WHY THIS IS NOT A CALL INTO `28_crossover_scan.fit_relaxation_time`.

That function applies its tail-bias check only when the point estimate comes
back exactly zero (`if tau_hat == 0.0:`). The check exists because a series
that is flat and stuck AWAY from target has no decay to resolve and must be
reported as `inf`, not as `0` -- opposite conclusions. But a cold start at
strong coupling does something the zero-case does not cover: it drops FAST from
far away to a plateau that is still wrong, which fits a sharp exponential and
returns a small NON-ZERO tau. That value then escapes the check entirely.

Measured, L = 64, beta = 636.85, cold arm, plaquette:

    starts   648 sigma from exact
    ends    12.3 sigma from exact   (t_therm = inf, never equilibrates)
    fit     tau = 2.24 +- 0.07 trajectories
    guard   _tail_is_biased -> True, but never consulted

So a chain that never equilibrates is reported as relaxing in two trajectories.
The scan's own stored `t_therm` is NOT affected: it uses the JOINT fit across
observables, which returns `nan` for these arms. The defect bites only a
per-observable re-fit, which is what this script does.

The guard here is applied unconditionally: whatever tau the fit returns, if the
settled half of the history is still biased against the target under chain
resampling, the answer is `inf`. That is strictly more conservative than the
scan and cannot turn a non-converging chain into a fast one.

Per-observable tau is worth having because it is BAND-INDEPENDENT -- a decay
rate, where `t_therm = tau * ln(b0/band)` is a crossing that inherits the
band's volume and coupling dependence -- and because the cold arm does
equilibrate on SOME observables even where the joint fit fails, so it gives the
comparison more than the single point the joint fit leaves.

Reads the saved series; needs no new HMC.
"""
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from u2_2d.lgt.exact import plaquette_exact, wilson_loop_exact  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_scan", ROOT / "u2_2d" / "scripts" / "28_crossover_scan.py")
_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_scan)

ARMS = ("cold start", "diffusion seed", "hot start")
AREA = {"plaquette": 1, "wilson_2x2": 4, "wilson_4x4": 16, "wilson_8x8": 64}


def exact_for(obs, beta, L):
    if obs == "plaquette":
        return plaquette_exact(beta, L)
    return wilson_loop_exact(beta, AREA[obs], lattice_size=L)


def guarded_tau(series, target, record_every, seed=0):
    """fit_relaxation_time, with the tail-bias check applied UNCONDITIONALLY.

    Returns (tau, err). `inf` means the settled half is still biased against
    target, whatever the fit said -- a chain that has not arrived cannot be
    assigned a relaxation time.
    """
    tau, err = _scan.fit_relaxation_time(series, target, record_every)
    tail = series[len(series) // 2:]
    rng = np.random.default_rng(seed)
    if _scan._tail_is_biased([(tail, target)], rng, series.shape[1]):
        return float("inf"), float("nan")
    return tau, err


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base",
                    default="out/u2_2d/coverage_scan_relaxation/wide_dense")
    ap.add_argument("--stems", default="crossover_topo:32,crossover_L64_topo:64")
    ap.add_argument("--out", default=None, help="write a JSON summary here")
    args = ap.parse_args()

    base = Path(args.base)
    out = {}
    for item in args.stems.split(","):
        stem, L = item.split(":")
        L = int(L)
        f = base / f"{stem}.json"
        if not f.exists():
            print(f"missing {f}")
            continue
        rows = json.loads(f.read_text(encoding="utf-8"))
        # observables actually present, in loop-size order
        probe = None
        for r in rows:
            sf = base / "series" / f"{stem}_beta{float(r['beta']):g}.npz"
            if sf.exists():
                probe = np.load(sf)
                break
        if probe is None:
            continue
        obs_list = [o for o in ("plaquette", "wilson_2x2", "wilson_4x4",
                                "wilson_8x8")
                    if f"cold start__{o}" in probe]

        print(f"\n=== L={L}  ({stem})  tau in trajectories, inf = never arrives")
        hdr = f"{'beta':>9} |"
        for arm in ARMS[:2]:
            hdr += f" {arm.split()[0]:^{7*len(obs_list)}} |"
        print(hdr)
        print(f"{'':>9} |" + ("".join(f"{o.replace('wilson_','W'):>7}"
                                      for o in obs_list) + " |") * 2)
        tally = {a: {"finite": 0, "inf": 0} for a in ARMS[:2]}
        for r in rows:
            beta = float(r["beta"])
            sf = base / "series" / f"{stem}_beta{beta:g}.npz"
            if not sf.exists():
                continue
            z = np.load(sf)
            re_ = float(z["record_every"])
            line = f"{beta:9.2f} |"
            rec = out.setdefault(f"{stem}|{beta:g}", {"beta": beta, "L": L})
            for arm in ARMS[:2]:
                cells = []
                for o in obs_list:
                    key = f"{arm}__{o}"
                    if key not in z:
                        cells.append("--")
                        continue
                    tau, _ = guarded_tau(np.asarray(z[key], dtype=float),
                                         exact_for(o, beta, L), re_)
                    rec.setdefault(arm, {})[o] = (None if not np.isfinite(tau)
                                                  else float(tau))
                    if np.isfinite(tau):
                        tally[arm]["finite"] += 1
                        cells.append(f"{tau:.0f}")
                    else:
                        tally[arm]["inf"] += 1
                        cells.append("inf")
                line += "".join(f"{c:>7}" for c in cells) + " |"
            print(line)
        for arm in ARMS[:2]:
            t = tally[arm]
            print(f"   {arm:16s} finite {t['finite']:3d}   never {t['inf']:3d}")

    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
