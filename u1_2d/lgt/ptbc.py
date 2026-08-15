"""Parallel tempering in boundary conditions, and open boundary conditions.

These are the two published classical remedies for topological freezing that
any speed claim in this project has to be measured against (Lüscher & Schaefer
JHEP 07 (2011) 036 for open boundaries; Hasenbusch PRD 96, 054504 (2017) and
Bonanno, Bonati & D'Elia JHEP 03 (2021) 111 for PTBC, which reports two orders
of magnitude in tau(Q^2)). Until now the project compared only against periodic
HMC with instanton/winding updates.

Construction (Hasenbusch). Take R replicas of the same lattice differing only
in a coupling factor c_r applied to the plaquettes of a small *defect* region
D, with

    S_r(theta) = -beta * sum_{p not in D} cos p - beta * c_r * sum_{p in D} cos p

and c_0 = 1 (periodic -- the physical replica whose measurements count) down to
c_{R-1} = 0 (the defect is cut, so windings can enter and leave freely there).
Configurations are swapped between adjacent replicas by Metropolis. Topology
decorrelates in the cut replica and the swap chain carries that mobility down
to the physical one, without biasing it: the c_0 = 1 replica is sampled from
the exact periodic action.

The swap acceptance follows from the pair exchange theta_r <-> theta_{r+1}:

    dS = beta (c_r - c_{r+1}) [ sum_D cos p(theta_r) - sum_D cos p(theta_{r+1}) ]

which involves only the defect plaquettes, so a swap is cheap regardless of
volume.

Open boundary conditions are the R = 1, c = 0 limit with the defect taken to
be a full line: plaquettes crossing one boundary are dropped, Q stops being an
integer, and windings enter through the open edge.
"""

import math

import torch

from .lattice import plaquette_angles, wrap


class DefectWilsonAction:
    """Wilson action with the plaquettes of a defect region scaled by `c`.

    `c = 1` reproduces `WilsonAction` exactly; `c = 0` cuts the defect. The
    defect is the set of plaquettes whose x-index lies in
    [x0, x0 + width) at every y -- a line wrapping the y direction, which is
    the 2D analogue of the (d-1)-dimensional defect used in the literature.

    Exposes the same surface as the other actions (`per_config`, `__call__`,
    `plaquette_log_weight`) so it drops into `BatchedHMC` unchanged.
    """

    name = "wilson_defect"

    def __init__(self, beta: float, L: int, c: float = 1.0,
                 defect_width: int = 1, defect_x0: int = 0,
                 defect_length: int | None = None, defect_y0: int = 0) -> None:
        self.beta = float(beta)
        self.L = int(L)
        self.c = float(c)
        self.defect_width = int(defect_width)
        self.defect_x0 = int(defect_x0) % self.L
        # l_d in Hasenbusch's notation. None means a full line (l_d = L), which
        # is the open-boundary limit and, per PRD 96 054504 sec IV C, the worst
        # choice: it needs many replicas for usable swap acceptance and is
        # "clearly outperformed" by a partial defect with l_d ~ xi.
        self.defect_length = int(defect_length) if defect_length else self.L
        self.defect_y0 = int(defect_y0) % self.L

    def _mask(self, device, dtype) -> torch.Tensor:
        """[L, L] multiplier: c on defect plaquettes, 1 elsewhere."""
        m = torch.ones(self.L, self.L, device=device, dtype=dtype)
        xs = (torch.arange(self.defect_width, device=device) + self.defect_x0) % self.L
        ys = (torch.arange(self.defect_length, device=device) + self.defect_y0) % self.L
        m[xs.unsqueeze(1), ys.unsqueeze(0)] = self.c
        return m

    def plaquette_log_weight(self, plaq: torch.Tensor) -> torch.Tensor:
        return self.beta * self._mask(plaq.device, plaq.dtype) * torch.cos(plaq)

    def per_config(self, theta: torch.Tensor) -> torch.Tensor:
        plaq = plaquette_angles(theta)
        return -self.plaquette_log_weight(plaq).sum(dim=(-2, -1))

    def __call__(self, theta: torch.Tensor) -> torch.Tensor:
        return self.per_config(theta).sum()

    def defect_cos_sum(self, theta: torch.Tensor) -> torch.Tensor:
        """sum over defect plaquettes of cos(theta_p), per configuration."""
        plaq = plaquette_angles(theta)
        xs = (torch.arange(self.defect_width, device=plaq.device)
              + self.defect_x0) % self.L
        ys = (torch.arange(self.defect_length, device=plaq.device)
              + self.defect_y0) % self.L
        return torch.cos(plaq[..., xs.unsqueeze(1), ys.unsqueeze(0)]).sum(dim=(-2, -1))

    def with_defect_at(self, x0: int, y0: int | None = None) -> "DefectWilsonAction":
        return DefectWilsonAction(self.beta, self.L, self.c, self.defect_width,
                                  x0, self.defect_length,
                                  self.defect_y0 if y0 is None else y0)


