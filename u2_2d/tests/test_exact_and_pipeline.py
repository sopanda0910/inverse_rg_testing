"""Exact solution, RG matching, and the factorized lift end to end."""

import math

import numpy as np
import pytest
import torch
from scipy.special import ive

from u2_2d.lgt import exact
from u2_2d.lgt.actions import WilsonU2Action
from u2_2d.lgt.blocking import (
    approx_matched_coarse_beta,
    approx_matched_fine_beta,
    block_links,
    ladder_charge_fixed_point,
    match_coarse_beta,
    matching_residuals,
    tree_level_coarse_beta,
)
from u2_2d.lgt.lattice import (
    det_links,
    half_retr,
    identity_links,
    plaquette,
    random_links,
    topological_charge,
    wilson_loop,
)
from u2_2d.lgt.local_updates import retherm_sweeps
from u2_2d.model.det_lift import det_pair, det_rung_data, model_beta
from u2_2d.model.su2_lift import assemble_links, half_quaternion, naive_su2_inverse_block
from u2_2d.validate.observables import exact_reference, measure_ensemble
from u2_2d.validate.report import compare, render_markdown


# ---------------------------------------------------------------- exact solution

@pytest.mark.parametrize("beta", [0.5, 2.0, 8.0, 30.0, 120.0])
def test_character_expansion_reproduces_weyl_integration(beta):
    x = 0.5 * beta
    weyl = 0.5 * ive(1, x) * (ive(0, x) - ive(2, x)) / (ive(0, x) ** 2 - ive(1, x) ** 2)
    assert exact.plaquette_exact(beta) == pytest.approx(weyl, abs=1e-10)


@pytest.mark.parametrize("beta", [1.0, 6.0, 25.0])
def test_fundamental_character_ratio_is_the_plaquette(beta):
    assert exact.wilson_loop_exact(beta, 1) == pytest.approx(exact.plaquette_exact(beta), abs=1e-10)


@pytest.mark.parametrize("beta", [1.0, 6.0, 25.0])
def test_area_law_is_exact(beta):
    ratio = exact.plaquette_exact(beta)
    for area in (2, 3, 7):
        assert exact.wilson_loop_exact(beta, area) == pytest.approx(ratio**area, rel=1e-9)
    assert -math.log(exact.wilson_loop_exact(beta, 1)) == pytest.approx(
        -math.log(ratio), abs=1e-10)


def test_parity_constraint_rejects_forbidden_irreps():
    with pytest.raises(ValueError):
        exact.wilson_loop_exact(4.0, 1, two_j=1, charge=0)


@pytest.mark.parametrize("beta", [2.0, 10.0])
def test_finite_volume_plaquette_converges_to_infinite_volume(beta):
    small = abs(exact.plaquette_exact(beta, 6) - exact.plaquette_exact(beta))
    large = abs(exact.plaquette_exact(beta, 20) - exact.plaquette_exact(beta))
    assert large <= small + 1e-12
    assert large < 1e-6


def test_log_partition_is_extensive():
    per_site = [exact.log_partition(5.0, size) / size**2 for size in (6, 12, 24)]
    assert per_site[2] == pytest.approx(per_site[1], rel=1e-3)


@pytest.mark.parametrize("beta", [3.0, 15.0])
def test_determinant_topological_charge_distribution(beta):
    q_values, probs = exact.det_topological_charge_distribution(beta, 10)
    assert probs.sum() == pytest.approx(1.0)
    assert np.allclose(probs, probs[::-1])
    chi_from_pq = float((q_values**2 * probs).sum()) / 100.0
    assert chi_from_pq == pytest.approx(exact.det_topological_susceptibility(beta), rel=0.05)


def test_determinant_weight_is_positive_and_peaked_at_zero():
    grid = np.linspace(-math.pi, math.pi, 101)
    density = exact.det_plaquette_angle_density(grid, 9.0)
    assert (density >= 0).all()
    assert density.argmax() == 50
    assert np.trapezoid(density, grid) == pytest.approx(1.0, rel=1e-6)


