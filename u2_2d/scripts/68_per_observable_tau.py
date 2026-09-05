"""Per-observable relaxation times, with error bars, from ALREADY-SAVED
raw series -- no new HMC. 28_crossover_scan.py's `t_therm_per_observable`
field discards `fit_relaxation_time`'s tau_err (it exists only as a
cross-check, "logged, not used for anything downstream"), so there is
currently no way to tell whether a per-observable tau is even resolved. This
reads the raw `series/*.npz` 28 already writes for exactly this reason and
recomputes tau + tau_err + chi2/dof per observable per arm, so slow vs fast
mode scaling can be read off with honest error bars instead of the joint
fit's single shared tau (which one unlucky observable can dominate --
Table tab:u2_coverage's caption in the paper).

    python u2_2d/scripts/68_per_observable_tau.py --dir out/u2_2d/coverage_scan_relaxation/default
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from importlib import import_module
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
scan = import_module("28_crossover_scan")

LOCAL = ("plaquette", "wilson_2x2", "wilson_4x4")
STEM_RE = re.compile(r"^(.+)_beta([\d.eE+-]+)\.npz$")
L_RE = re.compile(r"_L(\d+)(?:_|$)")


def targets_for(beta: float, size: int) -> dict:
    return {
        "plaquette": scan.plaquette_exact(beta, size),
        "wilson_2x2": scan.wilson_loop_exact(beta, 4),
        "wilson_4x4": scan.wilson_loop_exact(beta, 16),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True,
                        help="a coverage_scan_relaxation/<tag> directory with a series/ subfolder")
    parser.add_argument("--out", default=None,
                        help="default: <dir>/per_observable_tau.json")
    args = parser.parse_args()

    src = Path(args.dir)
    series_dir = src / "series"
    if not series_dir.exists():
        print(f"no series/ under {src}")
        return 1

    rows = []
    for path in sorted(series_dir.glob("*.npz")):
        m = STEM_RE.match(path.name)
        if not m:
            print(f"skip (unparsed name) {path.name}")
            continue
        stem, beta_s = m.groups()
        lm = L_RE.search(stem)
        size = int(lm.group(1)) if lm else 32
        beta = float(beta_s)
        f = np.load(path)
        record_every = int(f["record_every"])
        targets = targets_for(beta, size)
        arms = sorted({k.split("__")[0] for k in f.keys() if "__" in k})
        per_arm = {}
        for arm in arms:
            per_obs = {}
            for name in LOCAL:
                key = f"{arm}__{name}"
                if key not in f:
                    continue
                tau_hat, tau_err = scan.fit_relaxation_time(
                    f[key], targets[name], record_every)
                per_obs[name] = {
                    "tau": None if not np.isfinite(tau_hat) else float(tau_hat),
                    "tau_is_inf": bool(np.isinf(tau_hat)),
                    "tau_err": None if not np.isfinite(tau_err) else float(tau_err),
                    "z": (float(tau_hat / tau_err)
                          if np.isfinite(tau_hat) and np.isfinite(tau_err) and tau_err > 0
                          else None),
                }
            per_arm[arm] = per_obs
        rows.append({"stem": stem, "lattice_size": size, "beta": beta,
                     "model_beta": scan.matched_u1_beta(beta),
                     "per_observable": per_arm})
        print(f"  {path.name}: " + ", ".join(
            f"{name}={per_arm.get('diffusion seed', {}).get(name, {}).get('tau')}"
            for name in LOCAL))

    dest = Path(args.out) if args.out else src / "per_observable_tau.json"
    dest.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {dest} ({len(rows)} couplings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
