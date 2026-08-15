"""Coverage for the AIS entry points that had none.

`bridge_features`, `fit_surrogate`, `sector_resolved_estimate` and
`_BridgeAction` are exercised in test_audit_additions. `coarse_only_features`,
`fit_surrogate_cv` and `ais_correct` were not -- and `ais_correct` is the
function that produced Table S7 and, at 10 seeds, its 20% divergence rate.

The last class here is a regression guard for that finding: the diagnostic
that separates a healthy bridge from a diverged one (minimum HMC acceptance)
must actually be reported, because the deployment advice is to assert a floor
on it. A silent rename or drop of that key would make the guard unenforceable
without failing anything.
"""

import math

import torch

from u1_2d.lgt import make_action, random_gauge_transform
from u1_2d.lgt.blocking import approx_matched_coarse_beta
from u1_2d.model.ais import (
    ais_correct,
    bridge_features,
    coarse_only_features,
    fit_surrogate,
    fit_surrogate_cv,
)


def random_field(batch=16, size=8, seed=0):
    gen = torch.Generator().manual_seed(seed)
    return torch.rand(batch, 2, size, size, generator=gen) * 2 * math.pi - math.pi


class TestCoarseOnlyFeatures:
    def test_shape_and_finiteness(self):
        coarse = random_field(batch=12, size=8, seed=1)
        f = coarse_only_features(coarse)
        assert f.shape[0] == coarse.shape[0]
        assert f.dim() == 2 and f.shape[1] >= 1
        assert torch.isfinite(f).all()

    def test_gauge_invariant(self):
        """These are the c-only regressors of the R^2_c decomposition; if they
        were not gauge invariant the decomposition would be measuring gauge."""
        coarse = random_field(batch=8, size=8, seed=2)
        transformed = random_gauge_transform(
            coarse, generator=torch.Generator().manual_seed(4))
        assert torch.allclose(coarse_only_features(coarse),
                              coarse_only_features(transformed), atol=1e-4)

    def test_deterministic(self):
        coarse = random_field(batch=6, size=8, seed=3)
        assert torch.equal(coarse_only_features(coarse),
                           coarse_only_features(coarse))


class TestFitSurrogateCV:
    def _data(self, n=64, p=5, noise=0.1, seed=0):
        gen = torch.Generator().manual_seed(seed)
        x = torch.randn(n, p, generator=gen).double()
        true_g = torch.randn(p, generator=gen).double()
        y = x @ true_g + noise * torch.randn(n, generator=gen).double()
        return x, y, true_g

    def test_recovers_a_clean_linear_signal(self):
        x, y, _ = self._data(noise=0.01)
        out = fit_surrogate_cv(x, y)
        assert out["r2"] > 0.99
        assert out["resid_std"] < 0.2

    def test_reports_the_selected_ridge_and_its_cv_table(self):
        x, y, _ = self._data()
        out = fit_surrogate_cv(x, y)
        assert "ridge" in out and "cv_table" in out
        assert out["ridge"] in [float(k) for k in out["cv_table"]]
        # Selection uses unrounded CV scores while cv_table is rounded to 3
        # decimals, so the table's argmin can tie or differ slightly; require
        # only that the selected ridge is within rounding of the table's best.
        tab = out["cv_table"]
        best = min(tab.values())
        assert tab[f"{out['ridge']:g}"] <= best + 1e-3

    def test_selection_is_independent_of_ambient_rng(self):
        """Regression guard for the fold-seeding fix (2026-08-14).

        Folds used to come from an unseeded `torch.randperm`, so the selected
        ridge depended on global RNG state at call time -- identical inputs
        chose ridges spanning 0.003-0.03, and changing an unrelated seed moved
        the folds as well as the physics. Selection must now be a pure
        function of its arguments.
        """
        x, y, _ = self._data(noise=1.0, seed=5)
        picks = set()
        for i in range(8):
            torch.manual_seed(500 + i)
            picks.add(fit_surrogate_cv(x, y)["ridge"])
        assert len(picks) == 1, f"ridge still depends on ambient RNG: {picks}"

    def test_fold_seed_is_a_real_knob(self):
        """Guards against the fix degenerating into ignoring the seed."""
        x, y, _ = self._data(noise=1.5, seed=8)
        cvs = {fit_surrogate_cv(x, y, fold_seed=s)["cv_resid_std"]
               for s in range(6)}
        assert len(cvs) > 1

    def test_is_reproducible_under_a_fixed_global_seed(self):
        """The property callers actually rely on: same seed, same answer."""
        x, y, _ = self._data(noise=1.0, seed=6)
        torch.manual_seed(99)
        a = fit_surrogate_cv(x, y)
        torch.manual_seed(99)
        b = fit_surrogate_cv(x, y)
        assert a["ridge"] == b["ridge"]
        assert math.isclose(a["cv_resid_std"], b["cv_resid_std"], rel_tol=1e-12)

    def test_picks_more_shrinkage_on_collinear_features(self):
        """The docstring's rationale: collinear columns need more ridge.

        This is a tendency, not a per-instance guarantee, so it is tested as
        one -- across several draws rather than on a single lucky one. (The
        single-instance version of this test passed only because unseeded
        folds happened to favour it.)
        """
        import statistics

        n, coll, ind = 48, [], []
        for s in range(8):
            gen = torch.Generator().manual_seed(100 + s)
            base = torch.randn(n, 2, generator=gen).double()
            indep = torch.cat([base, torch.randn(n, 3, generator=gen).double()], dim=1)
            collinear = torch.cat(
                [base, base[:, :1] + 1e-3 * torch.randn(n, 3, generator=gen).double()],
                dim=1)
            y = base[:, 0] * 2.0 + torch.randn(n, generator=gen).double() * 0.5
            coll.append(math.log10(fit_surrogate_cv(collinear, y)["ridge"]))
            ind.append(math.log10(fit_surrogate_cv(indep, y)["ridge"]))
        assert statistics.fmean(coll) > statistics.fmean(ind)

    def test_cv_residual_is_not_better_than_in_sample(self):
        x, y, _ = self._data()
        out = fit_surrogate_cv(x, y)
        assert out["cv_resid_std"] >= out["resid_std"] * 0.9