def test_determinant_characters_decrease_with_charge():
    ratios = [exact.det_character_exact(8.0, q) for q in (1, 2, 3, 4)]
    assert all(ratios[i] > ratios[i + 1] > 0 for i in range(len(ratios) - 1))


def test_matched_u1_beta_approaches_quarter_beta():
    for beta, tol in ((14.0, 0.1), (56.0, 0.02), (400.0, 1e-3)):
        assert exact.matched_u1_beta(beta) / (beta / 4.0) == pytest.approx(1.0, abs=tol)


def test_determinant_sector_is_not_u1_wilson_at_strong_coupling():
    """The whole point of DetSectorAction: beta/4 is a large-beta limit, not an identity."""
    residual = exact.det_matching_residuals(4.0)
    assert abs(residual["tree_level_ratio"] - 1.0) > 0.1
    assert abs(residual["character_residuals"][2]) > 0.1
    fine = exact.det_matching_residuals(220.0)
    assert abs(fine["tree_level_ratio"] - 1.0) < 1e-3
    assert abs(fine["character_residuals"][2]) < 1e-4


# ------------------------------------------------------------------- RG matching

def test_matched_coarse_beta_approaches_tree_level():
    for beta, tol in ((55.0, 0.1), (220.0, 0.02)):
        matched = approx_matched_coarse_beta(beta)
        assert matched / tree_level_coarse_beta(beta) == pytest.approx(1.0, abs=tol)


def test_matched_beta_round_trip():
    for beta in (10.0, 60.0):
        assert approx_matched_fine_beta(approx_matched_coarse_beta(beta)) == pytest.approx(
            beta, rel=1e-5)


def test_matching_residuals_shrink_with_coupling():
    coarse = matching_residuals(14.0)["det_character_residuals"][2]
    fine = matching_residuals(220.0)["det_character_residuals"][2]
    assert abs(fine) < abs(coarse)


def test_empirical_beta_matching_recovers_the_analytic_one():
    torch.manual_seed(21)
    beta, size = 24.0, 8
    ensemble = retherm_sweeps(identity_links(size, batch=48, dtype=torch.float64),
                              WilsonU2Action(beta), 120)
    fitted = match_coarse_beta(block_links(ensemble))
    assert fitted == pytest.approx(approx_matched_coarse_beta(beta), rel=0.15)


def test_ladder_charge_is_near_a_fixed_point():
    rungs = ladder_charge_fixed_point(56.6, 8, n_rungs=4)
    values = [r["q_squared"] for r in rungs]
    assert all(r["beta"] == pytest.approx(56.6 * 4**i) for i, r in enumerate(rungs))
    assert all(r["lattice_size"] == 8 * 2**i for i, r in enumerate(rungs))
    assert abs(values[-1] / values[-2] - 1.0) < 0.02


# ----------------------------------------------------------------- factorization

def test_naive_su2_inverse_block_reproduces_the_blocking_constraint():
    torch.manual_seed(22)
    coarse = random_links(4, batch=2, dtype=torch.float64)
    seed = naive_su2_inverse_block(coarse[..., 1:])
    assert seed.shape == (2, 2, 8, 8, 4)
    fine = assemble_links(torch.zeros(2, 2, 8, 8, dtype=torch.float64), seed)
    blocked = block_links(fine)
    assert torch.allclose(blocked[..., 1:], coarse[..., 1:], atol=1e-10)


def test_half_quaternion_squares_back():
    torch.manual_seed(23)
    q = random_links(4, batch=2, dtype=torch.float64)[..., 1:]
    from u2_2d.lgt.lattice import quat_mul

    half = half_quaternion(q)
    assert torch.allclose(quat_mul(half, half), q, atol=1e-10)


