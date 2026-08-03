import math

import torch

from su2_2d.lgt import group
from su2_2d.lgt.exact import plaquette_exact, plaquette_exact_bessel
from su2_2d.lgt.heat_kernel import exact_conditional_score, kernel_value, sample_angle
from su2_2d.lgt.lattice import gauge_transform, wilson_force
from su2_2d.model.noise import exact_score_target, noise_links, proxy_score_target
from su2_2d.model.score_head import SU2ScoreNet, assemble_score, plaquette_features
from su2_2d.model.train import coarse_conditioning


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


class TestKernelRepresentations:
    def test_dual_matches_character_in_overlap(self):
        from su2_2d.lgt.heat_kernel import _log_kernel_character, _log_kernel_dual

        th = torch.linspace(0.05, math.pi - 0.05, 200, dtype=torch.float64)
        for s in (2.0, 4.0, 8.0):
            sv = torch.full_like(th, s)
            assert float((_log_kernel_dual(th, sv) - _log_kernel_character(th, sv)).abs().max()) < 1e-8

    def test_dual_survives_tiny_s_where_characters_cannot(self):
        # at s = 0.02 the kernel is ~e^-900 near theta = pi; the character sum
        # cannot represent that by cancellation in float64, the dual can
        from su2_2d.lgt.heat_kernel import _log_kernel_dual

        th = torch.tensor([3.0], dtype=torch.float64)
        v = _log_kernel_dual(th, torch.tensor([0.02], dtype=torch.float64))
        assert torch.isfinite(v).all() and float(v) < -100

    def test_normalization_across_scales(self):
        g = torch.linspace(1e-5, math.pi - 1e-5, 20000, dtype=torch.float64)
        for s in (0.02, 0.5, 5.0, 25.0):
            v = kernel_value(g, torch.full_like(g, s)) * torch.sin(g) ** 2 * (2 / math.pi)
            assert abs(float(torch.trapz(v, g)) - 1.0) < 2e-3

    def test_per_config_sigma_matches_scalar_calls(self):
        from su2_2d.lgt.heat_kernel import exact_conditional_score

        gen = torch.Generator().manual_seed(3)
        u0 = group.random_haar((4, 2, 4, 4), generator=gen)
        ut = group.random_haar((4, 2, 4, 4), generator=gen)
        sig = torch.tensor([0.1, 0.3, 0.7, 1.4])
        batched = exact_conditional_score(ut, u0, sig)
        for i in range(4):
            one = exact_conditional_score(ut[i:i + 1], u0[i:i + 1], float(sig[i]))
            assert torch.allclose(batched[i:i + 1], one, atol=1e-5)


class TestAugmentation:
    def test_d4_preserves_the_action(self):
        from su2_2d.lgt.lattice import wilson_action
        from su2_2d.model.augment import d4_element

        f = _rand_su2(2, 2, 8, 8, seed=21)
        s0 = wilson_action(f, 2.0)
        for k in range(8):
            assert float((wilson_action(d4_element(f, k), 2.0) - s0).abs().max()) < 1e-4

    def test_d4_is_an_involution_pairwise(self):
        from su2_2d.model.augment import flip_x, flip_y, transpose_xy

        f = _rand_su2(1, 2, 8, 8, seed=22)
        for op in (flip_x, flip_y, transpose_xy):
            assert torch.allclose(op(op(f)), f, atol=1e-5)


class TestScheduleBetaAware:
    def test_floor_scales_with_beta(self):
        from su2_2d.model.schedule import GeometricNoiseSchedule

        s = GeometricNoiseSchedule(0.05, 2.5, sigma_min_beta_coef=0.3)
        lo_weak = float(s.effective_sigma_min(1.0))
        lo_strong = float(s.effective_sigma_min(64.0))
        assert lo_strong < lo_weak <= 0.05 + 1e-9
        assert abs(lo_strong - 0.3 / 8.0) < 1e-6

    def test_high_beta_bias_shifts_mass_to_small_sigma(self):
        from su2_2d.model.schedule import GeometricNoiseSchedule

        s = GeometricNoiseSchedule(0.05, 2.5, sigma_min_beta_coef=0.3)
        beta = torch.full((4000,), 32.0)
        g = torch.Generator().manual_seed(1)
        plain = s.sample_sigma(4000, generator=g, beta=beta, high_beta_bias=0.0)
        biased = s.sample_sigma(4000, generator=g, beta=beta, high_beta_bias=0.5)
        assert float(biased.median()) < float(plain.median())


class TestTrainingPath:
    def test_score_target_works_under_no_grad(self):
        # the trainer computes EMA validation inside torch.no_grad(); the
        # exact score's internal autograd must still run there
        gen = torch.Generator().manual_seed(9)
        u0 = group.random_haar((4,), generator=gen)
        ut, _ = noise_links(u0, 0.3, generator=gen)
        with torch.no_grad():
            target = exact_score_target(ut, u0, 0.3)
        assert torch.isfinite(target).all()

    def test_train_optimizes_one_model_across_sizes(self):
        from su2_2d.model.train import train

        gen = torch.Generator().manual_seed(10)
        groups = [
            (group.random_haar((6, 2, 4, 4), generator=gen), torch.full((6,), 2.0)),
            (group.random_haar((6, 2, 8, 8), generator=gen), torch.full((6,), 4.0)),
        ]
        cfg = {"hidden": 8, "depth": 1, "train_steps": 4, "batch_size": 2,
               "conditional": True, "lr": 1e-3}
        before = None
        model, schedule = train(groups, cfg, checkpoint_path=None, seed=0, log_every=100)
        assert schedule.sigma_max > schedule.sigma_min
        # a single model handled both sizes without a shape error
        for data, betas in groups:
            out = model.score(data[:1], torch.full((1,), 0.4), betas[:1],
                              coarse_conditioning(data[:1]))
            assert out.shape == (1, 2, data.shape[-2], data.shape[-2], 3)


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
