"""Actions, forces, local updates, winding moves and HMC."""

import math

import pytest
import torch
from scipy.special import ive

from u2_2d.lgt.actions import (
    DetSectorAction,
    WilsonU2Action,
    det_sector_plaquette_score,
    log_g0,
    make_action,
)
from u2_2d.lgt.hmc import BatchedHMCU2, adapted_hmc_params, u2_force
from u2_2d.lgt.lattice import (
    det_links,
    half_retr,
    identity_links,
    plaquette,
    random_links,
    topological_charge,
    u2_exp,
    u2_mul,
)
from u2_2d.lgt.local_updates import (
    apply_winding,
    central_winding_field,
    conditional_su2_sweeps,
    heatbath_sweep,
    metropolis_sweep,
    overrelaxation_sweep,
    retherm_sweeps,
    sample_su2_heatbath,
    sample_su2_scalar,
    set_topological_charge,
    winding_update,
)

SIZE, BATCH, BETA = 6, 4, 5.0


@pytest.fixture
def warm():
    torch.manual_seed(11)
    return retherm_sweeps(identity_links(SIZE, batch=BATCH, dtype=torch.float64),
                          WilsonU2Action(BETA), 30)


def test_action_is_minus_beta_sum_half_retr(warm):
    action = WilsonU2Action(BETA)
    expected = -BETA * half_retr(plaquette(warm)).sum(dim=(-2, -1))
    assert torch.allclose(action.per_config(warm), expected, atol=1e-12)
    assert torch.allclose(action(warm), expected.sum(), atol=1e-12)


def test_make_action_dispatch():
    assert isinstance(make_action("wilson_u2", 1.0), WilsonU2Action)
    assert isinstance(make_action("det_sector", 1.0), DetSectorAction)
    with pytest.raises(ValueError):
        make_action("nope", 1.0)


def test_log_g0_matches_bessel():
    z = torch.tensor([0.0, 1e-6, 0.5, 3.0, 40.0, 300.0], dtype=torch.float64)
    expected = torch.tensor(
        [0.0] + [math.log(2 * ive(1, float(v)) / float(v)) + float(v) for v in z[1:]],
        dtype=torch.float64,
    )
    assert torch.allclose(log_g0(z), expected, atol=1e-10)


def test_log_g0_gradient_is_the_bessel_ratio():
    z = torch.tensor([0.3, 2.0, 15.0, 120.0], dtype=torch.float64, requires_grad=True)
    log_g0(z).sum().backward()
    expected = torch.tensor([ive(2, float(v)) / ive(1, float(v)) for v in z.detach()],
                            dtype=torch.float64)
    assert torch.allclose(z.grad, expected, atol=1e-10)


def test_det_sector_score_is_the_gradient_of_its_log_weight():
    alpha = torch.linspace(-math.pi + 1e-4, math.pi - 1e-4, 51, dtype=torch.float64,
                           requires_grad=True)
    DetSectorAction(7.0).plaquette_log_weight(alpha).sum().backward()
    assert torch.allclose(alpha.grad, det_sector_plaquette_score(alpha.detach(), 7.0), atol=1e-10)


def test_det_sector_action_acts_on_the_determinant_field(warm):
    value = DetSectorAction(BETA).per_config(det_links(warm))
    assert value.shape == (BATCH,)
    assert torch.isfinite(value).all()


def test_analytic_force_matches_autograd(warm):
    action = WilsonU2Action(BETA)
    algebra = torch.zeros(warm.shape[:-1] + (4,), dtype=torch.float64, requires_grad=True)
    (grad,) = torch.autograd.grad(action.per_config(u2_mul(u2_exp(algebra), warm)).sum(), algebra)
    assert torch.allclose(u2_force(warm, BETA), grad, atol=1e-11)


def test_overrelaxation_is_microcanonical(warm):
    action = WilsonU2Action(BETA)
    assert torch.allclose(action.per_config(overrelaxation_sweep(warm)),
                          action.per_config(warm), atol=1e-9)


def test_overrelaxation_actually_moves_the_configuration(warm):
    assert not torch.allclose(overrelaxation_sweep(warm), warm, atol=1e-6)


