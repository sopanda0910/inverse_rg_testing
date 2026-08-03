"""Denoising score matching on the exact SU(2) heat kernel.

Loss per sample, with the sigma^2 weighting that made the U(1) objective
scale-balanced:

    L = sigma^2 * | s_theta(U_t, sigma, beta[, cond]) - s_exact(U_t | U_0) |^2

s_exact is the exact conditional heat-kernel score (abelian-exactness carries
over: the SU(2) DSM target is exact because the kernel is known in closed
character form). EMA weights are what get saved — and, unlike the U(1) v2
trainer's original bug (audit B1), validation runs on the EMA weights too.
"""

import copy
import math
from pathlib import Path

import torch

from ..lgt.blocking import block_links
from .noise import exact_score_target, noise_links
from .schedule import GeometricNoiseSchedule
from .score_head import SU2ScoreNet, plaquette_features


def coarse_conditioning(fine_shape_field: torch.Tensor) -> torch.Tensor:
    """Invariant features of the blocked field, upsampled to fine resolution."""
    coarse = block_links(fine_shape_field)
    feats = plaquette_features(coarse)
    return torch.repeat_interleave(torch.repeat_interleave(feats, 2, dim=-2), 2, dim=-1)


def dsm_loss(model, batch, beta, schedule, generator=None, conditional=True):
    n = batch.shape[0]
    sigma = schedule.sample_sigma(n, generator=generator)
    losses = []
    for i in range(n):
        u0 = batch[i : i + 1]
        s = float(sigma[i])
        u_t, _ = noise_links(u0, s, generator=generator)
        target = exact_score_target(u_t, u0, s)
        cond = coarse_conditioning(u0) if conditional else None
        pred = model.score(u_t, sigma[i : i + 1], beta[i : i + 1], cond)
        losses.append(s * s * ((pred - target) ** 2).mean())
    return torch.stack(losses).mean()


def train(dataset, betas, config, checkpoint_path=None, seed=0, log_every=20):
    """dataset: [N, 2, L, L, 4]; betas: [N] coupling per config."""
    gen = torch.Generator().manual_seed(seed)
    schedule = GeometricNoiseSchedule(
        config.get("sigma_min", 0.05), config.get("sigma_max", 2.5))
    model = SU2ScoreNet(
        hidden=config.get("hidden", 48), depth=config.get("depth", 4),
        cond_channels=2 if config.get("conditional", True) else 0)
    ema = copy.deepcopy(model)
    opt = torch.optim.Adam(model.parameters(), lr=config.get("lr", 3e-4))
    decay = config.get("ema_decay", 0.999)
    n_steps = config.get("train_steps", 2000)
    batch_size = config.get("batch_size", 16)
    best = math.inf

    for step in range(1, n_steps + 1):
        idx = torch.randint(0, dataset.shape[0], (batch_size,), generator=gen)
        loss = dsm_loss(model, dataset[idx], betas[idx], schedule, generator=gen,
                        conditional=config.get("conditional", True))
        opt.zero_grad()
        loss.backward()
        opt.step()
        with torch.no_grad():
            for p_ema, p in zip(ema.parameters(), model.parameters()):
                p_ema.mul_(decay).add_(p, alpha=1 - decay)
        if step % log_every == 0:
            with torch.no_grad():
                val_idx = torch.arange(0, dataset.shape[0], max(1, dataset.shape[0] // 8))
                val = dsm_loss(ema, dataset[val_idx], betas[val_idx], schedule,
                               generator=torch.Generator().manual_seed(12345),
                               conditional=config.get("conditional", True))
            print(f"step {step}: loss {float(loss):.5f}  val(EMA) {float(val):.5f}", flush=True)
            if checkpoint_path is not None and float(val) < best:
                best = float(val)
                save_checkpoint(ema, schedule, config, checkpoint_path)
    return ema, schedule


def save_checkpoint(model, schedule, config, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "config": dict(config),
        "sigma_min": schedule.sigma_min,
        "sigma_max": schedule.sigma_max,
    }, path)


def load_checkpoint(path):
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    config = ckpt["config"]
    model = SU2ScoreNet(
        hidden=config.get("hidden", 48), depth=config.get("depth", 4),
        cond_channels=2 if config.get("conditional", True) else 0)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    schedule = GeometricNoiseSchedule(ckpt["sigma_min"], ckpt["sigma_max"])
    return model, schedule
