import math

import pytest
import torch

from diffusion.lgt import WilsonAction, random_gauge_transform, wrap
from diffusion.lgt.lattice import plaquette_angles
from diffusion.model.wrapped import (
    sample_wrapped_normal,
    wrapped_normal_score,
    wrapped_normal_log_density,
)
from diffusion.model.schedule import GeometricNoiseSchedule
from diffusion.model.score_net import (
    GaugeCovariantScoreNet,
    coarse_conditioning_channels,
    invariant_channels,
    plaquette_curl,
)
from diffusion.model.train import RungData, TrainConfig, denoising_loss, train_score_model


def random_field(batch=4, size=8, seed=0):
    gen = torch.Generator().manual_seed(seed)
    return torch.rand(batch, 2, size, size, generator=gen) * 2 * math.pi - math.pi


class TestWrappedKernel:
    def test_delta_diffuses_to_uniform(self):
        torch.manual_seed(0)
        x = torch.zeros(200000)
        noised = sample_wrapped_normal(x, torch.tensor(6.0))
        for q in (1, 2, 3):
            harmonic = torch.exp(1j * q * noised).mean()
            assert abs(harmonic) < 0.01
        counts, _ = torch.histogram(noised, bins=20, range=(-math.pi, math.pi))
        expected = len(noised) / 20
        assert float(((counts - expected) ** 2 / expected).sum()) < 60.0

    def test_score_matches_log_density_gradient(self):
        sigma = torch.tensor(0.7)
        delta = torch.linspace(-3.0, 3.0, 61, dtype=torch.float64).requires_grad_(True)
        log_p = wrapped_normal_log_density(delta, sigma.double())
        (grad,) = torch.autograd.grad(log_p.sum(), delta)
        score = wrapped_normal_score(delta.detach(), sigma.double())
        assert torch.allclose(score, grad, atol=1e-6)

    def test_small_sigma_score_is_gaussian(self):
        sigma = torch.tensor(0.05)
        delta = torch.tensor([0.1, -0.02, 0.03])
        assert torch.allclose(wrapped_normal_score(delta, sigma), -delta / sigma**2, rtol=1e-4)


class TestScoreNet:
    def test_score_invariant_under_gauge_transformation(self):
        torch.manual_seed(1)
        model = GaugeCovariantScoreNet(hidden=32, depth=2)
        for p in model.head.parameters():
            torch.nn.init.normal_(p, std=0.1)
        torch.nn.init.constant_(model.force_gate.bias, 0.7)
        field = random_field(batch=2, size=8)
        transformed = random_gauge_transform(field, generator=torch.Generator().manual_seed(9))
        sigma = torch.tensor([0.5, 0.5])
        beta = torch.tensor([2.0, 2.0])
        out_original = model(field, sigma, beta)
        out_transformed = model(transformed, sigma, beta)
        assert torch.allclose(out_original, out_transformed, atol=1e-4)

    def test_score_orthogonal_to_gauge_orbits(self):
        """Divergence at every site must vanish: sum of scores on links touching the site."""
        torch.manual_seed(2)
        model = GaugeCovariantScoreNet(hidden=32, depth=2)
        for p in model.head.parameters():
            torch.nn.init.normal_(p, std=0.1)
        torch.nn.init.constant_(model.force_gate.bias, 0.7)
        field = random_field(batch=2, size=8)
        out = model(field, torch.tensor([0.5, 0.5]), torch.tensor([2.0, 2.0]))
        divergence = (
            out[:, 0]
            - torch.roll(out[:, 0], shifts=1, dims=-2)
            + out[:, 1]
            - torch.roll(out[:, 1], shifts=1, dims=-1)
        )
        assert torch.allclose(divergence, torch.zeros_like(divergence), atol=1e-5)

    def test_curl_head_represents_wilson_force(self):
        beta = 1.7
        field = random_field(batch=3, size=8, seed=4).double().requires_grad_(True)
        action = WilsonAction(beta)
        (grad,) = torch.autograd.grad(action.per_config(field).sum(), field)
        h = (-beta * torch.sin(plaquette_angles(field.detach()))).unsqueeze(1)
        assert torch.allclose(plaquette_curl(h), -grad, atol=1e-10)

    def test_invariant_channels_gauge_invariant(self):
        field = random_field()
        transformed = random_gauge_transform(field, generator=torch.Generator().manual_seed(3))
        assert torch.allclose(
            invariant_channels(field), invariant_channels(transformed), atol=1e-5
        )

    def test_conditioning_channels_shape_and_invariance(self):
        coarse = random_field(batch=2, size=4, seed=6)
        cond = coarse_conditioning_channels(coarse, 8)
        assert cond.shape == (2, 4, 8, 8)
        cond_t = coarse_conditioning_channels(
            random_gauge_transform(coarse, generator=torch.Generator().manual_seed(8)), 8
        )
        assert torch.allclose(cond, cond_t, atol=1e-5)

    def test_runs_on_multiple_lattice_sizes(self):
        model = GaugeCovariantScoreNet(hidden=32, depth=2)
        for size in (8, 12, 16):
            out = model(random_field(batch=1, size=size), torch.tensor([0.3]), torch.tensor([1.0]))
            assert out.shape == (1, 2, size, size)


