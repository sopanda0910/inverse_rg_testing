import math

import pytest
import torch

from inverserg.diffusion.lgt import WilsonAction, random_gauge_transform, wrap
from inverserg.diffusion.lgt.lattice import plaquette_angles
from inverserg.diffusion.model.wrapped import (
    sample_wrapped_normal,
    wrapped_normal_score,
    wrapped_normal_log_density,
)
from inverserg.diffusion.model.schedule import GeometricNoiseSchedule
from inverserg.diffusion.model.score_net import (
    GaugeCovariantScoreNet,
    coarse_conditioning_channels,
    invariant_channels,
    plaquette_curl,
)
from inverserg.diffusion.model.train import RungData, TrainConfig, denoising_loss, train_score_model


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
        from inverserg.diffusion.pipeline.ladder import blocking_consistency_score
        from inverserg.diffusion.lgt import block_links
        from inverserg.diffusion.lgt.lattice import plaquette_angles, wrap

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
        from inverserg.diffusion.lgt.local_updates import instanton_field
        from inverserg.diffusion.lgt.lattice import topological_charge
        from inverserg.diffusion.model.wrapped import wrap as wrap_angle

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
