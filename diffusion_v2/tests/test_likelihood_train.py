"""Tests for the differentiable ODE-likelihood training path (Tiers 2/3)."""

import math

import torch

from diffusion_v2.model.likelihood import ode_log_likelihood
from diffusion_v2.model.likelihood_train import (
    integrate_with_divergence,
    ml_conditional_log_likelihood,
    reverse_kl_terms,
)
from diffusion_v2.model.schedule import GeometricNoiseSchedule
from diffusion_v2.model.score_net import GaugeCovariantScoreNet
from diffusion_v2.model.wrapped import wrap, wrapped_normal_score


def tiny_model(seed=0):
    torch.manual_seed(seed)
    return GaugeCovariantScoreNet(hidden=8, depth=1, cond_channels=4)


class TestIntegrator:
    def test_matches_eval_integrator_on_analytic_score(self):
        # Same wrapped-Gaussian analytic score as the eval-path test; the
        # differentiable integrator (Hutchinson) must agree with the exact-
        # divergence eval integrator up to probe noise, which averages out
        # over the batch.
        s0 = 0.8

        def score_fn(theta, sigma):
            width = torch.sqrt(torch.as_tensor(s0) ** 2 + sigma**2)
            return wrapped_normal_score(theta, width)

        sigmas_asc = torch.flip(GeometricNoiseSchedule(0.05, 6.0).discrete_sigmas(40), dims=[0])
        torch.manual_seed(2)
        x0 = wrap(torch.randn(16, 2, 4, 4) * s0)
        n_dof = 2 * 4 * 4

        torch.manual_seed(7)
        _, acc = integrate_with_divergence(score_fn, x0, sigmas_asc, n_probes=4)
        log_q_diff = -n_dof * math.log(2.0 * math.pi) + acc
        log_q_exact = ode_log_likelihood(score_fn, x0, sigmas_asc, n_probes=0)
        assert abs(float((log_q_diff - log_q_exact).mean())) < 1.0

    def test_ml_loss_gradients_flow(self):
        model = tiny_model()
        schedule = GeometricNoiseSchedule(0.05, 6.0)
        torch.manual_seed(1)
        coarse = wrap(torch.randn(2, 2, 4, 4))
        fine = wrap(torch.randn(2, 2, 8, 8) * 0.5)
        log_q = ml_conditional_log_likelihood(
            model, schedule, coarse, fine, beta_target=3.0, n_steps=4, n_probes=1
        )
        loss = -log_q.mean() / fine[0].numel()
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        assert grads, "no parameter received a gradient"
        total = sum(float(g.abs().sum()) for g in grads)
        assert math.isfinite(total) and total > 0

    def test_reverse_kl_gradients_flow(self):
        model = tiny_model(seed=3)
        schedule = GeometricNoiseSchedule(0.05, 6.0)
        torch.manual_seed(4)
        coarse = wrap(torch.randn(2, 2, 4, 4))
        x0, log_q = reverse_kl_terms(
            model, schedule, coarse, beta_target=3.0, n_steps=4, n_probes=1
        )
        assert x0.shape == (2, 2, 8, 8)
        fake_action = (3.0 * (1.0 - torch.cos(x0))).flatten(1).sum(dim=1)
        loss = (fake_action + log_q).mean() / x0[0].numel()
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        total = sum(float(g.abs().sum()) for g in grads)
        assert math.isfinite(total) and total > 0
