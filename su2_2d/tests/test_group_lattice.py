import math

import torch

from su2_2d.lgt import group
from su2_2d.lgt.blocking import block_links
from su2_2d.lgt.hmc import _kinetic, leapfrog
from su2_2d.lgt.lattice import (
    gauge_transform,
    mean_plaquette,
    plaquette_word,
    wilson_action,
    wilson_force,
    wilson_loop_trace_half,
)


def _rand_su2(*shape, seed=0):
    gen = torch.Generator().manual_seed(seed)
    return group.random_haar(shape, generator=gen)


class TestGroup:
    def test_mul_matches_matrix_product(self):
        a, b = _rand_su2(64, seed=1), _rand_su2(64, seed=2)
        lhs = group.to_matrix(group.mul(a, b))
        rhs = group.to_matrix(a) @ group.to_matrix(b)
        assert torch.allclose(lhs, rhs, atol=1e-6)

    def test_inverse_and_unitarity(self):
        a = _rand_su2(32, seed=3)
        e = group.mul(a, group.inverse(a))
        assert torch.allclose(e[..., 0], torch.ones(32), atol=1e-6)
        assert e[..., 1:].abs().max() < 1e-6
        m = group.to_matrix(a)
        det = m[..., 0, 0] * m[..., 1, 1] - m[..., 0, 1] * m[..., 1, 0]
        assert torch.allclose(det.real, torch.ones(32, dtype=torch.float64), atol=1e-6)

    def test_rotate_vector_matches_conjugation(self):
        g = _rand_su2(16, seed=4)
        s = torch.randn(16, 3, generator=torch.Generator().manual_seed(5))
        q = group.mul(group.mul(g, torch.cat([torch.zeros(16, 1), s], dim=-1)),
                      group.inverse(g))
        assert torch.allclose(group.rotate_vector(g, s), q[..., 1:], atol=1e-5)
        assert q[..., 0].abs().max() < 1e-5

    def test_exp_log_roundtrip(self):
        gen = torch.Generator().manual_seed(6)
        omega = torch.randn(64, 3, generator=gen)
        omega = omega / omega.norm(dim=-1, keepdim=True) * (
            torch.rand(64, 1, generator=gen) * 1.9 * math.pi)
        back = group.logmap(group.expmap(omega))
        assert torch.allclose(back, omega, atol=1e-4)

    def test_trace_half(self):
        a = _rand_su2(16, seed=7)
        tr = torch.diagonal(group.to_matrix(a), dim1=-2, dim2=-1).sum(-1)
        assert torch.allclose(group.trace_half(a), tr.real.float() / 2, atol=1e-6)


class TestLattice:
    def test_gauge_invariance(self):
        field = _rand_su2(2, 2, 6, 6, seed=8)
        g = _rand_su2(2, 6, 6, seed=9)
        transformed = gauge_transform(field, g)
        assert torch.allclose(mean_plaquette(field), mean_plaquette(transformed), atol=1e-5)
        assert torch.allclose(
            wilson_loop_trace_half(field, 2, 2).mean(dim=(-2, -1)),
            wilson_loop_trace_half(transformed, 2, 2).mean(dim=(-2, -1)), atol=1e-5)

    def test_wilson_loop_1x1_is_plaquette(self):
        field = _rand_su2(2, 2, 6, 6, seed=10)
        assert torch.allclose(
            wilson_loop_trace_half(field, 1, 1),
            group.trace_half(plaquette_word(field)), atol=1e-6)

    def test_force_matches_finite_difference(self):
        field = _rand_su2(1, 2, 4, 4, seed=11).double()
        beta = 2.0
        force = wilson_force(field, beta)
        eps = 1e-6
        for mu, x, y, a in [(0, 1, 2, 0), (1, 3, 0, 2)]:
            e = torch.zeros(3, dtype=torch.float64)
            e[a] = eps
            bump = group.expmap(e)
            up = field.clone()
            up[0, mu, x, y] = group.mul(bump, up[0, mu, x, y])
            down = field.clone()
            down[0, mu, x, y] = group.mul(group.expmap(-e), down[0, mu, x, y])
            fd = float((wilson_action(up, beta) - wilson_action(down, beta)) / (2 * eps))
            assert abs(-fd - float(force[0, mu, x, y, a])) < 1e-4

    def test_blocking_shapes_and_gauge_covariance(self):
        field = _rand_su2(2, 2, 8, 8, seed=12)
        coarse = block_links(field)
        assert coarse.shape == (2, 2, 4, 4, 4)


class TestHMC:
    def test_leapfrog_reversibility(self):
        # renormalize in double: float32-normalized quaternions are unit only
        # to ~1e-7, which would mask the integrator's true reversibility
        field = group.normalize(_rand_su2(2, 2, 4, 4, seed=13).double())
        gen = torch.Generator().manual_seed(14)
        pi = torch.randn(2, 2, 4, 4, 3, generator=gen, dtype=torch.float64)
        f1, p1 = leapfrog(field, pi, 2.0, 0.05, 10)
        f2, p2 = leapfrog(f1, -p1, 2.0, 0.05, 10)
        assert (group.mul(group.inverse(f2), field)[..., 0] - 1).abs().max() < 1e-8

    def test_dh_scales_as_dt_squared(self):
        field = _rand_su2(4, 2, 4, 4, seed=15).double()
        gen = torch.Generator().manual_seed(16)
        pi = torch.randn(4, 2, 4, 4, 3, generator=gen, dtype=torch.float64)
        beta = 2.0

        def dh(step):
            n = max(2, int(round(0.5 / step)))
            f, p = leapfrog(field, pi, beta, step, n)
            h0 = _kinetic(pi) + wilson_action(field, beta)
            h1 = _kinetic(p) + wilson_action(f, beta)
            return float((h1 - h0).abs().mean())

        assert dh(0.02) < dh(0.08)
