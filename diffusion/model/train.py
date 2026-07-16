"""Denoising score matching on wrapped-Gaussian noise, multi-rung training."""

import math
from dataclasses import dataclass
from pathlib import Path

import torch

from ..lgt.lattice import TWO_PI, plaquette_angles
from .wrapped import wrap, wrapped_normal_score
from .schedule import GeometricNoiseSchedule
from .score_net import GaugeCovariantScoreNet, coarse_conditioning_channels


@dataclass
class RungData:
    """Paired data at one RG rung: fine configs and their blocked coarse partners."""

    name: str
    fine: torch.Tensor
    coarse: torch.Tensor
    beta: float

    @property
    def lattice_size(self) -> int:
        return self.fine.shape[-1]


@dataclass
class TrainConfig:
    epochs: int = 40
    batch_size: int = 32
    learning_rate: float = 2e-4
    sigma_min: float = 0.02
    sigma_max: float = 6.0
    hidden: int = 64
    depth: int = 4
    kernel_size: int = 3
    device: str = "cpu"
    seed: int = 0
    topo_weight: float = 0.0
    checkpoint_path: str | None = None
    log_every: int = 1
    ema_decay: float = 0.999
    cosine_lr: bool = True
    min_learning_rate: float = 1e-6


def soft_topological_charge(field: torch.Tensor) -> torch.Tensor:
    """Field-theoretic charge sum sin(theta_p) / 2*pi.

    Unlike the integer (geometric) charge, whose gradient w.r.t. the links vanishes
    almost everywhere, this surrogate is smooth: through the curl-form score head its
    gradient is the cos(theta_p)-weighted lattice Laplacian, which is nonzero exactly
    because sin is nonlinear. It approaches Q as plaquettes concentrate (large beta);
    comparing generated vs target values of the SAME estimator cancels its
    multiplicative renormalization at small beta.
    """
    return torch.sin(plaquette_angles(field)).sum(dim=(-2, -1)) / TWO_PI


def denoising_loss(
    model: GaugeCovariantScoreNet,
    fine: torch.Tensor,
    cond: torch.Tensor,
    beta: torch.Tensor,
    schedule: GeometricNoiseSchedule,
    sigma: torch.Tensor | None = None,
    topo_weight: float = 0.0,
    return_parts: bool = False,
) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """E || model_scaled_score - sigma * true kernel score ||^2 (targets are O(1)).

    With topo_weight > 0, adds a penalty tying the soft topological charge of the
    single-step denoised estimate theta_t + sigma * out to that of the clean target,
    weighted by 1 / (1 + sigma^2) since the posterior at large sigma cannot resolve
    the charge sector.
    """
    batch = fine.shape[0]
    if sigma is None:
        sigma = schedule.sample_sigma(batch, fine.device)
    sigma4 = sigma.view(-1, 1, 1, 1)
    theta_t = wrap(fine + sigma4 * torch.randn_like(fine))
    delta = wrap(theta_t - fine)
    target = sigma4 * wrapped_normal_score(delta, sigma4)
    out = model(theta_t, sigma, beta, cond)
    dsm = (out - target).square().mean()
    if topo_weight <= 0.0:
        if return_parts:
            return dsm, dsm, torch.zeros_like(dsm)
        return dsm
    denoised = theta_t + sigma4 * out
    q_err = soft_topological_charge(denoised) - soft_topological_charge(fine)
    topo = (q_err.square() / (1.0 + sigma.square())).mean()
    total = dsm + topo_weight * topo
    if return_parts:
        return total, dsm, topo
    return total


def _prepare_rung(rung: RungData, device: str) -> dict:
    fine = rung.fine.to(device).float()
    cond = coarse_conditioning_channels(rung.coarse.to(device).float(), rung.lattice_size)
    beta = torch.full((fine.shape[0],), float(rung.beta), device=device)
    return {"name": rung.name, "fine": fine, "cond": cond, "beta": beta}