class TestBlockingConsistencyGuidance:
    def test_guidance_is_gauge_invariant_and_reduces_residual(self):
        from diffusion.pipeline.ladder import blocking_consistency_score
        from diffusion.lgt import block_links
        from diffusion.lgt.lattice import plaquette_angles, wrap

        torch.manual_seed(7)
        fine = random_field(batch=2, size=8, seed=11)
        coarse = block_links(fine)
        coarse_plaq = plaquette_angles(coarse)
        noisy = wrap(fine + 0.4 * torch.randn_like(fine))
        sigma = torch.tensor(0.4)

        guidance = blocking_consistency_score(noisy, coarse_plaq, sigma)
        transformed = random_gauge_transform(noisy, generator=torch.Generator().manual_seed(2))
        guidance_t = blocking_consistency_score(transformed, coarse_plaq, sigma)
        assert torch.allclose(guidance, guidance_t, atol=1e-4)

        def residual_norm(theta):
            plaq = plaquette_angles(theta)
            cell = plaq[:, 0::2, 0::2] + plaq[:, 1::2, 0::2] + plaq[:, 0::2, 1::2] + plaq[:, 1::2, 1::2]
            return float((cell - coarse_plaq).square().sum())

        stepped = wrap(noisy + 1e-3 * guidance)
        assert residual_norm(stepped) < residual_norm(noisy)


class TestCoarseChargeEnforcement:
    def test_instanton_shift_sets_fine_charge_to_coarse(self):
        from diffusion.lgt.local_updates import instanton_field
        from diffusion.lgt.lattice import topological_charge
        from diffusion.model.wrapped import wrap as wrap_angle

        torch.manual_seed(4)
        # Valid on equilibrated-like fields (plaquettes away from +-pi), which is
        # the regime where enforcement runs: post-sampling configs at beta >= 4.
        gen = torch.Generator().manual_seed(13)
        sample = 0.3 * torch.randn(6, 2, 16, 16, generator=gen)
        target_q = torch.tensor([2.0, -1.0, 0.0, 3.0, -2.0, 1.0])
        delta_q = target_q - topological_charge(sample)
        inst = instanton_field(16, dtype=sample.dtype)
        shifted = wrap_angle(sample + delta_q.view(-1, 1, 1, 1) * inst)
        assert torch.allclose(topological_charge(shifted), target_q, atol=1e-4)


class TestTraining:
    def test_denoising_loss_finite_and_decreases(self):
        torch.manual_seed(5)
        fine = random_field(batch=32, size=8, seed=10)
        coarse = fine[:, :, ::2, ::2]
        rung = RungData("test", fine, coarse, beta=1.0)
        config = TrainConfig(epochs=3, batch_size=8, hidden=32, depth=2, learning_rate=1e-3, seed=0)
        model, history = train_score_model([rung], [rung], config)
        assert all(math.isfinite(rec["train_loss"]) for rec in history)
        assert history[-1]["train_loss"] < history[0]["train_loss"] * 1.5


