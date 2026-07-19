"""Gauge-covariant conditional score network for 2D U(1) link angles.

Exact gauge structure by construction, not by training loss:

1.  The network never sees raw link angles. Inputs are gauge-invariant channels
    (cos/sin of plaquette and 1x2 / 2x1 rectangle angles of the noisy fine links),
    so every internal activation is exactly invariant under fine gauge
    transformations.

2.  The output head produces one scalar h_p per plaquette, and the score is
    assembled as the lattice "curl"
        s_x(x, y) = h(x, y) - h(x, y-1)
        s_y(x, y) = h(x-1, y) - h(x, y),
    i.e. s_mu(x) = sum_p h_p  d theta_p / d theta_mu(x). This is precisely the
    form of the gradient of a gauge-invariant functional of plaquettes: the score
    is exactly invariant under gauge transformations of the input and exactly
    orthogonal to gauge orbits. (For our target p(fine | coarse invariants) the
    true score is of this form: the density is a function of fine plaquette
    angles only, and the wrapped heat kernel preserves that property at all t.)
    Wilson-action check: h_p = -beta sin(theta_p) reproduces the exact score of
    exp(-S_W) through this head.

3.  The coarse lattice enters only through gauge-invariant features of the
    *coarse* links (cos/sin of coarse plaquettes and coarse 2x2 loops), upsampled
    onto the fine grid (each coarse site covers its 2x2 fine cell) and
    concatenated at the input plus injected via FiLM at every block.

4.  beta and the noise level sigma enter through sinusoidal embeddings feeding
    per-block FiLM modulation.

Fully convolutional with circular padding: translation equivariant, runs on any L.
The network predicts the *scaled* score (approximately sigma * true score, an O(1)
quantity); divide by sigma to obtain the score.
"""

import math

import torch
from torch import nn

from ..lgt.lattice import plaquette_angles, rectangle_x_angles, rectangle_y_angles, wilson_loop_angles


def invariant_channels(theta: torch.Tensor) -> torch.Tensor:
    """[B, 2, L, L] links -> [B, 6, L, L] gauge-invariant features."""
    plaq = plaquette_angles(theta)
    rect_x = rectangle_x_angles(theta)
    rect_y = rectangle_y_angles(theta)
    return torch.stack(
        [
            torch.cos(plaq), torch.sin(plaq),
            torch.cos(rect_x), torch.sin(rect_x),
            torch.cos(rect_y), torch.sin(rect_y),
        ],
        dim=1,
    )


def coarse_conditioning_channels(
    coarse: torch.Tensor, fine_size: int, n_channels: int = 4
) -> torch.Tensor:
    """[B, 2, L/2, L/2] coarse links -> [B, n_channels, L, L] invariant conditioning.

    n_channels = 4: cos/sin of coarse plaquette and 2x2 loop angles (original set).
    n_channels = 5: adds the raw wrapped plaquette angle itself. cos/sin discard the
    winding count, so topology reaches the (locally receptive) network only weakly;
    the raw angle is the local winding density -- it sums to 2 pi Q_coarse -- giving
    the sampler direct access to where the coarse configuration carries its charge.
    """
    if coarse.dim() == 3:
        coarse = coarse.unsqueeze(0)
    plaq = plaquette_angles(coarse)
    loop22 = wilson_loop_angles(coarse, 2, 2)
    channels = [torch.cos(plaq), torch.sin(plaq), torch.cos(loop22), torch.sin(loop22)]
    if n_channels == 5:
        channels.append(plaq)
    elif n_channels != 4:
        raise ValueError(f"unsupported conditioning channel count: {n_channels}")
    feats = torch.stack(channels, dim=1)
    scale = fine_size // coarse.shape[-1]
    return feats.repeat_interleave(scale, dim=-2).repeat_interleave(scale, dim=-1)


def plaquette_curl(h: torch.Tensor) -> torch.Tensor:
    """[B, 1, L, L] per-plaquette scalars -> [B, 2, L, L] link field s_mu = sum_p h_p dp/dl."""
    h = h.squeeze(1)
    s_x = h - torch.roll(h, shifts=1, dims=-1)
    s_y = torch.roll(h, shifts=1, dims=-2) - h
    return torch.stack([s_x, s_y], dim=1)


class SinusoidalEmbedding(nn.Module):
    def __init__(self, dim: int, max_period: float = 1e4) -> None:
        super().__init__()
        self.dim = dim
        self.max_period = max_period

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        half = self.dim // 2
        freqs = torch.exp(
            -math.log(self.max_period) * torch.arange(half, device=x.device, dtype=x.dtype) / half
        )
        args = x[:, None] * freqs[None, :] * 100.0
        return torch.cat([torch.sin(args), torch.cos(args)], dim=-1)


