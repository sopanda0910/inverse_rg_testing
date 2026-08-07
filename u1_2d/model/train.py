"""Denoising score matching on wrapped-Gaussian noise, multi-rung training."""

import math
from dataclasses import dataclass
from pathlib import Path

import torch

from ..lgt.blocking import block_links
from ..lgt.lattice import TWO_PI, plaquette_angles
from .wrapped import wrap, wrapped_normal_score
from .schedule import GeometricNoiseSchedule
from .score_net import GaugeCovariantScoreNet, coarse_conditioning_channels
from .symmetry import random_symmetry


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
    cond_channels: int = 4
    sigma_min_beta_coef: float | None = None
    device: str = "cpu"
    seed: int = 0
    topo_weight: float = 0.0
    checkpoint_path: str | None = None
    log_every: int = 1
    ema_decay: float = 0.999
    cosine_lr: bool = True
    min_learning_rate: float = 1e-6
    early_stop_patience: int = 0
    resume: bool = False
    snapshot_every: int = 10
    grad_clip_norm: float | None = 1.0
    high_beta_sigma_bias: float = 0.0
    sym_augment: float = 0.0
    norm_type: str = "group"
    cond_film: bool = False


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
    high_beta_sigma_bias: float = 0.0,
) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """E || model_scaled_score - sigma * true kernel score ||^2 (targets are O(1)).

    With topo_weight > 0, adds a penalty tying the soft topological charge of the
    single-step denoised estimate theta_t + sigma * out to that of the clean target,
    weighted by 1 / (1 + sigma^2) since the posterior at large sigma cannot resolve
    the charge sector.
    """
    batch = fine.shape[0]
    if sigma is None:
        sigma = schedule.sample_sigma(
            batch, fine.device, beta=beta, high_beta_bias=high_beta_sigma_bias
        )
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