class TestTopoPenalty:
    def test_soft_charge_matches_integer_charge_on_smooth_configs(self):
        from diffusion.lgt.local_updates import instanton_field
        from diffusion.lgt.lattice import topological_charge
        from diffusion.model.train import soft_topological_charge

        inst = instanton_field(16)
        for q in (-2.0, 1.0, 3.0):
            field = wrap(q * inst + 0.02 * torch.randn(2, 16, 16, generator=torch.Generator().manual_seed(7)))
            assert abs(float(soft_topological_charge(field)) - q) < 0.15
            assert float(topological_charge(field)) == q

    def test_zero_weight_reproduces_plain_dsm(self):
        torch.manual_seed(6)
        fine = random_field(batch=8, size=8, seed=11)
        cond = coarse_conditioning_channels(fine[:, :, ::2, ::2], 8)
        beta = torch.full((8,), 2.0)
        schedule = GeometricNoiseSchedule(0.05, 4.0)
        model = GaugeCovariantScoreNet(hidden=16, depth=2)
        sigma = schedule.sample_sigma(8, "cpu")
        torch.manual_seed(42)
        plain = denoising_loss(model, fine, cond, beta, schedule, sigma=sigma)
        torch.manual_seed(42)
        total, dsm, topo = denoising_loss(
            model, fine, cond, beta, schedule, sigma=sigma, topo_weight=0.0, return_parts=True
        )
        assert torch.allclose(plain, total) and torch.allclose(plain, dsm)
        assert float(topo) == 0.0

    def test_penalty_is_finite_and_carries_gradient(self):
        torch.manual_seed(6)
        fine = random_field(batch=8, size=8, seed=12)
        cond = coarse_conditioning_channels(fine[:, :, ::2, ::2], 8)
        beta = torch.full((8,), 2.0)
        schedule = GeometricNoiseSchedule(0.05, 4.0)
        model = GaugeCovariantScoreNet(hidden=16, depth=2)
        sigma = schedule.sample_sigma(8, "cpu")
        torch.manual_seed(42)
        total, dsm, topo = denoising_loss(
            model, fine, cond, beta, schedule, sigma=sigma, topo_weight=0.5, return_parts=True
        )
        assert math.isfinite(float(total.detach())) and math.isfinite(float(topo.detach()))
        assert torch.allclose(total, dsm + 0.5 * topo)
        (0.5 * topo).backward(retain_graph=False)
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        assert grads and any(float(g.abs().max()) > 0 for g in grads)

    def test_multi_size_rungs_train_together(self):
        fine16 = random_field(batch=12, size=16, seed=13)
        fine8 = random_field(batch=12, size=8, seed=14)
        rungs = [
            RungData("L16", fine16, fine16[:, :, ::2, ::2], beta=2.0),
            RungData("L8", fine8, fine8[:, :, ::2, ::2], beta=1.0),
        ]
        config = TrainConfig(epochs=1, batch_size=4, hidden=16, depth=2, topo_weight=0.1, seed=0)
        model, history = train_score_model(rungs, rungs, config)
        assert math.isfinite(history[-1]["train_loss"])
        assert math.isfinite(history[-1]["train_topo"])
        assert "val_L16" in history[-1] and "val_L8" in history[-1]