def test_assemble_links_sets_the_determinant_sector():
    torch.manual_seed(24)
    psi = torch.rand(2, 2, 6, 6, dtype=torch.float64) * 2 - 1
    su2 = random_links(6, batch=2, dtype=torch.float64)[..., 1:]
    links = assemble_links(psi, su2)
    assert links.shape == (2, 2, 6, 6, 5)
    assert torch.allclose(torch.sin(det_links(links)), torch.sin(psi), atol=1e-12)
    assert torch.equal(links[..., 1:], su2)


def test_det_pair_matches_u1_blocking():
    import u1_2d.lgt.blocking as u1_blocking

    torch.manual_seed(25)
    links = random_links(8, batch=3, dtype=torch.float64)
    fine, coarse = det_pair(links)
    assert fine.shape == (3, 2, 8, 8)
    assert coarse.shape == (3, 2, 4, 4)
    assert torch.allclose(torch.sin(coarse),
                          torch.sin(u1_blocking.block_links(fine)), atol=1e-12)


def test_det_rung_data_is_conditioned_on_the_matched_coupling():
    torch.manual_seed(26)
    rung = det_rung_data("t", random_links(8, batch=4), 56.0)
    assert rung.beta == pytest.approx(model_beta(56.0))
    assert rung.beta != pytest.approx(56.0 / 4.0)
    assert rung.fine.shape == (4, 2, 8, 8)
    assert rung.coarse.shape == (4, 2, 4, 4)


def test_generate_fine_from_coarse_doubles_the_lattice_and_keeps_the_sector():
    """A zeroed score net makes the lift a pure transport test: the determinant
    sector still carries the coarse charge, and the SU(2) sector is sampled."""
    from u1_2d.model.schedule import GeometricNoiseSchedule
    from u1_2d.model.score_net import GaugeCovariantScoreNet
    from u2_2d.pipeline.ladder import generate_fine_from_coarse

    torch.manual_seed(27)
    coarse = retherm_sweeps(identity_links(6, batch=4, dtype=torch.float32),
                            WilsonU2Action(14.0), 40)
    model = GaugeCovariantScoreNet(hidden=8, depth=1, cond_channels=4).eval()
    fine = generate_fine_from_coarse(
        model, GeometricNoiseSchedule(0.05, 6.0), coarse, 56.0,
        n_su2_sweeps=3, n_sampler_steps=8, batch_size=4,
    )
    assert fine.shape == (4, 2, 12, 12, 5)
    assert torch.allclose(fine[..., 1:].norm(dim=-1), torch.ones_like(fine[..., 0]), atol=1e-5)
    assert torch.equal(topological_charge(fine), topological_charge(coarse))


# -------------------------------------------------------------------- validation

def test_measure_ensemble_reports_both_families():
    torch.manual_seed(28)
    ensemble = retherm_sweeps(identity_links(8, batch=12, dtype=torch.float64),
                              WilsonU2Action(20.0), 40)
    measured = measure_ensemble(ensemble, loops=((1, 1), (2, 2), (3, 3)))
    assert measured["plaquette"].shape == (12,)
    assert measured["det_plaquette"].shape == (12,)
    assert "wilson_2x2" in measured and "det_wilson_2x2" in measured
    assert measured["topological_charge"].shape == (12,)
    assert measured["plaquette"] == pytest.approx(measured["wilson_1x1"])


def test_exact_reference_covers_what_is_measured():
    reference = exact_reference(20.0, 8, loops=((1, 1), (2, 2)))
    assert reference["plaquette"] == pytest.approx(exact.plaquette_exact(20.0, 8))
    assert reference["wilson_1x1"] == pytest.approx(reference["plaquette"], rel=1e-8)
    assert "creutz_2" in reference and "det_wilson_2x2" in reference


