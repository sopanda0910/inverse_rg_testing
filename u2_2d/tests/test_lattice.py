"""Group representation, geometry, gauge invariance and the determinant bridge."""

import math

import pytest
import torch

import u1_2d.lgt.blocking as u1_blocking
import u1_2d.lgt.lattice as u1_lattice
from u2_2d.lgt.blocking import block_links, blocked_det_plaquette_from_fine, half_link
from u2_2d.lgt.lattice import (
    det_links,
    det_phase,
    from_matrix,
    gauge_transform,
    half_imtr,
    half_retr,
    identity_links,
    link_environment,
    plaquette,
    plaquette_correlator,
    polyakov_loops,
    quat_mul,
    random_gauge_transform,
    random_links,
    set_det_links,
    su2_exp,
    su2_log,
    to_matrix,
    topological_charge,
    topological_charge_float,
    u2_conj,
    u2_exp,
    u2_log,
    u2_mul,
    wilson_loop,
    wrap,
)

SIZE, BATCH = 6, 3


@pytest.fixture
def links():
    torch.manual_seed(0)
    return random_links(SIZE, batch=BATCH, dtype=torch.float64)


def _roll(matrices, dx, dy):
    return torch.roll(matrices, shifts=(-dx, -dy), dims=(-4, -3))


def test_matrix_representation_round_trip(links):
    matrices = to_matrix(links)
    assert torch.allclose(to_matrix(from_matrix(matrices)), matrices, atol=1e-12)
    identity = torch.eye(2, dtype=torch.cdouble)
    assert torch.allclose(matrices @ matrices.mH, identity.expand_as(matrices), atol=1e-12)


def test_group_operations_are_matrix_operations(links):
    other = random_links(SIZE, batch=BATCH, dtype=torch.float64)
    assert torch.allclose(to_matrix(u2_mul(links, other)),
                          to_matrix(links) @ to_matrix(other), atol=1e-12)
    assert torch.allclose(to_matrix(u2_conj(links)), to_matrix(links).mH, atol=1e-12)


def test_quat_mul_is_associative_and_works_on_complex():
    torch.manual_seed(1)
    a, b, c = (torch.randn(5, 4, dtype=torch.cdouble) for _ in range(3))
    assert torch.allclose(quat_mul(quat_mul(a, b), c), quat_mul(a, quat_mul(b, c)), atol=1e-12)


def test_exp_log_round_trip():
    torch.manual_seed(2)
    algebra = 0.4 * torch.randn(32, 4, dtype=torch.float64)
    assert torch.allclose(u2_log(u2_exp(algebra)), algebra, atol=1e-12)
    su2 = 0.4 * torch.randn(32, 3, dtype=torch.float64)
    assert torch.allclose(su2_log(su2_exp(su2)), su2, atol=1e-12)


def test_su2_exp_is_stable_at_zero():
    tiny = torch.zeros(4, 3, dtype=torch.float64)
    result = su2_exp(tiny)
    assert torch.allclose(result[..., 0], torch.ones(4, dtype=torch.float64))
    assert torch.isfinite(result).all()


def test_plaquette_matches_explicit_matrix_product(links):
    matrices = to_matrix(links)
    m0, m1 = matrices[:, 0], matrices[:, 1]
    expected = m0 @ _roll(m1, 1, 0) @ _roll(m0, 0, 1).mH @ m1.mH
    assert torch.allclose(to_matrix(plaquette(links)), expected, atol=1e-12)


def test_trace_invariants(links):
    loop = plaquette(links)
    trace = to_matrix(loop)[..., 0, 0] + to_matrix(loop)[..., 1, 1]
    assert torch.allclose(half_retr(loop), 0.5 * trace.real, atol=1e-12)
    assert torch.allclose(half_imtr(loop), 0.5 * trace.imag, atol=1e-12)


def test_wilson_loop_1x1_is_the_plaquette(links):
    assert torch.allclose(to_matrix(wilson_loop(links, 1, 1)),
                          to_matrix(plaquette(links)), atol=1e-12)


def test_wilson_loop_of_identity_is_identity():
    field = identity_links(SIZE, batch=2, dtype=torch.float64)
    for extent in ((1, 1), (2, 3), (3, 3)):
        assert torch.allclose(half_retr(wilson_loop(field, *extent)),
                              torch.ones(2, SIZE, SIZE, dtype=torch.float64), atol=1e-12)