def train_score_model(
    train_rungs: list[RungData],
    val_rungs: list[RungData],
    config: TrainConfig,
    model: GaugeCovariantScoreNet | None = None,
) -> tuple[GaugeCovariantScoreNet, list[dict]]:
    torch.manual_seed(config.seed)
    device = config.device
    if model is None:
        model = GaugeCovariantScoreNet(
            hidden=config.hidden, depth=config.depth, kernel_size=config.kernel_size
        )
    model = model.to(device)
    schedule = GeometricNoiseSchedule(config.sigma_min, config.sigma_max)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)

    train_data = [_prepare_rung(r, device) for r in train_rungs]
    val_data = [_prepare_rung(r, device) for r in val_rungs]
    history: list[dict] = []
    best_val = math.inf

    steps_per_epoch = sum(
        (d["fine"].shape[0] + config.batch_size - 1) // config.batch_size for d in train_data
    )
    lr_schedule = (
        torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, max(config.epochs * steps_per_epoch, 1), eta_min=config.min_learning_rate
        )
        if config.cosine_lr
        else None
    )
    ema_state = {k: v.detach().clone() for k, v in model.state_dict().items()}

    for epoch in range(config.epochs):
        model.train()
        losses = []
        all_batches = []
        for data in train_data:
            n = data["fine"].shape[0]
            perm = torch.randperm(n, device=device)
            all_batches.extend(
                (data, perm[i : i + config.batch_size]) for i in range(0, n, config.batch_size)
            )
        order = torch.randperm(len(all_batches))
        topo_losses = []
        for batch_index in order.tolist():
            data, idx = all_batches[batch_index]
            optimizer.zero_grad()
            loss, _, topo = denoising_loss(
                model, data["fine"][idx], data["cond"][idx], data["beta"][idx], schedule,
                topo_weight=config.topo_weight, return_parts=True,
            )
            topo_losses.append(float(topo.detach()))
            loss.backward()
            optimizer.step()
            if lr_schedule is not None:
                lr_schedule.step()
            with torch.no_grad():
                for key, value in model.state_dict().items():
                    if value.dtype.is_floating_point:
                        ema_state[key].mul_(config.ema_decay).add_(value, alpha=1.0 - config.ema_decay)
                    else:
                        ema_state[key].copy_(value)
            losses.append(float(loss.detach()))

        record = {"epoch": epoch, "train_loss": sum(losses) / max(len(losses), 1)}
        if config.topo_weight > 0.0:
            record["train_topo"] = sum(topo_losses) / max(len(topo_losses), 1)
        model.eval()
        val_total = 0.0
        gen = torch.Generator(device="cpu").manual_seed(12345)
        with torch.no_grad():
            for data in val_data:
                n = data["fine"].shape[0]
                sigma = schedule.sigma(torch.rand(n, generator=gen).to(device))
                vloss = float(
                    denoising_loss(
                        model, data["fine"], data["cond"], data["beta"], schedule, sigma=sigma,
                        topo_weight=config.topo_weight,
                    )
                )
                record[f"val_{data['name']}"] = vloss
                val_total += vloss
        record["val_total"] = val_total
        history.append(record)

        if config.checkpoint_path and (not val_data or val_total <= best_val):
            best_val = val_total
            save_checkpoint(ema_state, config, config.checkpoint_path)
        if config.log_every and epoch % config.log_every == 0:
            val_str = " ".join(f"{k}={v:.4f}" for k, v in record.items() if k.startswith("val_"))
            print(f"epoch {epoch:3d}  train={record['train_loss']:.4f}  {val_str}")

    model.load_state_dict(ema_state)
    model.eval()
    return model, history


def save_checkpoint(state_dict: dict, config: TrainConfig, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": state_dict,
            "model_kwargs": {
                "hidden": config.hidden,
                "depth": config.depth,
                "kernel_size": config.kernel_size,
            },
            "sigma_min": config.sigma_min,
            "sigma_max": config.sigma_max,
        },
        path,
    )


def load_checkpoint(path: str, device: str = "cpu") -> tuple[GaugeCovariantScoreNet, GeometricNoiseSchedule]:
    payload = torch.load(path, map_location=device, weights_only=True)
    model = GaugeCovariantScoreNet(**payload["model_kwargs"])
    model.load_state_dict(payload["model_state"])
    model.to(device).eval()
    schedule = GeometricNoiseSchedule(payload["sigma_min"], payload["sigma_max"])
    return model, schedule
