# Mentor items — resolutions (2026-08-14)

All three are answered. Each was a measurement, and two of the three answers
are nulls, which is why they are written down rather than acted on.

---

## 1. Check how instanton updates are used, based on sigma

**Answer: the threshold violates its own stated criterion, and it does not
matter.**

`charge_projection_sigma = 0.5` was never measured against anything. The
justification in `docs/NARRATIVE.md` §13 was that above "σ ~ O(1)" the model
still tunnels on its own, so projecting there is wasted. Measuring the model's
actual sector dynamics with enforcement off
(`scripts/33_charge_freezing_sigma.py`) gives a freezing σ of **0.304**
(16:14.1), **0.312** (32:55.0) and **0.307** (64:218.6) — about 3× below the
assertion and below the deployed 0.5. So roughly the first two of ~11
projections fire while the model can still undo them.

It changes nothing measurable. A 3 × 3 A/B (thresholds 0.20 / 0.31 / 0.50 ×
seeds 11 / 12 / 13, full ladder + validation each) gives mean |z_exact| of
0.812 / 0.814 / 0.768, with between-arm spread (0.026) *smaller* than
between-seed spread (0.030): F(2,6) = 2.30 against F_crit = 5.14. The count of
|z| > 3 observables is identical across all three arms at every seed
(0 / 1 / 0 of 86).

Action taken: corrected §13's prose to the measured value; left the config
alone. `out/u1_2d/proj_sigma_ab/seed_sweep_summary.json`.

Byproduct worth keeping: σ_freeze is **flat in volume** (0.304/0.312/0.307
over a 16× range in V), so this conclusion transfers across volumes rather
than needing a per-L sweep. The same measurement gives the unaided sector
match rate — 0.484 / 0.234 / 0.094 at L = 16 / 32 / 64, halving per 4× volume,
which is the sharpest statement of the study's main weakness (§21.5).

---

## 2. Tune hyperparameters

**Answer: five of six knobs are inside seed noise. `topo_weight` may not be —
and that is a lead for the successor, not a change to this study.**

Five knobs had been fixed at first-guess values for the whole program and
never varied: `kernel_size`, `sigma_max`, `batch_size`, `topo_weight`,
`sym_augment`. The one capacity change ever made (`v3_scale`) moved hidden
size, depth and L=32 coverage together, so it attributes to none of them.

One factor at a time from `v2.yaml`, **plus three seeds of the unchanged
baseline** — the noise floor is the primary measurement here, because every
comparison in this project that lacked one turned out to be inside it. Scored
on deployed fiber log-weight spread, not training loss.

| arm | change | geo mean over 3 monitors |
|---|---|---|
| base_s0 / s1 / s2 | (baseline) | 43.8 / 47.1 / 59.1 |
| kernel5 | kernel_size 3 → 5 | 44.3 |
| sigmax3 | sigma_max 6 → 3 | 49.6 |
| sigmax12 | sigma_max 6 → 12 | 50.9 |
| sym10 | sym_augment 0.5 → 1.0 | 45.4 |
| batch32 | batch_size 16 → 32 | 49.6 |
| **topo03** ×3 seeds | **topo_weight 0.1 → 0.3** | **36.5 / 38.4 / 43.1** |
| **topo05** ×2 seeds | **topo_weight 0.1 → 0.5** | **37.3 / 36.0** |

Baseline seed spread: **43.8–59.1**. Five knobs land inside it — they are not
costing anything, which is a real result and is only sayable because the
baseline seeds were run. Without them, `kernel5` at 44.3 vs `base_s0` at 43.8
would have looked like a comparison.

`topo_weight` replicates. All five raised-`topo_weight` seeds fall below all
three baseline seeds — complete separation, exact one-sided rank test
p = 1/C(8,3) = **0.018**. Restricted to the 3 vs 3 that varies only the seed
(0.3 vs baseline) the separation still holds but at the minimum resolvable
p = 1/C(6,3) = 0.05, and its worst seed (43.1) clears the best baseline (43.8)
by a hair — the pooled test is the one carrying the weight here.

Dose-response is monotone but saturating: 0.1 → 50.0, 0.3 → 39.3, 0.5 → 36.6
(means). Going 0.1 → 0.3 buys 1.27×; another 0.3 → 0.5 buys 1.07× more. So 0.3
is roughly where the return flattens, and there is no evidence for pushing
past 0.5 from these five points.

**Why this is not being acted on even though it replicated.** Every recorded
number in the study is tied to the deployed checkpoint — all 28 figures,
Tables S2/S5/S6/S7, the validation report, the head-to-head, the ESS program.
Swapping the checkpoint invalidates the lot, and `CLAUDE.md` closes U(1) to
model-quality work. Chasing a 1.27× improvement in a quantity that is 14–39×
away from usable is not worth re-running the campaign. The finding is recorded
as **the recommended starting point for the non-abelian successor**
(`topo_weight = 0.3`), where it costs nothing to adopt.

The decisive follow-up is *not* more spread measurements: it is whether
`topo_weight` improves the **raw sector match rate**, since that is the
mechanism it would have to act through. That runs against the checkpoints
already trained, with no further training.

`out/u1_2d/hparam_sweep.json`, `scripts/run_hparam_sweep.py`.

---

## 3. Present thermalization vs interval time differently by beta

**Answer: done, and the real problem was the evidence base, not the plot.**

2τ_int had been dropped from Fig. 12 entirely — while the caption still
described it — because at large β an "equilibrated" chain has frozen topology
and its steady-state cost flatters HMC. Omitting it hid the caveat instead of
stating it.

Now plotted by regime: a solid bar where the chain genuinely mixes
(β ≤ 6.47), and where `q_freezing.frozen` is set, a solid bar for the measured
Wilson part plus a hatched extension and arrow past the budget — because there
the interval is a *lower bound* on the cost of an independent configuration,
not the cost itself. The boundary is read per rung from the data, not set by
hand.

Splitting the scan by regime (`scripts/35_crossover_window.py`) exposed the
larger issue: of 29 rungs, 22 sat where fresh HMC never thermalizes at all, so
the comparison there is not a speedup but a statement that one method finishes
and the other does not. The band where HMC is genuinely healthy held **7
rungs, median speedup 1.9×**, with the two large margins at its top edge and
then a gap straight to β = 8.80.

Six new matched pairs (Part G, β_f = 5.41–9.61) fill that gap. The healthy
band is now 9 rungs reaching β = 6.47, freezing is bracketed between 6.47 and
7.22 (was 6.11–8.80), and hot-start failure between 8.80 and 9.61. The
crossover is measured through rather than inferred across.

`out/u1_2d/thermalization/crossover_window.json`.