def test_finite_volume_wilson_loop_matches_the_free_energy():
    """A = 1 by the torus character sum must equal dlogZ/dbeta -- independent routes."""
    for beta, size in ((3.5, 8), (26.4128, 16), (105.651, 32), (416.524, 64)):
        assert exact.wilson_loop_exact(beta, 1, lattice_size=size) == pytest.approx(
            exact.plaquette_exact(beta, size), rel=1e-8)
    assert exact.wilson_loop_exact(105.651, 0, lattice_size=32) == pytest.approx(1.0, abs=1e-9)


def test_finite_volume_corrections_vanish_with_volume():
    """The torus-wrapping correction is O(exp(-sigma (V - A))), not a perimeter term."""
    beta, area = 105.651, 16
    infinite = exact.wilson_loop_exact(beta, area)
    errors = [abs(exact.wilson_loop_exact(beta, area, lattice_size=L) / infinite - 1.0)
              for L in (16, 32, 64)]
    assert errors[0] > 1e-4                      # resolved at small volume
    assert errors[1] < errors[0] / 100.0         # and dies fast
    assert errors[2] < 1e-9
    # Creutz ratios are built from the same finite-volume loops, so a small
    # lattice and a large one disagree by a resolvable amount at fixed beta.
    near = exact_reference(beta, 64)["creutz_4"]
    far = exact_reference(beta, 16)["creutz_4"]
    assert abs(far / near - 1.0) > 1e-4


def test_compare_and_render_run_end_to_end():
    torch.manual_seed(29)
    action = WilsonU2Action(20.0)
    a = retherm_sweeps(identity_links(8, batch=16, dtype=torch.float64), action, 40)
    b = retherm_sweeps(identity_links(8, batch=16, dtype=torch.float64), action, 40)
    summary = compare(a, b, 20.0, 8, loops=((1, 1), (2, 2)))
    assert summary["n_generated"] == 16
    assert any(row["observable"] == "plaquette" for row in summary["rows"])
    assert abs(sum(e["exact"] for e in summary["sector_histogram"]) - 1.0) < 0.05
    text = render_markdown(summary)
    assert "topological sectors" in text and "plaquette" in text


def test_su2_sector_is_reconstructible_from_the_determinant_sector():
    """The load-bearing claim of the factorization: p(q | psi) needs no model.

    Take an equilibrated joint ensemble, throw its SU(2) sector away completely
    (replace it with Haar noise, which drops <(1/2)ReTr P> to ~0), keep only the
    determinant field, and run the exact conditional sampler. A handful of sweeps
    puts every full-U(2) observable back where it was, and Q never moves.
    """
    torch.manual_seed(31)
    beta, size, batch = 8.0, 6, 24
    action = WilsonU2Action(beta)
    joint = retherm_sweeps(identity_links(size, batch=batch, dtype=torch.float64),
                           action, 150, topological_updates=True)
    draws = [joint]
    for _ in range(6):
        joint = retherm_sweeps(joint, action, 3, topological_updates=True)
        draws.append(joint.clone())
    joint = torch.cat(draws, dim=0)

    psi = det_links(joint)
    scrambled = assemble_links(psi, random_links(size, batch=joint.shape[0],
                                                dtype=torch.float64)[..., 1:])
    assert abs(float(half_retr(plaquette(scrambled)).mean())) < 0.05
    assert torch.equal(topological_charge(scrambled), topological_charge(joint))

    from u2_2d.lgt.local_updates import conditional_su2_sweeps

    rebuilt = conditional_su2_sweeps(scrambled, action, 8)
    assert torch.equal(topological_charge(rebuilt), topological_charge(joint))
    # psi survives to floating-point precision: conditional_su2_sweeps is bitwise
    # exact on it, and the one wrap round-trip inside assemble_links is not.
    assert torch.allclose(torch.sin(det_links(rebuilt)), torch.sin(psi), atol=1e-12)
    for observable in (lambda x: half_retr(plaquette(x)),
                       lambda x: half_retr(wilson_loop(x, 2, 2))):
        assert float(observable(rebuilt).mean()) == pytest.approx(
            float(observable(joint).mean()), abs=0.01)
