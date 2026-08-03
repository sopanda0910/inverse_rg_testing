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
from .augment import random_d4
from .noise import exact_score_target, noise_links
from .schedule import GeometricNoiseSchedule
from .score_head import SU2ScoreNet, plaquette_features


def coarse_conditioning(fine_shape_field: torch.Tensor) -> torch.Tensor:
    """Invariant features of the blocked field, upsampled to fine resolution."""
    coarse = block_links(fine_shape_field)
    feats = plaquette_features(coarse)
    return torch.repeat_interleave(torch.repeat_interleave(feats, 2, dim=-2), 2, dim=-1)


def dsm_loss(model, batch, beta, schedule, generator=None, conditional=True,
             augment=False, high_beta_bias=0.0):
    """Vectorized exact-heat-kernel DSM loss (no Python loop over the batch).

    sigma is drawn per configuration from the beta-aware floor, the whole
    batch is noised in one call, and the sigma^2 weighting balances the scales
    (the target grows like 1/sigma). D4 augmentation is applied to the clean
    configuration before noising, so conditioning and target stay consistent.
    """
    if augment:
        batch = random_d4(batch, generator)
    n = batch.shape[0]
    sigma = schedule.sample_sigma(n, generator=generator, beta=beta,
                                  high_beta_bias=high_beta_bias)
    u_t, _ = noise_links(batch, sigma, generator=generator)
    target = exact_score_target(u_t, batch, sigma)
    cond = coarse_conditioning(batch) if conditional else None
    pred = model.score(u_t, sigma, beta, cond)
    w = (sigma**2).view(-1, *([1] * (pred.dim() - 1)))
    return (w * (pred - target) ** 2).mean()


def train(groups, config, checkpoint_path=None, seed=0, log_every=20,
          heldout_groups=None):
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
        config.get("sigma_min", 0.05), config.get("sigma_max", 2.5),
        sigma_min_beta_coef=config.get("sigma_min_beta_coef", 0.3))
    augment = config.get("sym_augment", True)
    high_beta_bias = config.get("high_beta_sigma_bias", 0.0)
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

    def slices(gs, n_take=8):
        out = []
        for data, betas in gs or []:
            idx = torch.arange(0, data.shape[0], max(1, data.shape[0] // n_take))
            out.append((data[idx], betas[idx]))
        return out

    val_slices = slices(groups)
    heldout_slices = slices(heldout_groups)

    def evaluate(model_, sl):
        """Fixed-seed, EMA-weight evaluation (never augmented, so the number
        is comparable across steps)."""
        with torch.no_grad():
            return [float(dsm_loss(model_, d, b, schedule,
                                   generator=torch.Generator().manual_seed(12345),
                                   conditional=conditional, augment=False,
                                   high_beta_bias=high_beta_bias))
                    for d, b in sl]

    best_heldout = math.inf
    blocked = 0

    for step in range(1, n_steps + 1):
        g = int(torch.randint(0, len(groups), (1,), generator=gen))
        data, betas = groups[g]
        idx = torch.randint(0, data.shape[0], (batch_size,), generator=gen)
        loss = dsm_loss(model, data[idx], betas[idx], schedule, generator=gen,
                        conditional=conditional, augment=augment,
                        high_beta_bias=high_beta_bias)
        opt.zero_grad()
        loss.backward()
        opt.step()
        with torch.no_grad():
            for p_ema, p in zip(ema.parameters(), model.parameters()):
                p_ema.mul_(decay).add_(p, alpha=1 - decay)
        if step % log_every == 0:
            # fixed-seed validation on EMA weights -- the weights that get
            # saved (the U(1) trainer's B1 bug validated the raw model)
            vals = evaluate(ema, val_slices)
            val = sum(vals) / len(vals)
            detail = " ".join(f"L{d.shape[-3]}:{v:.4f}" for (d, _), v in zip(val_slices, vals))
            hout = evaluate(ema, heldout_slices) if heldout_slices else []
            hmean = sum(hout) / len(hout) if hout else None
            best_heldout = min(best_heldout, hmean) if hmean is not None else best_heldout

            # guarded save (U(1) script-22 protocol): improving the in-sample
            # validation is not enough -- a never-trained coupling must not
            # degrade, or we are just memorizing the training couplings
            save = checkpoint_path is not None and val < best
            if save and hmean is not None and hmean > 1.15 * best_heldout:
                save, blocked = False, blocked + 1
            msg = (f"step {step}: loss {float(loss):.5f}  val(EMA) {val:.5f}  [{detail}]")
            if hmean is not None:
                msg += f"  heldout {hmean:.5f}"
            if save:
                best = val
                save_checkpoint(ema, schedule, config, checkpoint_path)
                msg += "  *saved"
            elif checkpoint_path is not None and val < best:
                msg += "  (save BLOCKED by heldout guard)"
            print(msg, flush=True)
    if blocked:
        print(f"heldout guard blocked {blocked} save(s)", flush=True)
    return ema, schedule


def save_checkpoint(model, schedule, config, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "config": dict(config),
        "sigma_min": schedule.sigma_min,
        "sigma_max": schedule.sigma_max,
        "sigma_min_beta_coef": schedule.sigma_min_beta_coef,
    }, path)


def load_checkpoint(path):
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    config = ckpt["config"]
    model = SU2ScoreNet(
        hidden=config.get("hidden", 48), depth=config.get("depth", 4),
        cond_channels=2 if config.get("conditional", True) else 0)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    schedule = GeometricNoiseSchedule(
        ckpt["sigma_min"], ckpt["sigma_max"],
        sigma_min_beta_coef=ckpt.get("sigma_min_beta_coef", 0.3))
    return model, schedule