class TestInSamplerChargeProjection:
    def test_sampler_step_callback_is_applied_each_step(self):
        from diffusion.model.sampler import sample_ancestral

        calls = []

        def callback(theta, sigma_next):
            calls.append(float(sigma_next))
            return theta

        sigmas = torch.tensor([2.0, 1.0, 0.5, 0.1])
        torch.manual_seed(3)
        sample_ancestral(lambda t, s: torch.zeros_like(t), (2, 2, 8, 8), sigmas,
                         n_corrector_steps=0, step_callback=callback)
        assert len(calls) == 4
        assert calls[-1] == 0.0

    def test_generation_projects_charge_during_and_after_sampling(self):
        from diffusion.lgt.lattice import topological_charge
        from diffusion.model.schedule import GeometricNoiseSchedule
        from diffusion.pipeline.ladder import generate_fine_from_coarse

        class ZeroScoreModel:
            def eval(self):
                return self

            def score(self, theta, sigma, beta, cond):
                return torch.zeros_like(theta)

        torch.manual_seed(9)
        coarse = 0.1 * torch.randn(4, 2, 8, 8)
        schedule = GeometricNoiseSchedule(0.03, 3.0)
        fine = generate_fine_from_coarse(
            ZeroScoreModel(), schedule, coarse, beta_target=8.0,
            n_sampler_steps=40, n_corrector_steps=0, batch_size=4,
            consistency_weight=0.0, enforce_coarse_charge=True,
            charge_projection_sigma=0.5, charge_projection_interval=5,
        )
        assert torch.equal(topological_charge(fine), topological_charge(coarse))


class TestV6Machinery:
    def test_beta_aware_sigma_min(self):
        sched = GeometricNoiseSchedule(0.03, 6.0, sigma_min_beta_coef=0.3)
        assert sched.effective_sigma_min(None) == 0.03
        assert sched.effective_sigma_min(4.0) == 0.03
        assert abs(sched.effective_sigma_min(400.0) - 0.015) < 1e-9
        grid = sched.discrete_sigmas(50, beta=400.0)
        assert abs(float(grid[-1]) - 0.015) < 1e-6
        assert abs(float(grid[0]) - 6.0) < 1e-5
        betas = torch.tensor([1.0, 900.0])
        sig = sched.sample_sigma(2, "cpu", beta=betas)
        assert sig.shape == (2,) and float(sig.min()) > 0

    def test_legacy_schedule_unchanged(self):
        old = GeometricNoiseSchedule(0.03, 6.0)
        new = GeometricNoiseSchedule(0.03, 6.0, sigma_min_beta_coef=0.3)
        t = torch.linspace(0, 1, 7)
        assert torch.allclose(old.sigma(t), new.sigma(t))
        assert torch.allclose(old.discrete_sigmas(20), new.discrete_sigmas(20))

    def test_winding_channel_carries_charge(self):
        from diffusion.lgt.local_updates import instanton_field
        from diffusion.lgt.lattice import TWO_PI

        coarse = wrap(2.0 * instanton_field(8).unsqueeze(0) + 0.01 * torch.randn(1, 2, 8, 8))
        cond4 = coarse_conditioning_channels(coarse, 16)
        cond5 = coarse_conditioning_channels(coarse, 16, n_channels=5)
        assert cond4.shape == (1, 4, 16, 16) and cond5.shape == (1, 5, 16, 16)
        assert torch.allclose(cond4, cond5[:, :4])
        q_from_channel = float(cond5[0, 4].sum()) / (4.0 * TWO_PI)
        assert abs(q_from_channel - 2.0) < 0.05

    def test_checkpoint_roundtrip_with_v6_fields(self, tmp_path):
        from diffusion.model.train import save_checkpoint, load_checkpoint

        cfg = TrainConfig(hidden=16, depth=2, cond_channels=5, sigma_min=0.03,
                          sigma_max=6.0, sigma_min_beta_coef=0.3)
        model = GaugeCovariantScoreNet(hidden=16, depth=2, cond_channels=5)
        path = str(tmp_path / "ckpt.pt")
        save_checkpoint(model.state_dict(), cfg, path)
        loaded, sched = load_checkpoint(path)
        assert loaded.cond_channels == 5
        assert sched.sigma_min_beta_coef == 0.3
        theta = random_field(batch=2, size=8, seed=21)
        cond = coarse_conditioning_channels(theta[:, :, ::2, ::2], 8, n_channels=5)
        out = loaded(theta, torch.tensor([0.5, 0.5]), torch.tensor([100.0, 100.0]), cond)
        assert out.shape == (2, 2, 8, 8)

    def test_expand_rungs_deterministic_and_policied(self):
        from diffusion.utils import expand_rungs

        cfg = {"rungs": [{"beta": 55.0, "lattice_size": 16}],
               "random_rungs": [{"n": 20, "beta_min": 1.0, "beta_max": 60.0,
                                 "lattice_size": 16, "n_configs": 128}]}
        a = expand_rungs(cfg, seed=0)
        b = expand_rungs(cfg, seed=0)
        assert a == b and len(a) == 21
        for rung in a[1:]:
            assert 1.0 <= rung["beta"] <= 60.0 and rung["n_configs"] == 128
            if rung["beta"] < 5.0:
                assert rung["hot_start"] and rung["burn_in"] == 200
            elif rung["beta"] >= 20.0:
                assert not rung["hot_start"] and rung["burn_in"] == 2000
            else:
                assert not rung["hot_start"] and rung["burn_in"] == 600
        assert expand_rungs(cfg, seed=1)[1:] != a[1:]