@pytest.mark.parametrize("concentration", [0.2, 1.0, 4.0, 25.0])
def test_su2_scalar_sampler_matches_its_mean(concentration):
    torch.manual_seed(5)
    draws = sample_su2_scalar(torch.full((40000,), concentration, dtype=torch.float64))
    expected = ive(2, concentration) / ive(1, concentration)
    assert abs(float(draws.mean()) - expected) < 0.02
    assert bool((draws.abs() <= 1.0).all())


def test_su2_heatbath_concentrates_along_its_axis():
    torch.manual_seed(6)
    axis = torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64).expand(20000, 4)
    drawn = sample_su2_heatbath(axis.clone(), beta=8.0)
    assert torch.allclose(drawn.norm(dim=-1), torch.ones(20000, dtype=torch.float64), atol=1e-9)
    assert float(drawn[:, 3].mean()) > 0.8


def test_heatbath_and_metropolis_preserve_shapes_and_normalization(warm):
    for updated in (heatbath_sweep(warm, BETA),
                    metropolis_sweep(warm, WilsonU2Action(BETA))):
        assert updated.shape == warm.shape
        assert torch.allclose(updated[..., 1:].norm(dim=-1),
                              torch.ones_like(updated[..., 0]), atol=1e-9)


def test_conditional_su2_sampler_freezes_the_determinant_sector(warm):
    relaxed = conditional_su2_sweeps(warm, WilsonU2Action(BETA), 5)
    assert torch.equal(det_links(relaxed), det_links(warm))
    assert torch.equal(topological_charge(relaxed), topological_charge(warm))
    assert not torch.allclose(relaxed[..., 1:], warm[..., 1:], atol=1e-6)


def test_central_winding_field_is_the_u1_instanton():
    import u1_2d.lgt.lattice as u1_lattice

    field = central_winding_field(SIZE, dtype=torch.float64)
    angles = u1_lattice.plaquette_angles(field)
    assert torch.allclose(angles, torch.full_like(angles, 2 * math.pi / SIZE**2), atol=1e-12)


def test_central_winding_changes_charge_by_two_and_leaves_su2_alone():
    torch.manual_seed(12)
    cold = retherm_sweeps(identity_links(SIZE, batch=BATCH, dtype=torch.float64),
                          WilsonU2Action(60.0), 60)
    shifted = apply_winding(cold, torch.full((BATCH,), 2.0, dtype=torch.float64))
    assert torch.equal(topological_charge(shifted), topological_charge(cold) + 2)
    assert torch.equal(shifted[..., 1:], cold[..., 1:])


def test_odd_winding_must_move_the_su2_sector():
    """pi_1(U(2)) = Z but U(2) = (U(1) x SU(2)) / Z_2: odd Q forces the SU(2)
    plaquettes to multiply to -1, so no odd-charge move can be purely central."""
    torch.manual_seed(13)
    cold = retherm_sweeps(identity_links(SIZE, batch=BATCH, dtype=torch.float64),
                          WilsonU2Action(60.0), 60)
    shifted = apply_winding(cold, torch.ones(BATCH, dtype=torch.float64))
    assert torch.equal(topological_charge(shifted), topological_charge(cold) + 1)
    assert not torch.allclose(shifted[..., 1:], cold[..., 1:], atol=1e-6)


def test_set_topological_charge_hits_every_sector():
    torch.manual_seed(14)
    cold = retherm_sweeps(identity_links(SIZE, batch=BATCH, dtype=torch.float64),
                          WilsonU2Action(60.0), 60)
    targets = topological_charge(cold) + torch.tensor([0.0, 1.0, -2.0, 3.0], dtype=torch.float64)
    assert torch.equal(topological_charge(set_topological_charge(cold, targets)), targets)


def test_conditional_su2_relaxes_the_odd_winding_defect():
    """The odd-charge instanton leaves a large SU(2) action defect; the exact
    conditional sampler removes it without touching the sector it just reached."""
    torch.manual_seed(15)
    action = WilsonU2Action(20.0)
    cold = retherm_sweeps(identity_links(8, batch=8, dtype=torch.float64), action, 80)
    moved = set_topological_charge(cold, topological_charge(cold) + 1)
    before = float((action.per_config(moved) - action.per_config(cold)).mean())
    relaxed = conditional_su2_sweeps(moved, action, 25)
    after = float((action.per_config(relaxed) - action.per_config(cold)).mean())
    assert after < 0.4 * before
    assert torch.equal(topological_charge(relaxed), topological_charge(moved))