class TestAisCorrect:
    def _setup(self, n=8, size=8, fine_beta=6.0, seed=0):
        fine0 = random_field(batch=n, size=size, seed=seed)
        coarse_beta = approx_matched_coarse_beta(fine_beta, "wilson")
        feats = bridge_features(fine0, coarse_beta, "wilson")
        action = make_action("wilson", fine_beta)
        with torch.no_grad():
            target = action.per_config(fine0).double()
        fit = fit_surrogate(feats.double(), target)
        log_q = -target
        return fine0, log_q, fine_beta, coarse_beta, fit

    def test_runs_and_returns_the_documented_triple(self):
        fine0, log_q, fb, cb, fit = self._setup()
        x, log_w, diag = ais_correct(
            fine0, log_q, fb, cb, fit["g"], fit["const"],
            n_bridge=4, n_hmc_per_step=1, seed=0)
        assert x.shape == fine0.shape
        assert log_w.shape[0] == fine0.shape[0]
        assert torch.isfinite(log_w).all()
        assert isinstance(diag, dict)

    def test_reports_the_divergence_diagnostic(self):
        """Minimum bridge-HMC acceptance is what separates healthy runs from
        the 2-in-10 that diverge (Table S7b), and the deployment advice is to
        guard on it. It must be present and in [0, 1]."""
        fine0, log_q, fb, cb, fit = self._setup()
        _, _, diag = ais_correct(fine0, log_q, fb, cb, fit["g"], fit["const"],
                                 n_bridge=4, n_hmc_per_step=1, seed=0)
        assert "hmc_acceptance_min" in diag
        assert 0.0 <= diag["hmc_acceptance_min"] <= 1.0
        assert "hmc_acceptance_mean" in diag
        assert diag["hmc_acceptance_min"] <= diag["hmc_acceptance_mean"] + 1e-9
        # increment_std_per_step is the other divergence signature (~1e3
        # increments sustained across the schedule on the failed seeds).
        assert len(diag["increment_std_per_step"]) == 4

    def test_seed_is_honoured(self):
        fine0, log_q, fb, cb, fit = self._setup()
        args = (fine0, log_q, fb, cb, fit["g"], fit["const"])
        kw = dict(n_bridge=3, n_hmc_per_step=1)
        _, w1, _ = ais_correct(*args, seed=11, **kw)
        _, w2, _ = ais_correct(*args, seed=11, **kw)
        _, w3, _ = ais_correct(*args, seed=12, **kw)
        assert torch.allclose(w1, w2)
        assert not torch.allclose(w1, w3)

    def test_more_bridge_steps_do_not_break_the_weights(self):
        fine0, log_q, fb, cb, fit = self._setup()
        for n_bridge in (2, 8):
            _, log_w, _ = ais_correct(
                fine0, log_q, fb, cb, fit["g"], fit["const"],
                n_bridge=n_bridge, n_hmc_per_step=1, seed=5)
            assert torch.isfinite(log_w).all()
