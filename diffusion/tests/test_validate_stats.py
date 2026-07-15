import numpy as np

from diffusion.validate.stats import normalized_autocorrelation


def ar1(n: int, phi: float, rng: np.random.Generator) -> np.ndarray:
    x = np.empty(n)
    x[0] = rng.standard_normal()
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.standard_normal()
    return x


def test_gamma_zero_is_one():
    rng = np.random.default_rng(0)
    gamma = normalized_autocorrelation(rng.standard_normal(200), max_lag=10)
    assert gamma.shape == (11,)
    assert gamma[0] == 1.0


def test_uncorrelated_series_decays_to_noise():
    rng = np.random.default_rng(1)
    gamma = normalized_autocorrelation(rng.standard_normal((4000, 8)), max_lag=5)
    assert gamma.shape == (6, 8)
    assert np.all(gamma[0] == 1.0)
    assert np.abs(gamma[1:]).max() < 0.1


def test_ar1_matches_phi_to_the_lag():
    rng = np.random.default_rng(2)
    phi = 0.8
    chains = np.stack([ar1(20000, phi, rng) for _ in range(4)], axis=1)
    gamma = normalized_autocorrelation(chains, max_lag=4).mean(axis=1)
    expected = phi ** np.arange(5)
    assert np.allclose(gamma, expected, atol=0.05)


def test_max_lag_clipped_to_series_length():
    gamma = normalized_autocorrelation(np.array([1.0, 2.0, 3.0, 4.0]), max_lag=100)
    assert gamma.shape == (3,)


def test_batched_matches_per_chain():
    rng = np.random.default_rng(3)
    chains = rng.standard_normal((300, 3))
    batched = normalized_autocorrelation(chains, max_lag=6)
    for b in range(3):
        single = normalized_autocorrelation(chains[:, b], max_lag=6)
        assert np.allclose(batched[:, b], single)
