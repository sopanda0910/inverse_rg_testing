"""Regression tests for the appendix-figure assembly and the ladder plots.

Both bugs guarded here were real and both produced a *plausible-looking* wrong
figure rather than an error, which is why they need tests:

  1. Rows under a `## rung..._RAW_preenforcement` heading were being folded into
     the preceding rung, so figure 01 showed the raw pre-rethermalization
     ensemble (plaquette z = -9.1) as if it were the deployed one (-0.19).
  2. `write_report` emits only the columns present in a given table, so the
     column set differs between rungs. Parsing by fixed index silently read
     ks_p as `ref_topology_frozen` and lost the frozen flag at L = 32.
"""

import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from u1_2d.validate.report import plot_ladder_drift, plot_ladder_topology

REPO = Path(__file__).resolve().parents[2]


def _assemble_module():
    path = REPO / "u1_2d" / "scripts" / "30_assemble_appendix_figures.py"
    spec = importlib.util.spec_from_file_location("assemble_appendix", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Two rungs whose tables have DIFFERENT column sets (rung1 has no ref_tau_int),
# each followed by a RAW_preenforcement table with contradictory numbers.
REPORT = """# Validation report

## rung0_L16_beta4

| observable | value | error | exact | z_exact | reference | ref_error | ref_tau_int | z_ref | ref_topology_frozen | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.8653 | 0.0008 | 0.8635 | 2.155 | 0.8641 | 0.0008 |  | 1.068 | False | 0.7159 |  |
| wilson_2x2 | 0.5571 | 0.0034 | 0.556 | 0.3097 | 0.5579 | 0.0027 |  | -0.177 | False | 0.9925 |  |
| wilson_4x4 | 0.0942 | 0.0065 | 0.09558 | -0.2125 | 0.09572 | 0.0042 |  | -0.196 | False | 0.7118 |  |
| Q | -0.0625 | 0.1064 | 0 | -0.5875 | -0.1667 | 0.1226 | 1.906 | 0.6419 | False | 0.9996 |  |
| Q^2 | 1.823 | 0.1725 | 1.934 | -0.6431 | 1.536 | 0.1729 | 1.447 | 1.173 | False | 0.7262 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.0071 | 0.0007 | 0.0076 | -0.6687 | 0.0059 | 0.0007 |  | 1.297 | False |  |  |

## rung0_L16_beta4_RAW_preenforcement

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ref_topology_frozen | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.8566 | 0.0011 | 0.8635 | -6.445 | 0.8641 | 0.0008 | -5.575 | False | 2.4e-06 |  |

## rung1_L32_beta14.1464

| observable | value | error | exact | z_exact | reference | ref_error | z_ref | ref_topology_frozen | ks_p | chi2_p |
|---|---|---|---|---|---|---|---|---|---|---|
| plaquette | 0.9641 | 0.0001 | 0.964 | 0.779 | 0.9627 | 0.0001 | 8.007 | False | 2.6e-11 |  |
| wilson_2x2 | 0.8683 | 0.0005 | 0.8684 | -0.064 | 0.8651 | 0.0004 | 5.1 | False | 1e-06 |  |
| wilson_4x4 | 0.5680 | 0.0016 | 0.5685 | -0.278 | 0.5601 | 0.0013 | 3.8 | False | 1e-05 |  |
| Q | -0.0625 | 0.1064 | 0 | -0.5875 | -0.375 | 0.1778 | 1.508 | True | 2.9e-05 |  |
| Q^2 | 1.823 | 0.1725 | 1.904 | -0.47 | 12.25 | 1.08 | -9.537 | True | 1.2e-08 |  |
| chi_top ((<Q^2>-<Q>^2)/V) | 0.0018 | 0.0002 | 0.0019 | -0.495 | 0.0118 | 0.001 | -9.5 | True |  |  |
"""


def _parse(tmp_path):
    module = _assemble_module()
    report = tmp_path / "report.md"
    report.write_text(REPORT, encoding="utf-8")
    return module.parse_validation_report(report)


def test_raw_preenforcement_rows_do_not_overwrite_the_deployed_rung(tmp_path):
    rungs = _parse(tmp_path)
    assert [r["rung"] for r in rungs] == [0, 1]
    # -6.445 is the RAW value; the deployed one is +2.155.
    assert rungs[0]["z"]["plaquette"] == 2.155
    assert rungs[0]["plaq_z"] == 2.155


def test_columns_parsed_by_name_not_position(tmp_path):
    """rung1's table omits ref_tau_int, shifting every later column."""
    rungs = _parse(tmp_path)
    q2 = rungs[1]["obs"]["Q^2"]
    assert q2["reference"] == 12.25
    assert q2["ref_topology_frozen"] is True
    assert rungs[0]["obs"]["Q^2"]["ref_topology_frozen"] is False


def test_drift_observables_present_for_every_rung(tmp_path):
    rungs = _parse(tmp_path)
    for rung in rungs:
        for name in ("plaquette", "wilson_2x2", "wilson_4x4"):
            assert name in rung["z"], f"rung{rung['rung']} missing {name}"


def test_ladder_plots_render_from_parsed_report(tmp_path):
    rungs = _parse(tmp_path)
    plot_ladder_drift(rungs, tmp_path)
    plot_ladder_topology(rungs, tmp_path)
    assert (tmp_path / "ladder_drift.png").stat().st_size > 0
    assert (tmp_path / "ladder_topology.png").stat().st_size > 0


def test_every_tracked_figure_is_referenced_by_the_appendix():
    module = _assemble_module()
    referenced = module.referenced_in_appendix()
    if not referenced:
        return  # appendix.md not present in this checkout
    assert not (set(module.SOURCES) - referenced), "tracked figure never cited"
    assert not (referenced - set(module.SOURCES)), "appendix cites an untracked figure"
