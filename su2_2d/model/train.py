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


def train(groups, config, checkpoint_path=None, seed=0, log_every=20):
    """Train ONE model across all (lattice size, beta) groups.

    groups: list of (data [N, 2, L, L, 4], betas [N]) — one entry per lattice
    size. The network is fully convolutional and `dsm_loss` evaluates
    per-sample, so sizes are trained jointly by drawing each step's batch from
    a randomly chosen group; this is the multi-size/continuous-beta discipline
    the U(1) study converged on. Training per size in separate calls would
    discard the earlier size (each call builds a fresh model).
    """
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
    conditional = config.get("conditional", True)
    best = math.inf

    val_slices = []
    for data, betas in groups:
        idx = torch.arange(0, data.shape[0], max(1, data.shape[0] // 4))
        val_slices.append((data[idx], betas[idx]))

    for step in range(1, n_steps + 1):
        g = int(torch.randint(0, len(groups), (1,), generator=gen))
        data, betas = groups[g]
        idx = torch.randint(0, data.shape[0], (batch_size,), generator=gen)
        loss = dsm_loss(model, data[idx], betas[idx], schedule, generator=gen,
                        conditional=conditional)
        opt.zero_grad()
        loss.backward()
        opt.step()
        with torch.no_grad():
            for p_ema, p in zip(ema.parameters(), model.parameters()):
                p_ema.mul_(decay).add_(p, alpha=1 - decay)
        if step % log_every == 0:
            # fixed-seed validation over EVERY group (EMA weights, matching
            # what gets saved -- the U(1) trainer's B1 bug was validating the
            # raw model while saving EMA)
            with torch.no_grad():
                vals = [float(dsm_loss(ema, vd, vb, schedule,
                                       generator=torch.Generator().manual_seed(12345),
                                       conditional=conditional))
                        for vd, vb in val_slices]
            val = sum(vals) / len(vals)
            detail = " ".join(f"L{d.shape[-2]}:{v:.4f}" for (d, _), v in zip(val_slices, vals))
            print(f"step {step}: loss {float(loss):.5f}  val(EMA) {val:.5f}  [{detail}]",
                  flush=True)
            if checkpoint_path is not None and val < best:
                best = val
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