def _prepare_rung(rung: RungData, device: str, cond_channels: int = 4) -> dict:
    fine = rung.fine.to(device).float()
    cond = coarse_conditioning_channels(
        rung.coarse.to(device).float(), rung.lattice_size, n_channels=cond_channels
    )
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
            hidden=config.hidden, depth=config.depth, kernel_size=config.kernel_size,
            cond_channels=config.cond_channels, norm_type=config.norm_type,
            cond_film=config.cond_film,
        )
    model = model.to(device)
    schedule = GeometricNoiseSchedule(
        config.sigma_min, config.sigma_max, sigma_min_beta_coef=config.sigma_min_beta_coef
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)

    train_data = [_prepare_rung(r, device, config.cond_channels) for r in train_rungs]
    val_data = [_prepare_rung(r, device, config.cond_channels) for r in val_rungs]
    history: list[dict] = []
    best_val = math.inf
    best_ema_state: dict | None = None

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

    snapshot_path = (
        Path(str(config.checkpoint_path) + ".resume") if config.checkpoint_path else None
    )
    start_epoch = 0
    best_epoch = -1
    if config.resume and snapshot_path and snapshot_path.exists():
        snap = torch.load(snapshot_path, map_location=device, weights_only=False)
        model.load_state_dict(snap["model_state"])
        ema_state = {k: v.to(device) for k, v in snap["ema_state"].items()}
        optimizer.load_state_dict(snap["optimizer_state"])
        if lr_schedule is not None and snap.get("lr_state") is not None:
            lr_schedule.load_state_dict(snap["lr_state"])
        history = snap["history"]
        best_val = snap["best_val"]
        best_epoch = snap["best_epoch"]
        start_epoch = snap["epoch"] + 1
        print(f"resuming from epoch {start_epoch} (best val {best_val:.4f} at {best_epoch})")

    # Flat views for the EMA update, built after any resume so they alias the live
    # tensors. state_dict() hands back detached views sharing storage with the
    # parameters, so in-place optimizer steps and load_state_dict() both stay visible
    # here. Two _foreach_ kernels replace ~200 per-tensor ops per step -- on GPU this
    # workload is launch-bound (many small rungs, small L), so it dominates.
    _live_state = model.state_dict()
    _float_keys = [k for k, v in _live_state.items() if v.dtype.is_floating_point]
    _ema_float = [ema_state[k] for k in _float_keys]
    _live_float = [_live_state[k] for k in _float_keys]
    _int_pairs = [
        (ema_state[k], v) for k, v in _live_state.items() if not v.dtype.is_floating_point
    ]

    for epoch in range(start_epoch, config.epochs):
        model.train()
        all_batches = []
        for data in train_data:
            n = data["fine"].shape[0]
            # Permutations drawn on CPU so a run visits batches in the same order on
            # CPU and GPU -- otherwise the two devices' RNG streams diverge and the
            # ported run cannot be checked against the reference one.
            perm = torch.randperm(n).to(data["fine"].device)
            all_batches.extend(
                (data, perm[i : i + config.batch_size]) for i in range(0, n, config.batch_size)
            )
        order = torch.randperm(len(all_batches))
        # Accumulated on-device: a float() per step would sync the GPU every batch.
        loss_sum = torch.zeros((), device=device)
        topo_sum = torch.zeros((), device=device)
        n_steps = 0
        for batch_index in order.tolist():
            data, idx = all_batches[batch_index]
            optimizer.zero_grad()
            fine_b, cond_b = data["fine"][idx], data["cond"][idx]
            if config.sym_augment > 0.0 and torch.rand(()) < config.sym_augment:
                # Exact action symmetries (D4 x charge conjugation). Blocking does
                # not commute with them cell-for-cell, so the coarse partner is
                # re-blocked from the transformed fine field.
                fine_b = random_symmetry(fine_b)
                cond_b = coarse_conditioning_channels(
                    block_links(fine_b), fine_b.shape[-1], n_channels=config.cond_channels
                )
            loss, _, topo = denoising_loss(
                model, fine_b, cond_b, data["beta"][idx], schedule,
                topo_weight=config.topo_weight, return_parts=True,
                high_beta_sigma_bias=config.high_beta_sigma_bias,
            )
            loss.backward()
            if config.grad_clip_norm is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip_norm)
            optimizer.step()
            if lr_schedule is not None:
                lr_schedule.step()
            with torch.no_grad():
                torch._foreach_mul_(_ema_float, config.ema_decay)
                torch._foreach_add_(_ema_float, _live_float, alpha=1.0 - config.ema_decay)
                for ema_buffer, live_buffer in _int_pairs:
                    ema_buffer.copy_(live_buffer)
                loss_sum += loss.detach()
                topo_sum += topo.detach()
            n_steps += 1

        record = {"epoch": epoch, "train_loss": float(loss_sum) / max(n_steps, 1)}
        if config.topo_weight > 0.0:
            record["train_topo"] = float(topo_sum) / max(n_steps, 1)
        model.eval()
        val_total = 0.0
        gen = torch.Generator(device="cpu").manual_seed(12345)
        # Validate the EMA weights -- they are what save_checkpoint ships, so
        # best-epoch selection and early stopping must measure the same curve.
        raw_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        model.load_state_dict(ema_state)
        # The manual_seed below reseeds every CUDA generator as well as the CPU one,
        # so the fork must cover this run's device -- with devices=[] a GPU run would
        # restart its training noise from seed 12345 after every validation pass.
        fork_devices = [torch.device(device).index or 0] if str(device).startswith("cuda") else []
        with torch.no_grad(), torch.random.fork_rng(devices=fork_devices):
            torch.manual_seed(12345)
            for data in val_data:
                n = data["fine"].shape[0]
                # beta passed so the validation noise distribution matches the
                # beta-aware training floor -- otherwise best-checkpoint selection
                # runs on a different sigma distribution than training.
                sigma = schedule.sigma(
                    torch.rand(n, generator=gen).to(device), beta=data["beta"]
                )
                vloss = float(
                    denoising_loss(
                        model, data["fine"], data["cond"], data["beta"], schedule, sigma=sigma,
                        topo_weight=config.topo_weight,
                    )
                )
                record[f"val_{data['name']}"] = vloss
                val_total += vloss
        model.load_state_dict(raw_state)
        record["val_total"] = val_total
        history.append(record)

        if not val_data or val_total <= best_val:
            best_val = val_total
            best_epoch = epoch
            best_ema_state = {k: v.detach().clone() for k, v in ema_state.items()}
            if config.checkpoint_path:
                save_checkpoint(ema_state, config, config.checkpoint_path)
        if config.log_every and epoch % config.log_every == 0:
            val_str = " ".join(f"{k}={v:.4f}" for k, v in record.items() if k.startswith("val_"))
            print(f"epoch {epoch:3d}  train={record['train_loss']:.4f}  {val_str}")
        if snapshot_path and config.snapshot_every and (epoch + 1) % config.snapshot_every == 0:
            torch.save({
                "epoch": epoch,
                "model_state": model.state_dict(),
                "ema_state": ema_state,
                "optimizer_state": optimizer.state_dict(),
                "lr_state": lr_schedule.state_dict() if lr_schedule is not None else None,
                "history": history,
                "best_val": best_val,
                "best_epoch": best_epoch,
            }, snapshot_path)
        if (config.early_stop_patience > 0 and val_data
                and epoch - best_epoch >= config.early_stop_patience):
            print(f"early stop at epoch {epoch}: no val improvement for "
                  f"{config.early_stop_patience} epochs (best {best_val:.4f} at {best_epoch})")
            break

    # Return the best-epoch EMA weights so the in-memory model matches the disk
    # checkpoint on early-stopped runs (resumed runs without an in-memory best
    # fall back to the final EMA, as before).
    model.load_state_dict(best_ema_state if best_ema_state is not None else ema_state)
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
                "cond_channels": config.cond_channels,
                "norm_type": config.norm_type,
                "cond_film": config.cond_film,
            },
            "sigma_min": config.sigma_min,
            "sigma_max": config.sigma_max,
            "sigma_min_beta_coef": config.sigma_min_beta_coef,
        },
        path,
    )


def load_checkpoint(path: str, device: str = "cpu") -> tuple[GaugeCovariantScoreNet, GeometricNoiseSchedule]:
    payload = torch.load(path, map_location=device, weights_only=True)
    model = GaugeCovariantScoreNet(**payload["model_kwargs"])
    model.load_state_dict(payload["model_state"])
    model.to(device).eval()
    schedule = GeometricNoiseSchedule(
        payload["sigma_min"], payload["sigma_max"],
        sigma_min_beta_coef=payload.get("sigma_min_beta_coef"),
    )
    return model, schedule