class StackedDefectWilsonAction:
    """All R replicas of a ladder as ONE action, so the ladder advances in one
    `BatchedHMC.metropolis_step` instead of R sequential ones.

    `per_config` takes `[R*B, 2, L, L]` laid out replica-major (replica r owns
    rows `r*B : (r+1)*B`) and applies a per-replica defect coupling. The
    per-replica loop in a PTBC driver is latency-bound at this project's
    volumes -- R tiny kernel launches per trajectory -- so folding the replica
    index into the batch is worth close to a factor R, and it is what makes the
    GPU competitive for this arm at all.

    The defect indicator is cached per (device, dtype, x0, y0). Rebuilding it
    inside the integrator, which is what the unstacked class did, costs more
    than the arithmetic it feeds.
    """

    name = "wilson_defect_stack"

    def __init__(self, beta: float, L: int, cs, n_chains: int = 1,
                 defect_width: int = 1, defect_x0: int = 0,
                 defect_length: int | None = None, defect_y0: int = 0) -> None:
        self.beta = float(beta)
        self.L = int(L)
        self.cs = [float(c) for c in cs]
        self.n_replicas = len(self.cs)
        self.n_chains = int(n_chains)
        self.defect_width = int(defect_width)
        self.defect_x0 = int(defect_x0) % self.L
        self.defect_length = int(defect_length) if defect_length else self.L
        self.defect_y0 = int(defect_y0) % self.L
        self._ind_cache: dict = {}
        self._mask_cache: dict = {}

    def indicator(self, device, dtype) -> torch.Tensor:
        """[L, L], 1 on defect plaquettes and 0 elsewhere."""
        key = (str(device), dtype, self.defect_x0, self.defect_y0)
        ind = self._ind_cache.get(key)
        if ind is None:
            ind = torch.zeros(self.L, self.L, device=device, dtype=dtype)
            xs = (torch.arange(self.defect_width, device=device)
                  + self.defect_x0) % self.L
            ys = (torch.arange(self.defect_length, device=device)
                  + self.defect_y0) % self.L
            ind[xs.unsqueeze(1), ys.unsqueeze(0)] = 1.0
            self._ind_cache[key] = ind
        return ind

    def _mask(self, device, dtype) -> torch.Tensor:
        """[R, 1, L, L] multiplier: c_r on defect plaquettes, 1 elsewhere."""
        key = (str(device), dtype, self.defect_x0, self.defect_y0)
        m = self._mask_cache.get(key)
        if m is None:
            ind = self.indicator(device, dtype)
            cs = torch.as_tensor(self.cs, device=device, dtype=dtype)
            m = 1.0 + (cs.view(-1, 1, 1, 1) - 1.0) * ind
            self._mask_cache[key] = m
        return m

    def _split(self, x: torch.Tensor) -> torch.Tensor:
        b = x.shape[0] // self.n_replicas
        return x.view(self.n_replicas, b, *x.shape[1:])

    def per_config(self, theta: torch.Tensor) -> torch.Tensor:
        plaq = self._split(plaquette_angles(theta))
        w = self.beta * self._mask(plaq.device, plaq.dtype) * torch.cos(plaq)
        return -w.sum(dim=(-2, -1)).reshape(-1)

    def __call__(self, theta: torch.Tensor) -> torch.Tensor:
        return self.per_config(theta).sum()

    def defect_cos_sums(self, theta: torch.Tensor) -> torch.Tensor:
        """[R, B] sum of cos over defect plaquettes -- all replicas at once.

        The unstacked swap recomputed plaquette angles twice per pair; this is
        the same information from one pass, which matters because the swap sits
        in the trajectory loop.
        """
        plaq = self._split(plaquette_angles(theta))
        ind = self.indicator(plaq.device, plaq.dtype)
        return (torch.cos(plaq) * ind).sum(dim=(-2, -1))

    def move_defect_to(self, x0: int, y0: int | None = None) -> None:
        self.defect_x0 = int(x0) % self.L
        if y0 is not None:
            self.defect_y0 = int(y0) % self.L