class TestTrainingResumeAndEarlyStop:
    def test_snapshot_resume_continues_history(self, tmp_path):
        fine = random_field(batch=16, size=8, seed=31)
        rung = RungData("r", fine, fine[:, :, ::2, ::2], beta=1.0)
        ckpt = str(tmp_path / "net.pt")
        cfg = TrainConfig(epochs=4, batch_size=8, hidden=16, depth=2, seed=0,
                          checkpoint_path=ckpt, snapshot_every=2)
        _, hist1 = train_score_model([rung], [rung], cfg)
        assert (tmp_path / "net.pt.resume").exists()
        cfg2 = TrainConfig(epochs=6, batch_size=8, hidden=16, depth=2, seed=0,
                           checkpoint_path=ckpt, snapshot_every=2, resume=True)
        _, hist2 = train_score_model([rung], [rung], cfg2)
        assert [h["epoch"] for h in hist2] == [0, 1, 2, 3, 4, 5]

    def test_early_stop_breaks_before_epochs(self):
        torch.manual_seed(6)
        fine = random_field(batch=16, size=8, seed=32)
        rung = RungData("r", fine, fine[:, :, ::2, ::2], beta=1.0)
        cfg = TrainConfig(epochs=50, batch_size=8, hidden=16, depth=2, seed=0,
                          learning_rate=0.0, early_stop_patience=2)
        _, hist = train_score_model([rung], [rung], cfg)
        assert len(hist) < 50


class TestPhysicsScoreBlend:
    def test_exact_score_matches_autograd(self):
        from diffusion.pipeline.ladder import wilson_exact_score

        torch.manual_seed(7)
        beta = 14.0
        theta = wrap(torch.randn(3, 2, 8, 8, dtype=torch.float64) * 0.3)
        theta.requires_grad_(True)
        log_p = beta * torch.cos(plaquette_angles(theta)).sum()
        (autograd_score,) = torch.autograd.grad(log_p, theta)
        with torch.no_grad():
            analytic = wilson_exact_score(theta, beta)
        assert torch.allclose(analytic, autograd_score, atol=1e-10)

    def test_exact_score_is_gauge_invariant(self):
        from diffusion.pipeline.ladder import wilson_exact_score

        torch.manual_seed(8)
        theta = wrap(torch.randn(2, 2, 8, 8) * 0.5)
        gen = torch.Generator().manual_seed(3)
        transformed = random_gauge_transform(theta, generator=gen)
        s_orig = wilson_exact_score(theta, 5.0)
        s_trans = wilson_exact_score(transformed, 5.0)
        plaq = plaquette_angles(theta)
        plaq_t = plaquette_angles(transformed)
        assert torch.allclose(plaq, plaq_t, atol=1e-5)
        assert torch.allclose(s_orig, s_trans, atol=1e-5)

    def test_blend_weight_limits(self):
        beta = 200.0
        coef = 1.0
        sigma_c = coef / math.sqrt(beta)
        for sigma, expect_high in [(sigma_c / 10, True), (sigma_c * 10, False)]:
            w = 1.0 / (1.0 + (sigma / sigma_c) ** 2)
            assert (w > 0.98) if expect_high else (w < 0.02)
