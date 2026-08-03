"""Gauge-covariant curl-head score network for SU(2), the non-abelian
counterpart of the U(1) curl parameterization.

A CNN maps gauge-INVARIANT plaquette features (trace and axis magnitude of
the plaquette word, plus sigma/beta embeddings and optional coarse
conditioning) to one scalar h per plaquette. The score at each link is then
assembled from the explicit tangent-derivative of tr P of the two adjacent
plaquettes:

    score_a(link) = sum_{p ni link} h_p * d/dt tr[ P_p(link -> e^{i t s_a/2} link) ]

For a plaquette word starting AT the link the derivative is -vec_a(P); for a
word containing the link inverted, cycle the word to start at the inverse and
the derivative is +vec_a(cycled word). With h_p = beta/2 uniform this
reproduces exactly -grad S (tested), so at sigma -> 0 the head can represent
the true Boltzmann score; gauge covariance is automatic because h is
invariant and the vec parts transform in the adjoint at the link's site.
"""

import torch
from torch import nn

from ..lgt import group
from ..lgt.lattice import X_DIM, Y_DIM, plaquette_word


def _vec(q: torch.Tensor) -> torch.Tensor:
    return q[..., 1:]


def _roll(t, shift, dim):
    return torch.roll(t, shifts=shift, dims=dim)


def assemble_score(h: torch.Tensor, field: torch.Tensor) -> torch.Tensor:
    """h [B, L, L] per-plaquette coefficients -> score [B, 2, L, L, 3]."""
    ux, uy = field[..., 0, :, :, :], field[..., 1, :, :, :]
    p = plaquette_word(field)
    hq = h.unsqueeze(-1)

    # All words are cycled to anchor at the LINK'S BASE SITE (x, y): a link
    # appearing non-inverted starts its word (derivative -vec), a link
    # appearing inverted ends its word (derivative +vec). Anchoring at the
    # base site is what makes the covariance rotation R(g(x,y)) match the
    # left-tangent basis at the link.

    # x-link at (x, y): P(x, y) = Ux(x,y) ... -> -vec(P);
    # from P(x, y-1), cycled with Ux(x,y)^-1 LAST:
    # V2 = Uy(x,y-1)^-1 Ux(x,y-1) Uy(x+1,y-1) Ux(x,y)^-1 -> +vec(V2).
    v2 = group.mul(group.inverse(_roll(uy, 1, Y_DIM)), _roll(ux, 1, Y_DIM))
    v2 = group.mul(v2, _roll(_roll(uy, 1, Y_DIM), -1, X_DIM))
    v2 = group.mul(v2, group.inverse(ux))
    score_x = -hq * _vec(p) + _roll(hq, 1, Y_DIM) * _vec(v2)

    # y-link at (x, y): P(x, y) already ends with Uy(x,y)^-1 -> +vec(P);
    # from P(x-1, y), cycled with Uy(x,y) FIRST:
    # W4 = Uy(x,y) Ux(x-1,y+1)^-1 Uy(x-1,y)^-1 Ux(x-1,y) -> -vec(W4).
    w4 = group.mul(uy, group.inverse(_roll(_roll(ux, 1, X_DIM), -1, Y_DIM)))
    w4 = group.mul(w4, group.inverse(_roll(uy, 1, X_DIM)))
    w4 = group.mul(w4, _roll(ux, 1, X_DIM))
    score_y = hq * _vec(p) - _roll(hq, 1, X_DIM) * _vec(w4)

    return torch.stack([score_x, score_y], dim=-4)


def plaquette_features(field: torch.Tensor) -> torch.Tensor:
    """Gauge-invariant per-plaquette channels [B, 2, L, L]."""
    p = plaquette_word(field)
    return torch.stack([p[..., 0], p[..., 1:].norm(dim=-1)], dim=-3)


class SU2ScoreNet(nn.Module):
    """Periodic CNN over invariant plaquette features -> per-plaquette h,
    FiLM-conditioned on (log sigma, log beta) and optional coarse features."""

    def __init__(self, hidden: int = 48, depth: int = 4, cond_channels: int = 0):
        super().__init__()
        self.cond_channels = cond_channels
        in_ch = 2 + cond_channels
        self.inp = nn.Conv2d(in_ch, hidden, 3, padding=1, padding_mode="circular")
        self.blocks = nn.ModuleList(
            nn.Conv2d(hidden, hidden, 3, padding=1, padding_mode="circular")
            for _ in range(depth)
        )
        # FiLM sees (log sigma, log beta) plus GLOBAL coarse summaries: a local
        # receptive field cannot reach lattice-wide coarse structure, which
        # U(1) found mattered (its analogue was the coarse winding sum)
        self.film = nn.Linear(2 + (2 if cond_channels else 0), 2 * hidden * (depth + 1))
        self.out = nn.Conv2d(hidden, 1, 3, padding=1, padding_mode="circular")
        nn.init.zeros_(self.out.weight)
        nn.init.zeros_(self.out.bias)

    def h_field(self, field, sigma, beta, cond=None):
        feats = plaquette_features(field)
        if cond is not None:
            feats = torch.cat([feats, cond], dim=-3)
        emb = [torch.log(sigma), torch.log(beta)]
        if cond is not None:
            emb.append(cond[..., 0, :, :].mean(dim=(-2, -1)))
            emb.append(cond[..., 1, :, :].mean(dim=(-2, -1)))
        film = self.film(torch.stack(emb, dim=-1))
        chunks = film.chunk(2 * (len(self.blocks) + 1), dim=-1)
        x = self.inp(feats)
        x = x * (1 + chunks[0][..., None, None]) + chunks[1][..., None, None]
        x = torch.nn.functional.silu(x)
        for i, block in enumerate(self.blocks):
            y = block(x)
            y = y * (1 + chunks[2 * i + 2][..., None, None]) + chunks[2 * i + 3][..., None, None]
            x = x + torch.nn.functional.silu(y)
        # baseline h = beta/2 recovers the exact sigma->0 Boltzmann score;
        # the zero-initialized head learns the sigma-dependent correction
        return self.out(x).squeeze(-3) + 0.5 * beta.view(-1, 1, 1)

    def score(self, field, sigma, beta, cond=None):
        return assemble_score(self.h_field(field, sigma, beta, cond), field)