def swap_replicas_stacked(theta: torch.Tensor,
                          action: StackedDefectWilsonAction, parity: int,
                          generator: torch.Generator | None = None
                          ) -> tuple[torch.Tensor, torch.Tensor]:
    """Vectorized swap sweep over a stacked `[R*B, 2, L, L]` ladder.

    Same Metropolis rule as `swap_replicas`. All pairs of one parity are
    disjoint, so their decisions commute and can be taken simultaneously from a
    single pass of defect cos-sums -- each pair still uses the pre-swap values
    of its own two replicas, which is what detailed balance requires.

    Returns the updated stack and per-pair acceptance `[R-1, B]`; pairs of the
    other parity report NaN (see `swap_replicas`).
    """
    R = action.n_replicas
    B = theta.shape[0] // R
    m = action.defect_cos_sums(theta)
    lo = torch.arange(parity, R - 1, 2, device=theta.device)
    accepts = torch.full((R - 1, B), float("nan"), device=theta.device,
                         dtype=theta.dtype)
    if lo.numel() == 0:
        return theta, accepts
    hi = lo + 1
    cs = torch.as_tensor(action.cs, device=theta.device, dtype=m.dtype)
    d_s = action.beta * (cs[lo] - cs[hi]).unsqueeze(1) * (m[lo] - m[hi])
    u = torch.rand(d_s.shape, device=d_s.device, dtype=d_s.dtype,
                   generator=generator)
    acc = (u < torch.exp(-d_s)).to(theta.dtype)
    accepts[lo] = acc

    stack = theta.view(R, B, *theta.shape[1:])
    mask = acc.view(acc.shape[0], B, *([1] * (stack.dim() - 2)))
    a, b = stack[lo].clone(), stack[hi].clone()
    stack[lo] = mask * b + (1 - mask) * a
    stack[hi] = mask * a + (1 - mask) * b
    return stack.view(R * B, *theta.shape[1:]), accepts


def geometric_c_ladder(n_replicas: int) -> list[float]:
    """c values from 1 down to 0, linearly spaced.

    A reasonable default only at weak coupling. At the couplings this project
    cares about it fails badly: the defect action varies almost entirely within
    c < 0.2 (measured at L = 16, beta = 14.15: mean defect cos-sum -0.02 at
    c = 0 against 12.79 at c = 0.2), so a linear ladder puts a dS of order 30
    between the last two replicas and nothing is ever exchanged. Use
    `calibrated_c_ladder` for anything quantitative.
    """
    if n_replicas < 2:
        return [1.0]
    return [1.0 - r / (n_replicas - 1) for r in range(n_replicas)]


def calibrated_c_ladder(c_grid, m_grid, n_replicas: int) -> list[float]:
    """Place c values so the swap acceptance is roughly uniform along the ladder.

    For a defect coupling c, the exchange cost between neighbours is
    dS = beta (c_r - c_{r+1}) (m_r - m_{r+1}) with m(c) the mean defect
    cos-sum, so for small spacings dS ~ beta (dc)^2 dm/dc. Equalizing dS
    therefore requires dc ∝ (dm/dc)^{-1/2}, i.e. replicas equally spaced in

        u(c) = integral_0^c sqrt(dm/dc') dc'

    which is what this inverts. `m_grid` comes from a short pilot run at each
    `c_grid` point. Endpoints c = 1 and c = 0 are always included: the first is
    the physical replica and the last is the one that actually tunnels.
    """
    import numpy as np

    c = np.asarray(c_grid, dtype=float)
    m = np.asarray(m_grid, dtype=float)
    order = np.argsort(c)
    c, m = c[order], m[order]
    dm = np.gradient(m, c)
    # dm/dc should be positive (more coupling -> more ordered defect); clamp
    # noise at the flat end rather than letting a negative slope invert the map.
    w = np.sqrt(np.maximum(dm, 1e-6))
    u = np.concatenate([[0.0], np.cumsum(0.5 * (w[1:] + w[:-1]) * np.diff(c))])
    if u[-1] <= 0:
        return geometric_c_ladder(n_replicas)
    targets = np.linspace(0.0, u[-1], n_replicas)
    cs = np.interp(targets, u, c)
    cs[0], cs[-1] = 0.0, 1.0
    return [float(x) for x in cs[::-1]]  # c = 1 first (physical replica)


