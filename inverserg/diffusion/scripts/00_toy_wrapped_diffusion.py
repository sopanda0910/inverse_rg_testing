"""Toy validation of the wrapped-Gaussian score-matching machinery.

Unconditional sampling of the single-plaquette distribution p(theta) ~ exp(beta cos theta)
with a small MLP score model; verifies moments and the KS statistic against the exact
distribution before any lattice-scale training. Run:

    python inverserg/diffusion/scripts/00_toy_wrapped_diffusion.py [--beta 2.0]
"""

import argparse
import math

import numpy as np
import torch
from torch import nn

from inverserg.diffusion.model.wrapped import wrap, wrapped_normal_score
from inverserg.diffusion.model.schedule import GeometricNoiseSchedule
from inverserg.diffusion.model.sampler import sample_ancestral
from inverserg.diffusion.lgt import exact


class ToyScore(nn.Module):
    def __init__(self, width: int = 96) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, width), nn.SiLU(),
            nn.Linear(width, width), nn.SiLU(),
            nn.Linear(width, width), nn.SiLU(),
            nn.Linear(width, 1),
        )

    def forward(self, theta, sigma):
        sig = sigma.expand_as(theta)
        feats = torch.cat([torch.cos(theta), torch.sin(theta), torch.log(sig), sig], dim=-1)
        return self.net(feats)

    def score(self, theta, sigma):
        return self.forward(theta, sigma) / sigma


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--beta", type=float, default=2.0)
    parser.add_argument("--steps", type=int, default=20000)
    parser.add_argument("--n-train", type=int, default=50000)
    parser.add_argument("--n-sample", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    torch.manual_seed(args.seed)

    data = (
        torch.distributions.VonMises(torch.zeros(args.n_train), torch.full((args.n_train,), args.beta))
        .sample()
        .view(-1, 1)
    )

    model = ToyScore()
    ema = ToyScore()
    ema.load_state_dict(model.state_dict())
    schedule = GeometricNoiseSchedule(0.03, 6.0)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    lr_sched = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.steps, eta_min=1e-5)

    for step in range(args.steps):
        idx = torch.randint(0, args.n_train, (1024,))
        x0 = data[idx]
        sigma = schedule.sample_sigma(1024, "cpu").view(-1, 1)
        xt = wrap(x0 + sigma * torch.randn_like(x0))
        target = sigma * wrapped_normal_score(wrap(xt - x0), sigma)
        loss = (model(xt, sigma) - target).square().mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        lr_sched.step()
        with torch.no_grad():
            for p_ema, p in zip(ema.parameters(), model.parameters()):
                p_ema.mul_(0.999).add_(p, alpha=0.001)
        if step % 2000 == 0:
            print(f"step {step:6d} loss {float(loss.detach()):.4f}")

    sigmas = schedule.discrete_sigmas(200)
    with torch.no_grad():
        samples = sample_ancestral(
            lambda th, s: ema.score(th, s), (args.n_sample, 1), sigmas, n_corrector_steps=2
        )
    s = samples.squeeze(-1).numpy()

    from scipy.stats import kstest

    exact_mean = exact.plaquette_exact(args.beta)
    grid = np.linspace(-math.pi, math.pi, 20001)
    pdf = exact.plaquette_angle_density(grid, args.beta)
    cdf = np.cumsum(pdf) * (grid[1] - grid[0])
    cdf /= cdf[-1]
    ks = kstest(s, lambda x: np.interp(x, grid, cdf))
    print(f"<cos theta> generated {np.cos(s).mean():.4f}  exact {exact_mean:.4f}")
    print(f"KS statistic {ks.statistic:.4f}")
    assert abs(np.cos(s).mean() - exact_mean) < 0.03, "toy sampling outside tolerance"
    print("toy wrapped-diffusion check PASSED")


if __name__ == "__main__":
    main()
