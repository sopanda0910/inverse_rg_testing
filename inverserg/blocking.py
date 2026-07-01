import torch
import torch.nn.functional as F
from torch import nn

from .lattice import plaquette_angles, rectangle_x_angles, rectangle_y_angles, regularize


def _circular_average(paths: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    # This is to ensure that the averaging is taken in the complex plane, and then mapped back to its phase
    # For example, 179 and -179 should have the average 180, not 0, but standard arithmetic would give 0
    sin_sum = (weights[:, :, None, None] * torch.sin(paths)).sum(dim=1)
    cos_sum = (weights[:, :, None, None] * torch.cos(paths)).sum(dim=1)
    return torch.atan2(sin_sum, cos_sum)


def _spatial_circular_average(paths: torch.Tensor, weights: torch.Tensor) -> torch.Tensor:
    """Circular average with per-site weights.

    paths:   [B, n_paths, L_c, L_c]
    weights: [B, n_paths, L_c, L_c]
    """
    sin_sum = (weights * torch.sin(paths)).sum(dim=1)
    cos_sum = (weights * torch.cos(paths)).sum(dim=1)
    return torch.atan2(sin_sum, cos_sum)


def _block_plaquette_features(field: torch.Tensor) -> torch.Tensor:
    """Gauge-invariant cos(plaquette) features for each 2x2 blocking cell."""
    plaq = plaquette_angles(field)
    if plaq.dim() == 2:
        plaq = plaq.unsqueeze(0)
    return torch.stack([
        torch.cos(plaq[:, 0::2, 0::2]),
        torch.cos(plaq[:, 1::2, 0::2]),
        torch.cos(plaq[:, 0::2, 1::2]),
        torch.cos(plaq[:, 1::2, 1::2]),
    ], dim=1)


def _block_rectangle_features(field: torch.Tensor) -> torch.Tensor:
    """Gauge-invariant cos(rectangle) features for each 2x2 blocking cell.

    Returns [B, 8, L_c, L_c]: 4 channels from rectangle_x, 4 from rectangle_y.
    """
    rect_x = rectangle_x_angles(field)
    rect_y = rectangle_y_angles(field)
    if rect_x.dim() == 2:
        rect_x = rect_x.unsqueeze(0)
        rect_y = rect_y.unsqueeze(0)
    return torch.stack([
        torch.cos(rect_x[:, 0::2, 0::2]),
        torch.cos(rect_x[:, 1::2, 0::2]),
        torch.cos(rect_x[:, 0::2, 1::2]),
        torch.cos(rect_x[:, 1::2, 1::2]),
        torch.cos(rect_y[:, 0::2, 0::2]),
        torch.cos(rect_y[:, 1::2, 0::2]),
        torch.cos(rect_y[:, 0::2, 1::2]),
        torch.cos(rect_y[:, 1::2, 1::2]),
    ], dim=1)


def _block_gauge_invariant_features(field: torch.Tensor) -> torch.Tensor:
    """Combined plaquette + rectangle features: [B, 12, L_c, L_c]."""
    # Essentially returns all of the physical observables (the wilson loops in the given lattice configuration)
    # Returns 12 channels of coarse lattices
    return torch.cat([_block_plaquette_features(field),
                      _block_rectangle_features(field)], dim=1)


def _subsample_even_even(tensor: torch.Tensor) -> torch.Tensor:
    return tensor[..., 0::2, 0::2]


def _batched_context(
    context: torch.Tensor | None,
    batch_size: int,
    context_dim: int,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    if context is None:
        return torch.zeros((batch_size, context_dim), device=device, dtype=dtype)
    if context.dim() == 1:
        context = context.unsqueeze(0)
    if context.shape[-1] != context_dim:
        raise ValueError(f"Expected context dim {context_dim}, got {tuple(context.shape)}")
    if context.shape[0] == 1 and batch_size > 1:
        context = context.expand(batch_size, -1)
    if context.shape[0] != batch_size:
        raise ValueError(f"Expected context batch {batch_size}, got {context.shape[0]}")
    return context.to(device=device, dtype=dtype)


def _x_paths(field: torch.Tensor) -> torch.Tensor:
    """All non-backtracking paths from (2i,2j) to (2i+2,2j) within |y|<=1.

    Returns [B, 7, L_c, L_c] with paths:
      0  straight      x, x
      1  up             y, x, x, -y
      2  down          -y, x, x,  y
      3  staircase_up   y, x, -y, x
      4  staircase_dn  -y, x,  y, x
      5  mid_up         x, y,  x, -y
      6  mid_down       x, -y, x,  y
    """

    ux = field[:, 0]
    uy = field[:, 1]
    
    # Generates possible paths to be considered    
    straight = ux + torch.roll(ux, shifts=-1, dims=-2)
    up = (uy + torch.roll(ux, shifts=-1, dims=-1)
          + torch.roll(ux, shifts=(-1, -1), dims=(-2, -1))
          - torch.roll(uy, shifts=-2, dims=-2))
    down = (-torch.roll(uy, shifts=1, dims=-1)
            + torch.roll(ux, shifts=1, dims=-1)
            + torch.roll(ux, shifts=(-1, 1), dims=(-2, -1))
            + torch.roll(torch.roll(uy, shifts=1, dims=-1), shifts=-2, dims=-2))
    staircase_up = (uy + torch.roll(ux, shifts=-1, dims=-1)
                    - torch.roll(uy, shifts=-1, dims=-2)
                    + torch.roll(ux, shifts=-1, dims=-2))
    staircase_down = (-torch.roll(uy, shifts=1, dims=-1)
                      + torch.roll(ux, shifts=1, dims=-1)
                      + torch.roll(uy, shifts=(-1, 1), dims=(-2, -1))
                      + torch.roll(ux, shifts=-1, dims=-2))
    mid_up = (ux + torch.roll(uy, shifts=-1, dims=-2)
              + torch.roll(ux, shifts=(-1, -1), dims=(-2, -1))
              - torch.roll(uy, shifts=-2, dims=-2))
    mid_down = (ux - torch.roll(uy, shifts=(-1, 1), dims=(-2, -1))
                + torch.roll(ux, shifts=(-1, 1), dims=(-2, -1))
                + torch.roll(uy, shifts=(-2, 1), dims=(-2, -1)))
    paths = [straight, up, down, staircase_up, staircase_down, mid_up, mid_down]
    
    # This is actually what makes the coarser lattice because only sampling even indices in all paths 
    # This function essentially returns all of the linear paths that could be used to make a coarse lattice
    # Then the NN figures out the weights to combine these coarse lattices to minimize the difference in measurables
    return regularize(torch.stack([_subsample_even_even(p) for p in paths], dim=1))


def _y_paths(field: torch.Tensor) -> torch.Tensor:
    """All non-backtracking paths from (2i,2j) to (2i,2j+2) within |x|<=1.

    Returns [B, 7, L_c, L_c] with paths:
      0  straight        y, y
      1  right           x, y, y, -x
      2  left           -x, y, y,  x
      3  staircase_rt    x, y, -x, y
      4  staircase_lt   -x, y,  x, y
      5  mid_right       y, x,  y, -x
      6  mid_left        y, -x, y,  x
    """
    ux = field[:, 0]
    uy = field[:, 1]

    # Generating all relevant paths needed to be considered
    straight = uy + torch.roll(uy, shifts=-1, dims=-1)
    right = (ux + torch.roll(uy, shifts=-1, dims=-2)
             + torch.roll(uy, shifts=(-1, -1), dims=(-2, -1))
             - torch.roll(ux, shifts=-2, dims=-1))
    left = (-torch.roll(ux, shifts=1, dims=-2)
            + torch.roll(uy, shifts=1, dims=-2)
            + torch.roll(uy, shifts=(1, -1), dims=(-2, -1))
            + torch.roll(torch.roll(ux, shifts=1, dims=-2), shifts=-2, dims=-1))
    staircase_right = (ux + torch.roll(uy, shifts=-1, dims=-2)
                       - torch.roll(ux, shifts=-1, dims=-1)
                       + torch.roll(uy, shifts=-1, dims=-1))
    staircase_left = (-torch.roll(ux, shifts=1, dims=-2)
                      + torch.roll(uy, shifts=1, dims=-2)
                      + torch.roll(ux, shifts=(1, -1), dims=(-2, -1))
                      + torch.roll(uy, shifts=-1, dims=-1))
    mid_right = (uy + torch.roll(ux, shifts=-1, dims=-1)
                 + torch.roll(uy, shifts=(-1, -1), dims=(-2, -1))
                 - torch.roll(ux, shifts=-2, dims=-1))
    mid_left = (uy - torch.roll(ux, shifts=(1, -1), dims=(-2, -1))
                + torch.roll(uy, shifts=(1, -1), dims=(-2, -1))
                + torch.roll(ux, shifts=(1, -2), dims=(-2, -1)))
    paths = [straight, right, left, staircase_right, staircase_left, mid_right, mid_left]
    
    return regularize(torch.stack([_subsample_even_even(p) for p in paths], dim=1))


class LearnableGaugeCovariantBlocker(nn.Module):
    # This model learns one fixed set of weights for the 7 paths that is applied everywhere
    
    def __init__(self, path_logits: torch.Tensor | None = None) -> None:
        super().__init__()
        if path_logits is None:
            # Initializing 2 7-element arrays as the logits
            # Logits are the inputs from the previous layer
            path_logits = torch.zeros(2, 7, dtype=torch.float32)
            # Initializing both of the arrays first elements as 2
            path_logits[:, 0] = 2.0
        self.path_logits = nn.Parameter(path_logits.clone().detach().float())

    def path_probabilities(self) -> torch.Tensor:
        # Calculates softmax across the columns (the 7 parameters in each array)
        # Outputs a tensor with shape (2, 7), but now normalized into probabilities
        return torch.softmax(self.path_logits, dim=-1)

    def forward(self, fine_field: torch.Tensor) -> torch.Tensor:
        if fine_field.dim() == 3:
            fine_field = fine_field.unsqueeze(0)
        if fine_field.shape[-1] % 2 != 0 or fine_field.shape[-2] % 2 != 0:
            raise ValueError("2x2 blocking requires even lattice dimensions.")
        weights = self.path_probabilities()
        coarse_x = _circular_average(_x_paths(fine_field), weights[0:1]) # Just extracts the 1st row (x-weights)
        coarse_y = _circular_average(_y_paths(fine_field), weights[1:2]) # Extracts 2nd row (y-weights)
        coarse = torch.stack([coarse_x, coarse_y], dim=1)
        return regularize(coarse)

    def regularization_loss(self) -> torch.Tensor:
        probs = self.path_probabilities()
        # This essentially calculates the entropy of the probability distribution of the paths
        # The 1e-8 is there to prevent 0*log(0) errors
        # This gives a score close to 0 if only one path is heavily weighted
        # Gives a very negative score if all paths are evenly weighted
        return torch.sum(probs * torch.log(probs + 1e-8))

    def summary(self) -> dict:
        probs = self.path_probabilities().detach().cpu()
        return {
            "type": "LearnableGaugeCovariantBlocker",
            "x_links": [float(x) for x in probs[0]],
            "y_links": [float(x) for x in probs[1]],
        }


class FixedGaugeCovariantBlocker(LearnableGaugeCovariantBlocker):
    def __init__(self) -> None:
        logits = torch.full((2, 7), -12.0, dtype=torch.float32)
        logits[:, 0] = 12.0
        super().__init__(path_logits=logits)
        self.path_logits.requires_grad_(False)

    def regularization_loss(self) -> torch.Tensor:
        return torch.tensor(0.0)

    def summary(self) -> dict:
        return {"type": "FixedGaugeCovariantBlocker"}


class SpatialGaugeCovariantBlocker(nn.Module):
    """Gauge-covariant blocker with spatially varying path weights.

    A convolutional network predicts per-site path logits from local
    gauge-invariant features (plaquette + rectangle cosines within each 2x2
    blocking cell).  At initialization the network favours the straight path,
    matching the behaviour of :class:`LearnableGaugeCovariantBlocker`.
    """

    # Consider using naive approach of actual links instead of measurables as inputs

    N_PATHS = 7
    # The input features are the physical observable wilson loops (the square and rectangle wilson loops)
    N_INPUT_FEATURES = 12

    def __init__(self, hidden_dim: int = 32, kernel_size: int = 3) -> None:
        # General structure of CNN
        '''
        Kernel with weights at each node of the kernel grid and a single bias. This kernel is convoluted across the entire input lattice, which produces
        a feature map which serves as the output. A typical CNN generally has many different kernels that are fitted and their feature maps are combined
        to produce an output. These output feature maps are then convoluted as the input of the next CNN layer        
        '''

        super().__init__()
        self.hidden_dim = hidden_dim
        self.kernel_size = kernel_size
        self._pad = (kernel_size - 1) // 2
        # Expects a lattice with self.N_INPUT_FEATURES channels, and will output a lattice with hidden_dim channels
        # Padding 0 only fits a kernel where all of the points in the kernel are input points
        # a non-zero padding would allow for edges where some of the kernel is just zeros or something like that
        self.conv1 = nn.Conv2d(self.N_INPUT_FEATURES, hidden_dim, kernel_size, padding=0)
        # This essentially just maps hidden_dim feature maps to hidden_dim feature maps with kernel of size 1
        # What is the point of this convolution layer?
        self.conv2 = nn.Conv2d(hidden_dim, hidden_dim, 1)
        # This produces feature maps for each possible path for x and y (multiply by 2)
        # Only convolves with kernel size 1 (each grid point)
        self.conv_out = nn.Conv2d(hidden_dim, 2 * self.N_PATHS, 1)
        self._init_output_bias()

    def _init_output_bias(self) -> None:
        nn.init.zeros_(self.conv_out.weight)
        with torch.no_grad():
            self.conv_out.bias.zero_()
            self.conv_out.bias[0] = 2.0
            self.conv_out.bias[self.N_PATHS] = 2.0

    def _predict_logits(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # This function actually goes through NN layers

        # [self._pad] * 4 = [self._pad, self._pad, self._pad, self._pad], which corresponds to [left, right, top, bottom]
        # This padding is required so that the 3x3 kernel convolution returns it back to its original size
        x = F.pad(features, [self._pad] * 4, mode="circular") if self._pad > 0 else features
        # Adds non-linearity to the feature map outputs
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        # Gets the output layer
        x = self.conv_out(x)
        # 0:self.N_PATHS is for the x and self.N_PATHS:end is the y links
        return x[:, :self.N_PATHS], x[:, self.N_PATHS:]

    def forward(self, fine_field: torch.Tensor) -> torch.Tensor:
        if fine_field.dim() == 3:
            fine_field = fine_field.unsqueeze(0)
        if fine_field.shape[-1] % 2 != 0 or fine_field.shape[-2] % 2 != 0:
            raise ValueError("2x2 blocking requires even lattice dimensions.")
        # Determines all of the square and rectangular wilson loop features
        # QUESTION: Why only using gauage invariant features, why not consider guage covariant inputs
        # like link variables + wilson loops/other observables, like used in the paper
        features = _block_gauge_invariant_features(fine_field)
        # Propagates through the NN layer
        x_logits, y_logits = self._predict_logits(features)

        # The output shape corresponds to the fact that at each lattice point, there is a 7-entry vector
        # containing the weights of each of the 7 paths, and this just softamxes these
        # Applies the softmax to the weights of each path (which is in dimension 1)
        # This is essentially maps the 1-dim of this tensor to a vector (still with 7 entries), but now normalized to sum to 1
        x_weights = torch.softmax(x_logits, dim=1)
        y_weights = torch.softmax(y_logits, dim=1)

        # Using these weights, this averages around these paths
        coarse_x = _spatial_circular_average(_x_paths(fine_field), x_weights)
        coarse_y = _spatial_circular_average(_y_paths(fine_field), y_weights)

        return regularize(torch.stack([coarse_x, coarse_y], dim=1))

    def regularization_loss(self) -> torch.Tensor:
        # Squared sum of all of its parameters
        # This isn't the full model loss, but just part of it
        # It may be useful to keep the parameters low to ensure smooth and accurate coarse graining
        # QUESTION: Purpose
        loss = torch.tensor(0.0)
        for p in self.parameters():
            loss = loss + p.square().sum()
        return loss

    def summary(self) -> dict:
        return {
            "type": "SpatialGaugeCovariantBlocker",
            "n_parameters": sum(p.numel() for p in self.parameters()),
            "n_paths": self.N_PATHS,
            "hidden_dim": self.hidden_dim,
            "kernel_size": self.kernel_size,
        }


class ConditionedSpatialGaugeCovariantBlocker(nn.Module):
    """Gauge-covariant blocker conditioned on a low-dimensional theory code."""

    N_PATHS = 7
    N_INPUT_FEATURES = 12

    def __init__(
        self,
        hidden_dim: int = 32,
        kernel_size: int = 3,
        context_dim: int = 16,
    ) -> None:

        super().__init__()
        self.hidden_dim = hidden_dim
        self.kernel_size = kernel_size
        self.context_dim = context_dim
        self._pad = (kernel_size - 1) // 2
        self.conv1 = nn.Conv2d(self.N_INPUT_FEATURES, hidden_dim, kernel_size, padding=0)
        self.conv2 = nn.Conv2d(hidden_dim, hidden_dim, 1)
        self.conv_out = nn.Conv2d(hidden_dim, 2 * self.N_PATHS, 1)

        # What is this? What is the purpose of context, and how is it used?
        self.film1 = nn.Linear(context_dim, 2 * hidden_dim)
        self.film2 = nn.Linear(context_dim, 2 * hidden_dim)
        self._init_conditioning()
        self._init_output_bias()

    def _init_conditioning(self) -> None:
        nn.init.normal_(self.film1.weight, mean=0.0, std=2e-2)
        nn.init.zeros_(self.film1.bias)
        nn.init.normal_(self.film2.weight, mean=0.0, std=2e-2)
        nn.init.zeros_(self.film2.bias)
        nn.init.normal_(self.conv_out.weight, mean=0.0, std=2e-2)

    def _init_output_bias(self) -> None:
        with torch.no_grad():
            self.conv_out.bias.zero_()
            self.conv_out.bias[0] = 2.0
            self.conv_out.bias[self.N_PATHS] = 2.0

    def _apply_film(self, x: torch.Tensor, context: torch.Tensor, layer: nn.Linear) -> torch.Tensor:
        gamma, beta = layer(context).chunk(2, dim=-1)
        return x * (1.0 + gamma[:, :, None, None]) + beta[:, :, None, None]

    def _predict_logits(
        self,
        features: torch.Tensor,
        context: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        x = F.pad(features, [self._pad] * 4, mode="circular") if self._pad > 0 else features
        x = self._apply_film(F.relu(self.conv1(x)), context, self.film1)
        x = self._apply_film(F.relu(self.conv2(F.relu(x))), context, self.film2)
        x = self.conv_out(F.relu(x))
        return x[:, :self.N_PATHS], x[:, self.N_PATHS:]

    def forward(self, fine_field: torch.Tensor, context: torch.Tensor | None = None) -> torch.Tensor:
        if fine_field.dim() == 3:
            fine_field = fine_field.unsqueeze(0)
        if fine_field.shape[-1] % 2 != 0 or fine_field.shape[-2] % 2 != 0:
            raise ValueError("2x2 blocking requires even lattice dimensions.")
        features = _block_gauge_invariant_features(fine_field)
        context = _batched_context(
            context,
            batch_size=fine_field.shape[0],
            context_dim=self.context_dim,
            device=fine_field.device,
            dtype=fine_field.dtype,
        )
        x_logits, y_logits = self._predict_logits(features, context)
        x_weights = torch.softmax(x_logits, dim=1)
        y_weights = torch.softmax(y_logits, dim=1)
        coarse_x = _spatial_circular_average(_x_paths(fine_field), x_weights)
        coarse_y = _spatial_circular_average(_y_paths(fine_field), y_weights)
        return regularize(torch.stack([coarse_x, coarse_y], dim=1))

    def regularization_loss(self) -> torch.Tensor:
        loss = torch.tensor(0.0, device=self.conv1.weight.device)
        for p in self.parameters():
            loss = loss + p.square().sum()
        return loss

    def summary(self) -> dict:
        return {
            "type": "ConditionedSpatialGaugeCovariantBlocker",
            "n_parameters": sum(p.numel() for p in self.parameters()),
            "n_paths": self.N_PATHS,
            "hidden_dim": self.hidden_dim,
            "kernel_size": self.kernel_size,
            "context_dim": self.context_dim,
        }

class NaiveBlocker(nn.Module):
    def forward(self, fine_field: torch.Tensor) -> torch.Tensor:
        # The fine_field shape is [batch_size, 2, width, length]
        # 2 because of x, y
        # The width and length must be even for the blocking to work
        if fine_field.dim() == 3:
            fine_field = fine_field.unsqueeze(0)
        if fine_field.shape[-1] % 2 != 0 or fine_field.shape[-2] % 2 != 0:
            raise ValueError("2x2 blocking requires even lattice dimensions.")
        ux = fine_field[:, 0] # This picks out all of the x values for all nodes and all batches
        uy = fine_field[:, 1]
        # This starts at 0 and skips every 2 going to the right, and starts at 0 and skips every 2 going up
        # then this is summed with the values of starting at 1 and going every 2 to the right, and 0 and skips every 2 going up
        coarse_x = regularize(ux[:, 0::2, 0::2] + ux[:, 1::2, 0::2])
        # This is the same process, but instead is shfited going up
        coarse_y = regularize(uy[:, 0::2, 0::2] + uy[:, 0::2, 1::2])
        # Restructures to maintain similar shape
        return torch.stack([coarse_x, coarse_y], dim=1)
