import math

import torch

from su2_2d.lgt import group
from su2_2d.lgt.exact import plaquette_exact, plaquette_exact_bessel
from su2_2d.lgt.heat_kernel import exact_conditional_score, kernel_value, sample_angle
from su2_2d.lgt.lattice import gauge_transform, wilson_force
from su2_2d.model.noise import exact_score_target, noise_links, proxy_score_target
from su2_2d.model.score_head import SU2ScoreNet, assemble_score, plaquette_features


def _rand_su2(*shape, seed=0):
    gen = torch.Generator().manual_seed(seed)
    return group.random_haar(shape, generator=gen)


class TestExactReferences:
    def test_plaquette_quadrature_matches_bessel(self):
        for beta in (0.5, 2.0, 8.0):
            assert abs(plaquette_exact(beta) - plaquette_exact_bessel(beta)) < 1e-6


class TestHeatKernel:
    def test_normalization(self):
        # int K_s dHaar = 1 with class measure (2/pi) sin^2(theta)
        theta = torch.linspace(1e-4, math.pi - 1e-4, 20000, dtype=torch.float64)
        for s in (0.05, 0.3, 1.0):
            dens = kernel_value(theta, s) * torch.sin(theta) ** 2 * (2.0 / math.pi)
            integral = torch.trapz(dens, theta)
            assert abs(float(integral) - 1.0) < 1e-3

    def test_large_s_is_haar(self):
        theta = torch.linspace(0.2, math.pi - 0.2, 100)
        vals = kernel_value(theta, 25.0)
        assert (vals - 1.0).abs().max() < 1e-3

    def test_sampled_angle_matches_density_mean(self):
        s = 0.2
        gen = torch.Generator().manual_seed(0)
        samples = sample_angle(s, (200000,), generator=gen)
        theta = torch.linspace(1e-4, math.pi - 1e-4, 8192, dtype=torch.float64)
        dens = kernel_value(theta, s) * torch.sin(theta) ** 2
        mean_exact = float((theta * dens).sum() / dens.sum())
        assert abs(float(samples.mean()) - mean_exact) < 5e-3

    def test_proxy_close_to_exact_at_small_sigma(self):
        gen = torch.Generator().manual_seed(1)
        u0 = group.random_haar((512,), generator=gen)
        ut, omega = noise_links(u0, 0.1, generator=gen)
        exact = exact_score_target(ut, u0, 0.1)
        proxy = proxy_score_target(omega, 0.1)
        rel = float((proxy - exact).norm(dim=-1).mean() / exact.norm(dim=-1).mean())
        assert rel < 0.02

    def test_score_is_gradient_of_log_kernel(self):
        # autograd through the full composition U -> theta -> log K must agree
        # with the (1/2) dlogK n_hat closed form
        gen = torch.Generator().manual_seed(2)
        u0 = group.random_haar((16,), generator=gen)
        ut, _ = noise_links(u0, 0.4, generator=gen)
        s = 0.4 * 0.4
        score = exact_conditional_score(ut, u0, 0.4)

        x = ut.detach().double().requires_grad_(True)
        rel = group.mul(group.inverse(u0.double()), x)
        w = rel[..., 0].clamp(-1 + 1e-9, 1 - 1e-9)
        theta = torch.acos(w)
        val = torch.log(kernel_value(theta, s).clamp_min(1e-300)).sum()
        (dq,) = torch.autograd.grad(val, x)
        from su2_2d.lgt.lattice import project_tangent
        auto = project_tangent(dq, x)
        assert torch.allclose(score.double(), auto, atol=1e-4)


class TestScoreHead:
    def test_uniform_h_reproduces_boltzmann_score(self):
        field = _rand_su2(2, 2, 6, 6, seed=3)
        beta = 2.0
        h = torch.full((2, 6, 6), beta / 2.0)
        score = assemble_score(h, field)
        force = wilson_force(field, beta)
        assert torch.allclose(score, force, atol=1e-4)

    def test_gauge_covariance(self):
        field = _rand_su2(1, 2, 6, 6, seed=4)
        g = _rand_su2(1, 6, 6, seed=5)
        h = torch.rand(1, 6, 6, generator=torch.Generator().manual_seed(6))
        transformed = gauge_transform(field, g)
        s_orig = assemble_score(h, field)
        s_trans = assemble_score(h, transformed)
        # right-tangent coords at U rotate by Ad(g at the link's base site)
        expected_x = group.rotate_vector(g, s_orig[:, 0])
        expected_y = group.rotate_vector(g, s_orig[:, 1])
        assert torch.allclose(s_trans[:, 0], expected_x, atol=1e-4)
        assert torch.allclose(s_trans[:, 1], expected_y, atol=1e-4)

    def test_net_shapes_and_invariant_features(self):
        field = _rand_su2(3, 2, 8, 8, seed=7)
        g = _rand_su2(3, 8, 8, seed=8)
        feats = plaquette_features(field)
        feats_t = plaquette_features(gauge_transform(field, g))
        assert torch.allclose(feats, feats_t, atol=1e-5)
        net = SU2ScoreNet(hidden=16, depth=2)
        sigma = torch.full((3,), 0.3)
        beta = torch.full((3,), 2.0)
        out = net.score(field, sigma, beta)
        assert out.shape == (3, 2, 8, 8, 3)