def test_winding_update_leaves_the_action_finite(warm):
    updated, accept = winding_update(warm, WilsonU2Action(BETA), charge_step=2)
    assert accept.shape == (BATCH,)
    assert torch.isfinite(WilsonU2Action(BETA).per_config(updated)).all()
    changed = topological_charge(updated) - topological_charge(warm)
    assert bool(((changed == 0) | (changed.abs() == 2)).all())


def test_adapted_hmc_params_keeps_trajectory_length_constant():
    for beta in (2.0, 8.0, 64.0, 512.0):
        step, n_steps = adapted_hmc_params(beta)
        assert 0.9 < step * n_steps / (0.2 * 5) < 1.15


def test_hmc_step_preserves_group_structure():
    torch.manual_seed(16)
    sampler = BatchedHMCU2(SIZE, WilsonU2Action(BETA), n_chains=BATCH, n_steps=4,
                           step_size=0.15)
    state = sampler.initialize()
    state, accept = sampler.metropolis_step(state)
    assert accept.shape == (BATCH,)
    assert torch.allclose(state[..., 1:].norm(dim=-1), torch.ones_like(state[..., 0]), atol=1e-5)
    assert bool((state[..., 0].abs() <= math.pi + 1e-5).all())


def test_hmc_integrator_is_second_order():
    """Omelyan is a second-order symplectic integrator, so at FIXED trajectory
    length dH falls as dt^2. The trajectory length has to be held fixed: dH
    oscillates along a trajectory, so shrinking dt at fixed n_steps compares two
    different endpoints and measures nothing."""
    torch.manual_seed(17)
    action = WilsonU2Action(BETA)
    state = retherm_sweeps(identity_links(SIZE, batch=2, dtype=torch.float64), action, 20)
    momenta = torch.randn(state.shape[:-1] + (4,), dtype=torch.float64)
    errors = []
    for step_size, n_steps in ((0.08, 8), (0.04, 16), (0.02, 32)):
        sampler = BatchedHMCU2(SIZE, action, n_chains=2, n_steps=n_steps, step_size=step_size)
        old = action.per_config(state) + 0.5 * momenta.square().sum(dim=(1, 2, 3, 4))
        new_state, new_momenta = sampler.omelyan(state.clone(), momenta.clone())
        new = action.per_config(new_state) + 0.5 * new_momenta.square().sum(dim=(1, 2, 3, 4))
        errors.append(float((new - old).abs().max()))
    for coarse, fine in zip(errors, errors[1:]):
        assert 0.2 < fine / coarse < 0.32


def test_hmc_integrator_is_reversible():
    """Flipping the momenta and re-integrating must return the starting point --
    the property Metropolis detailed balance rests on."""
    torch.manual_seed(19)
    action = WilsonU2Action(BETA)
    state = retherm_sweeps(identity_links(SIZE, batch=2, dtype=torch.float64), action, 20)
    momenta = torch.randn(state.shape[:-1] + (4,), dtype=torch.float64)
    sampler = BatchedHMCU2(SIZE, action, n_chains=2, n_steps=8, step_size=0.08)
    forward_state, forward_momenta = sampler.omelyan(state.clone(), momenta.clone())
    back_state, back_momenta = sampler.omelyan(forward_state.clone(), -forward_momenta)
    assert torch.allclose(back_state, state, atol=1e-11)
    assert torch.allclose(back_momenta, -momenta, atol=1e-11)


def test_hmc_reproduces_the_exact_plaquette():
    from u2_2d.lgt.exact import plaquette_exact

    torch.manual_seed(18)
    beta, size = 6.0, 6
    step, n_steps = adapted_hmc_params(beta)
    sampler = BatchedHMCU2(size, WilsonU2Action(beta), n_chains=24, n_steps=n_steps,
                           step_size=step, topological_updates=True)
    configs, stats = sampler.sample(20, burn_in=150, thin=3)
    measured = float(half_retr(plaquette(configs)).mean())
    assert stats.acceptance_rate > 0.6
    assert abs(measured - plaquette_exact(beta, size)) < 0.01
