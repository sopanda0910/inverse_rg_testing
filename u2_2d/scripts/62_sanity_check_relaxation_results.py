"""Value-level sanity monitor for the relaxation-time coverage/volume matrix.

Built 2026-09-03 after a real bug shipped a physically-impossible result
(`seed=3980.0` trajectories against a 400-trajectory budget) into a live run
-- caught by chance during a routine status check, not by anything
automated. A process-liveness watchdog (`watchdog_overnight.ps1`) checks
"is it running", never "is the OUTPUT sane"; this script is the second kind
of check, meant to run every watchdog tick alongside the first.

Flags, on every record in every out/u2_2d/coverage_scan_relaxation/*/*.json:

  * a finite tau larger than the total trajectory budget for that coupling
    (`n_traj`) -- the fit's search bound is deliberately much larger than
    the budget (to allow genuinely slow-but-resolved decays), so this is
    not automatically a bug the way the boundary-saturation case was, but
    it is a big enough number to warrant a human look every time, exactly
    the shape of anomaly that shipped last time.
  * a NEGATIVE tau, tau_err, or chi2_per_dof (impossible for all three).
  * a NaN/Inf chi2_per_dof paired with a FINITE tau (chi2_per_dof should
    only be undefined-looking in the tau=0/inf branches, never alongside a
    genuine resolved fit).
  * THE SPECIFIC PATTERN THAT PROMPTED THIS SCRIPT'S NAME: a checkpoint's
    diffusion-seed arm reporting a SMALL, finite, resolved tau at a coupling
    whose model_beta sits well past that checkpoint's own training-coverage
    edge. Every measurement so far says the seed should be unresolvable
    (tau=inf) out there, not merely slow -- a small finite tau there is
    either a genuine, surprising physics result or (far more likely, on
    priors) another fitting artifact, and either way it must not be quoted
    without being looked at directly first.

Run standalone:
    python u2_2d/scripts/62_sanity_check_relaxation_results.py
Or via the watchdog (wired into watchdog_overnight.ps1), which diffs against
a small state file so only NEW anomalies alert, not the same one every 15
minutes forever.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

# Training-coverage ceilings, in MODEL beta -- kept in sync with
# 58_training_coverage_scan.py's CHECKPOINTS table by hand (both are small
# and rarely change; a mismatch here only makes this monitor conservative,
# never silently wrong in the dangerous direction, since UNDER-estimating a
# checkpoint's true ceiling only produces extra false-positive flags to
# review, not a missed real one).
TRAIN_MODEL_BETA_MAX = {
    "default": 104.132, "v2": 107.5, "cap": 107.5,
    "cov60": 56.83, "cov30": 29.60, "cov15": 14.55,
}
PAST_COVERAGE_FACTOR = 1.5  # "well past" = 50% beyond the checkpoint's own edge


def check_record(tag: str, r: dict) -> list[str]:
    issues = []
    n_traj = r.get("n_traj")
    model_beta = r.get("model_beta")
    train_max = TRAIN_MODEL_BETA_MAX.get(tag)
    tau_map = r.get("t_therm", {})
    err_map = r.get("t_therm_err", {})
    chi2_map = r.get("t_therm_chi2_per_dof", {})

    for arm, tau in tau_map.items():
        if tau is None:
            continue
        err = (err_map or {}).get(arm)
        chi2 = (chi2_map or {}).get(arm)

        if isinstance(tau, (int, float)) and tau == tau and tau not in (float("inf"),):
            if tau < 0:
                issues.append(f"[{tag}] beta={r.get('beta'):.2f} arm={arm}: "
                              f"NEGATIVE tau={tau}")
            elif n_traj and tau > n_traj:
                issues.append(f"[{tag}] beta={r.get('beta'):.2f} arm={arm}: "
                              f"tau={tau:.1f} EXCEEDS the trajectory budget "
                              f"(n_traj={n_traj}) -- review before quoting")
            if arm == "diffusion seed" and train_max and model_beta and 0 < tau:
                if model_beta > PAST_COVERAGE_FACTOR * train_max:
                    issues.append(
                        f"[{tag}] beta={r.get('beta'):.2f} (model {model_beta:.1f}, "
                        f"{model_beta / train_max:.1f}x past its {train_max:.1f} "
                        f"coverage edge): diffusion seed reports a RESOLVED "
                        f"finite tau={tau:.2f} -- every prior measurement says "
                        f"this should be inf; verify before treating as real")

        if err is not None and isinstance(err, (int, float)) and err == err and err < 0:
            issues.append(f"[{tag}] beta={r.get('beta'):.2f} arm={arm}: "
                          f"NEGATIVE tau_err={err}")
        if chi2 is not None and isinstance(chi2, (int, float)):
            if chi2 == chi2 and chi2 < 0:
                issues.append(f"[{tag}] beta={r.get('beta'):.2f} arm={arm}: "
                              f"NEGATIVE chi2_per_dof={chi2}")
            if chi2 != chi2 and tau not in (0.0, float("inf")):  # NaN check
                issues.append(f"[{tag}] beta={r.get('beta'):.2f} arm={arm}: "
                              f"chi2_per_dof is NaN alongside a resolved tau={tau}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="out/u2_2d/coverage_scan_relaxation")
    parser.add_argument("--state-file",
                        default="out/u2_2d/coverage_scan_relaxation/sanity_seen.json")
    parser.add_argument("--quiet-if-clean", action="store_true",
                        help="print nothing when there are no NEW issues")
    args = parser.parse_args()

    seen = set()
    state_path = Path(args.state_file)
    if state_path.exists():
        try:
            seen = set(json.loads(state_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            seen = set()

    all_issues = []
    for path in sorted(glob.glob(f"{args.root}/*/*.json")):
        tag = Path(path).parent.name
        try:
            rows = json.loads(Path(path).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(rows, list):
            continue
        for r in rows:
            all_issues.extend(check_record(tag, r))

    new_issues = [i for i in all_issues if i not in seen]
    if new_issues:
        print(f"SANITY CHECK: {len(new_issues)} NEW issue(s) found")
        for i in new_issues:
            print(f"  !! {i}")
    elif not args.quiet_if_clean:
        print(f"SANITY CHECK: clean ({len(all_issues)} known issue(s), 0 new)")

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(set(all_issues))), encoding="utf-8")
    return 1 if new_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