def refine_ladder_bottom(cs, beta: float, defect_length: int,
                         bc_step: float = 0.6, bc_max: float = 3.0) -> list[float]:
    """Resolve the last stretch of the ladder, where c -> 0.

    Measured symptom (scan at L=32, beta=218.58, l_d=2): with a calibrated
    ladder every pair accepts at 0.30-0.49 EXCEPT the final one, which sits at
    0.03-0.10 and improves only slowly with more replicas. The cause is that
    the natural tempering coordinate near the bottom is the defect coupling
    beta*c, not c: the defect only switches off once beta*c drops below O(1),
    and a ladder spaced evenly in the sense of dm/dc crosses that whole window
    in a single step.

    Swap cost near c = 0 is dS ~ d(beta c) * d(defect cos-sum), and the
    cos-sum difference between a free defect and a weakly coupled one is O(1)
    per plaquette. So the bottom must be stepped in beta*c, with spacing
    `bc_step` -- independent of beta, which is why the same ladder shape fails
    at 218.58 after working at 14.15.

    Everything above beta*c = `bc_max` is left as the calibration placed it.
    """
    cs = sorted({float(c) for c in cs}, reverse=True)
    keep = [c for c in cs if c * beta > bc_max]
    n_bottom = max(1, int(round(bc_max / bc_step)))
    bottom = [bc_max * (1.0 - k / n_bottom) / beta for k in range(n_bottom + 1)]
    out = keep + bottom
    out = sorted({round(c, 10) for c in out}, reverse=True)
    if out[0] < 1.0:
        out = [1.0] + [c for c in out if c < 1.0]
    if out[-1] > 0.0:
        out.append(0.0)
    return out


def swap_replicas(theta: torch.Tensor, actions: list[DefectWilsonAction],
                  parity: int, generator: torch.Generator | None = None
                  ) -> tuple[torch.Tensor, torch.Tensor]:
    """One sweep of Metropolis swaps between adjacent replicas.

    `theta` is [R, 2, L, L] (one configuration per replica) or
    [R, B, 2, L, L] for B independent tempering streams. Pairs (r, r+1) with
    r % 2 == parity are proposed simultaneously, which is the standard
    even/odd decomposition -- they are disjoint, so the moves commute.

    Returns the updated stack and the per-pair acceptance (1 = accepted). Pairs
    of the OTHER parity are reported as NaN, not 0: they were never proposed,
    and averaging them in as zeros halves every reported acceptance -- which is
    exactly what happened to the swap-acceptance column of the first benchmark
    run. Callers must aggregate with a NaN-skipping mean.
    """
    batched = theta.dim() == 5
    stack = theta if batched else theta.unsqueeze(1)
    R = stack.shape[0]
    accepts = torch.full((R - 1, stack.shape[1]), float("nan"),
                         device=stack.device)
    for r in range(parity, R - 1, 2):
        a_lo, a_hi = actions[r], actions[r + 1]
        # dS involves only the defect plaquettes; both actions share the same
        # defect region, so one cos-sum per replica is enough.
        s_lo = a_lo.defect_cos_sum(stack[r])
        s_hi = a_lo.defect_cos_sum(stack[r + 1])
        d_s = a_lo.beta * (a_lo.c - a_hi.c) * (s_lo - s_hi)
        u = torch.rand(d_s.shape, device=d_s.device, generator=generator)
        acc = (u < torch.exp(-d_s)).to(stack.dtype)
        mask = acc.view(-1, *([1] * (stack.dim() - 2)))
        lo, hi = stack[r].clone(), stack[r + 1].clone()
        stack[r] = mask * hi + (1 - mask) * lo
        stack[r + 1] = mask * lo + (1 - mask) * hi
        accepts[r] = acc
    return (stack if batched else stack.squeeze(1)), accepts


class OpenBoundaryWilsonAction:
    """Wilson action with one boundary opened: plaquettes at x = L-1 dropped.

    Q is no longer an integer under open boundaries -- that is the point, it is
    what lets windings enter -- so the charge is reported as the float
    `topological_charge_float` and compared only through its autocorrelation,
    never against the periodic exact P(Q).
    """

    name = "wilson_open"

    def __init__(self, beta: float, L: int) -> None:
        self.beta = float(beta)
        self.L = int(L)

    def plaquette_log_weight(self, plaq: torch.Tensor) -> torch.Tensor:
        m = torch.ones(self.L, self.L, device=plaq.device, dtype=plaq.dtype)
        m[self.L - 1, :] = 0.0
        return self.beta * m * torch.cos(plaq)

    def per_config(self, theta: torch.Tensor) -> torch.Tensor:
        return -self.plaquette_log_weight(plaquette_angles(theta)).sum(dim=(-2, -1))

    def __call__(self, theta: torch.Tensor) -> torch.Tensor:
        return self.per_config(theta).sum()