def test_gauge_invariance(links):
    gauged = random_gauge_transform(links)
    assert torch.allclose(half_retr(plaquette(gauged)), half_retr(plaquette(links)), atol=1e-12)
    assert torch.allclose(torch.sin(det_phase(plaquette(gauged))),
                          torch.sin(det_phase(plaquette(links))), atol=1e-12)
    assert torch.equal(topological_charge(gauged), topological_charge(links))
    for extent in ((2, 2), (3, 2)):
        assert torch.allclose(half_retr(wilson_loop(gauged, *extent)),
                              half_retr(wilson_loop(links, *extent)), atol=1e-12)


def test_su2_gauge_transformation_leaves_determinant_sector_alone(links):
    torch.manual_seed(3)
    gauge = random_links(SIZE, batch=BATCH, dtype=torch.float64)
    gauge = torch.cat([torch.zeros_like(gauge[..., :1]), gauge[..., 1:]], dim=-1)
    transformed = gauge_transform(links, gauge[:, 0])
    assert torch.allclose(torch.sin(det_links(transformed)),
                          torch.sin(det_links(links)), atol=1e-12)


def test_topological_charge_is_an_integer(links):
    assert torch.allclose(topological_charge_float(links), topological_charge(links), atol=1e-9)


def test_determinant_sector_is_a_u1_gauge_field(links):
    psi = det_links(links)
    assert psi.shape == (BATCH, 2, SIZE, SIZE)
    assert torch.allclose(torch.sin(u1_lattice.plaquette_angles(psi)),
                          torch.sin(det_phase(plaquette(links))), atol=1e-12)
    assert torch.equal(u1_lattice.topological_charge(psi), topological_charge(links))
    assert torch.allclose(torch.sin(u1_lattice.wilson_loop_angles(psi, 3, 2)),
                          torch.sin(det_phase(wilson_loop(links, 3, 2))), atol=1e-12)


def test_set_det_links_sets_the_determinant_and_keeps_su2(links):
    torch.manual_seed(4)
    target = wrap(torch.randn(BATCH, 2, SIZE, SIZE, dtype=torch.float64))
    updated = set_det_links(links, target)
    assert torch.allclose(torch.sin(det_links(updated)), torch.sin(target), atol=1e-12)
    assert torch.equal(updated[..., 1:], links[..., 1:])


def test_blocking_commutes_with_the_determinant(links):
    coarse = block_links(links)
    assert coarse.shape == (BATCH, 2, SIZE // 2, SIZE // 2, 5)
    assert torch.allclose(torch.sin(det_links(coarse)),
                          torch.sin(u1_blocking.block_links(det_links(links))), atol=1e-12)


def test_determinant_telescope_is_exact(links):
    coarse = block_links(links)
    assert torch.allclose(torch.sin(det_phase(plaquette(coarse))),
                          torch.sin(blocked_det_plaquette_from_fine(links)), atol=1e-12)


def test_half_link_squares_to_the_link(links):
    half = half_link(links)
    assert torch.allclose(to_matrix(u2_mul(half, half)), to_matrix(links), atol=1e-12)


def test_staple_sum_rule(links):
    environment = link_environment(links)
    total = environment[..., 0].real.sum(dim=(1, 2, 3))
    expected = 4.0 * half_retr(plaquette(links)).sum(dim=(-2, -1))
    assert torch.allclose(total, expected, atol=1e-9)


def test_polyakov_loops_of_identity():
    field = identity_links(SIZE, batch=2, dtype=torch.float64)
    loop_x, loop_y = polyakov_loops(field)
    assert torch.allclose(half_retr(loop_x), torch.ones_like(half_retr(loop_x)), atol=1e-12)
    assert torch.allclose(half_retr(loop_y), torch.ones_like(half_retr(loop_y)), atol=1e-12)


def test_unbatched_inputs_are_accepted(links):
    single = links[0]
    assert plaquette(single).shape == (SIZE, SIZE, 5)
    assert det_links(single).shape == (2, SIZE, SIZE)
    assert topological_charge(single).shape == ()
    assert block_links(single).shape == (2, SIZE // 2, SIZE // 2, 5)


def test_plaquette_correlator_shape(links):
    assert plaquette_correlator(links, 3).shape == (3,)


def test_wrap_range():
    values = torch.tensor([-3 * math.pi, -math.pi, 0.0, math.pi, 7.0], dtype=torch.float64)
    wrapped = wrap(values)
    assert bool((wrapped > -math.pi - 1e-12).all() and (wrapped <= math.pi + 1e-12).all())
    assert torch.allclose(torch.sin(wrapped), torch.sin(values), atol=1e-12)