class FiLMResBlock(nn.Module):
    def __init__(self, channels: int, emb_dim: int, kernel_size: int = 3) -> None:
        super().__init__()
        pad = kernel_size // 2
        self.conv1 = nn.Conv2d(channels, channels, kernel_size, padding=pad, padding_mode="circular")
        self.conv2 = nn.Conv2d(channels, channels, kernel_size, padding=pad, padding_mode="circular")
        self.norm1 = nn.GroupNorm(8, channels)
        self.norm2 = nn.GroupNorm(8, channels)
        self.film = nn.Linear(emb_dim, 2 * channels)
        self.act = nn.SiLU()

    def forward(self, x: torch.Tensor, emb: torch.Tensor) -> torch.Tensor:
        scale, shift = self.film(emb).chunk(2, dim=-1)
        h = self.act(self.norm1(self.conv1(x)))
        h = h * (1.0 + scale[:, :, None, None]) + shift[:, :, None, None]
        h = self.norm2(self.conv2(h))
        return self.act(x + h)


class GaugeCovariantScoreNet(nn.Module):
    def __init__(
        self,
        hidden: int = 64,
        depth: int = 4,
        emb_dim: int = 128,
        cond_channels: int = 4,
        kernel_size: int = 3,
    ) -> None:
        super().__init__()
        self.cond_channels = cond_channels
        self.sigma_embed = SinusoidalEmbedding(emb_dim // 2)
        self.beta_embed = SinusoidalEmbedding(emb_dim // 2)
        self.emb_mlp = nn.Sequential(
            nn.Linear(emb_dim, emb_dim), nn.SiLU(), nn.Linear(emb_dim, emb_dim)
        )
        in_channels = 6 + cond_channels
        pad = kernel_size // 2
        self.stem = nn.Conv2d(in_channels, hidden, kernel_size, padding=pad, padding_mode="circular")
        self.blocks = nn.ModuleList(
            FiLMResBlock(hidden, emb_dim, kernel_size) for _ in range(depth)
        )
        self.head = nn.Conv2d(hidden, 1, kernel_size, padding=pad, padding_mode="circular")
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        self.force_gate = nn.Linear(emb_dim, 1)
        nn.init.zeros_(self.force_gate.weight)
        nn.init.zeros_(self.force_gate.bias)

    def _embedding(self, sigma: torch.Tensor, beta: torch.Tensor) -> torch.Tensor:
        emb = torch.cat([self.sigma_embed(torch.log(sigma)), self.beta_embed(torch.log(beta))], dim=-1)
        return self.emb_mlp(emb)

    def forward(
        self,
        theta: torch.Tensor,
        sigma: torch.Tensor,
        beta: torch.Tensor,
        cond: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Returns the scaled score (~ sigma * score), shape [B, 2, L, L].

        theta: [B, 2, L, L] noisy fine links; sigma, beta: [B] (or scalar tensors);
        cond: [B, cond_channels, L, L] invariant coarse features (zeros if None).
        """
        batch, _, size, _ = theta.shape
        sigma = sigma.expand(batch) if sigma.dim() <= 1 and sigma.numel() == 1 else sigma
        beta = beta.expand(batch) if beta.dim() <= 1 and beta.numel() == 1 else beta
        if cond is None:
            cond = torch.zeros(batch, self.cond_channels, size, size, device=theta.device, dtype=theta.dtype)
        feats = torch.cat([invariant_channels(theta), cond], dim=1)
        sigma = sigma.reshape(batch)
        beta = beta.reshape(batch)
        emb = self._embedding(sigma, beta)
        x = self.stem(feats)
        for block in self.blocks:
            x = block(x, emb)
        h = self.head(x)
        # Gated analytic Wilson force: at sigma -> 0 the exact scaled score is
        # sigma * curl(-beta sin theta_p); the gate learns its (sigma, beta) envelope.
        gate = self.force_gate(emb).view(batch, 1, 1, 1)
        plaq = plaquette_angles(theta)
        analytic = -(beta.view(-1, 1, 1) * sigma.view(-1, 1, 1)) * torch.sin(plaq)
        h = h + gate * analytic.unsqueeze(1)
        return plaquette_curl(h)

    def score(
        self,
        theta: torch.Tensor,
        sigma: torch.Tensor,
        beta: torch.Tensor,
        cond: torch.Tensor | None = None,
    ) -> torch.Tensor:
        sigma_b = sigma.reshape(-1, 1, 1, 1) if sigma.dim() > 0 else sigma
        return self.forward(theta, sigma, beta, cond) / sigma_b
