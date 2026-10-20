# Referee-style feedback on `paper/current.tex`

Collected feedback on the draft *"Diffusion models as preconditioners for Hybrid
Monte Carlo in lattice gauge theory"* (Panda, He, Zhao), with implementation
notes detailed enough to act on without re-deriving the context.

**Nothing in this file has been applied to `paper/current.tex`.** Each item is
written so that whoever implements it can do so directly.

Status as of 2026-10-13:

| source | received | nature |
|---|---|---|
| Qianteng Zhu | 2026-10-13 | substantive, one clear ask |
| Lingxiao Wang | 2026-10-13 | holding reply; full feedback promised next week |
| Jinchen He, Yong Zhao | — | pending |

---

## 1. Qianteng Zhu

### 1.1 What he said, verbatim

> Thanks for your summary, you used a different way to handle topology and your
> result is nice.
>
> But my point is still that it would be helpful to discuss more about full-QCD
> (you will finally go to it and it's our real world).
> (You may read my paper for U(2) and SU(2), our method can be easily applied to
> any compact group in any dimension.)

Two distinct requests, and they should not be conflated:

- **(A)** Expand the full-QCD discussion. This is the explicit ask, and he had
  already made it once before ("my point is **still**"), so it is the thing he
  actually cares about.
- **(B)** An implicit one, carried by the parenthesis: engage with his U(2)/SU(2)
  work, and be clear-eyed that his construction is group-agnostic where ours is
  not.

### 1.2 Which paper he means, and what is in it

"My paper for U(2) and SU(2)" is **arXiv:2601.19552**, *Generalizable Equivariant
Diffusion Models for Non-Abelian Lattice Gauge Theory* (Aarts, Habibi, Ipp,
Müller, Ranner, Wang, Wang, Zhu, Jan 2026).

**This is already `ref [9]` in our bibliography** (`aarts2026` in `main.bib`).
The problem is not a missing citation — it is that we cite it three times in
lists (`[6-9]`, `[8, 9]`, `[7-9, 11]`) and never once say what it does. A reader
cannot tell from our draft that ref [9] studies **the same theory we do, 2D
U(2)**, with a different method. That omission is what the parenthesis is
pointing at.

What their method is, for whoever writes the comparison:

| | ref [9] (Aarts/Zhu et al.) | this work |
|---|---|---|
| role of the model | **the sampler** — it produces the ensemble | **the initial condition** — HMC produces the ensemble |
| architecture | L-CNN, gauge-equivariant, score on the group manifold | CNN + FiLM on gauge-invariant loop features, score via plaquette curl |
| exactness | Metropolis accept/reject on the Wilson action, applied in the last 2% of annealing steps; asymptotically exact | HMC's own accept/reject; the lift only has to be a good start |
| topology | sampled by the model; checked via `chi_top` | **transported**, never generated |
| training | one ensemble, `beta_0 = 2`, `L = 16` | fixed rungs across couplings, plus sector augmentation |
| demonstrated at | 2D U(2) and SU(2), `beta` to 18, `L` to 64 | 2D U(1) and U(2), `beta` to 1660, `L` to 128 |
| generality by construction | formulated on the group manifold; the authors state it "extends to other gauge groups and can be formulated in arbitrary space-time dimensions" | relies on three 2D/Abelian properties (our own Sec. VI) |

Their earlier U(1) papers are ref [7] (arXiv:2410.19602, 2D U(1), physics
conditioning transfers one trained model across couplings) and ref [8]
(arXiv:2502.05504, JHEP 03, 111 (2026), 2D U(1), exactness via MALA, claims to
sample topological quantities more efficiently than HMC and Langevin).

### 1.3 Two facts from their paper that matter for how we respond

Both are from arXiv:2601.19552 and should be verified against the published
version before anything is written into our draft:

1. **Their `chi_top` degrades at strong coupling.** They report agreement at
   `beta = 2` and `beta = 10`, and a deviation at `beta = 18`
   (0.00837 against an exact 0.0064, roughly 30% high), which they attribute to
   sensitivity to infrared modes. They also state "only at the largest inverse
   couplings, `beta >= 16`, significant deviations are found."
2. **Their 4D scaling is explicitly open.** Their own outlook says "The question
   remains if DMs can successfully scale to four-dimensional SU(3) gauge theory
   with large lattice volumes."

So the honest position is **not** that their method generalizes and ours does
not. It is that *their architecture* generalizes to any compact group by
construction, while *neither method* has been demonstrated beyond two
dimensions. We should concede the first half plainly and not the second.

---

## 2. Implementation items

Ordered by (value to the paper) / (effort). F1-F3 are courtesy and accuracy and
should be done regardless. F4 is the substantive ask. F5-F6 are optional.

### F1 — Say what ref [9] actually does, in `sec:intro`

**Where:** `paper/current.tex`, Sec. I, the paragraph beginning *"In most of this
work the learned model is itself part of the sampler..."*

**Problem:** ref [9] appears only inside citation lists. Nothing tells the reader
it is a 2D U(2) study — the same theory as our Sec. IV C benchmark.

**Change:** add one or two sentences naming it, along the lines of:
gauge-equivariant diffusion models built on L-CNNs have been applied to
two-dimensional U(2) and SU(2) [9], with exactness restored by a
Metropolis-adjusted annealed Langevin step and with generalization demonstrated
to larger inverse couplings and lattice sizes from a single training ensemble.
Then state the contrast: there the model is the sampler and must be accurate at
the target coupling; here it supplies only the starting configuration.

**Effort:** 20 minutes. **Risk:** none. **Do this first** — it is the cheapest
thing that answers the parenthesis in his email.

### F2 — State the generality asymmetry in print, before a referee does

**Where:** end of Sec. VI, or a short paragraph in Sec. I after F1.

**Problem:** Our Sec. VI opens with *"The results rest on three structural
properties of the two-dimensional theories, and 4D SU(3) has none of them."*
That is honest, but it sits with no comparison, so the reader is left to work out
on their own that a contemporary alternative does not carry those restrictions.
Zhu has now worked it out and said so. Better to write it ourselves.

**Change:** one short paragraph making three claims, in this order:

1. A score model defined on the group manifold with an equivariant architecture
   carries to any compact group and any dimension by construction [9]; our
   construction does not, and the three properties in Sec. VI are the reason.
2. What we buy in exchange: the model never has to be accurate at the target.
   It supplies an initial condition, HMC supplies correctness, and the topology
   is transported rather than modelled — so the quantity hardest for a
   generative model to get right at strong coupling is the one quantity we never
   ask it for. (Their own `chi_top` at `beta = 18` is a concrete illustration;
   cite it neutrally, as a cost of the direct-sampling route, **not** as a
   criticism of their paper.)
3. Both are two-dimensional demonstrations. Their 4D SU(3) scaling is stated as
   open in their own outlook; ours is Sec. VI. Say so.

**Effort:** half a day of careful writing. **Risk:** tone. This must read as a
statement of complementary trade-offs, not as a rebuttal. Zhu is a likely
referee and a near-certain reader.

### F3 — Do not overstate what we concede

**Note for whoever writes F2.** Resist the temptation to soften our own result to
be polite. The following remain true and should survive the edit:

- Topology is transported exactly, configuration by configuration — verified by
  direct measurement (`u2_2d/scripts/36_transport_check.py`), including under
  composition of three lifts.
- We reach `beta = 1660` at `L = 128`, which is far outside the range either
  method has been tested at, and the lifted configuration starts 35 ppm from the
  exact plaquette against a cold start's 1200.
- Our correctness argument does not depend on the model at all: HMC's
  accept/reject is responsible throughout.

### F4 — Expand Sec. VI into a 4D programme, not a list of obstacles ← **the main ask**

**Where:** Sec. VI, currently about one page.

**Problem:** Sec. VI is organized as *three things we have that SU(3) does not*.
It is accurate and it is honest, but structurally it is a list of reasons the
method might not transfer. Zhu asked twice for "more about full-QCD" because what
is missing is the other half: **what one would actually do**. Every obstacle
should be paired with a candidate resolution, named concretely enough that a
reader can judge whether it is plausible.

Six sub-items. F4a-F4c are rewrites of material already present; F4d-F4f are new.

#### F4a — Blocking in 4D: say what would replace the plaquette sum

Current text establishes that an ordered product of SU(3) matrices does not
telescope, then stops.

Add: what property is *actually* required. We do not need a blocking map that
preserves `Q` exactly — we need coarse/fine training pairs whose **relative**
charge is known, plus a transport step at deployment. Those are different and
weaker requirements, and the distinction is already load-bearing elsewhere in
our own argument (App. B: coverage without correct frequencies). Candidates to
name: standard RG blocking schemes for non-Abelian links (APE/HYP-style
projected averaging), or measuring `Q` independently on both members of the pair
after smoothing rather than deriving equality from the map.

#### F4b — The charge definition in 4D: pick one and state the consequence

Current text says `Q` has no cheap unambiguous lattice definition, cites the
smoothing-scheme dependence [56] and the Ginsparg-Wilson index [57], and
concludes that imposing `Q_coarse` would be exact only with respect to a chosen
definition.

Add: say which definition we would use (gradient-flow charge at a fixed flow
time, rounded), and spell out that this makes transport exact with respect to
that definition and that the physics claim is then about the flowed charge. This
is a normal, defensible position in the field and stating it converts a stated
weakness into a stated choice.

#### F4c — The cheap topology-changing update: make the PTBC/bias-potential route concrete

Current text names PTBC [58-60], boundary-opening with non-equilibrium
evolution [61, 62], a stochastic sector-jumping dynamics [63], and
multicanonical/metadynamics bias potentials [64-66], then says we find the bias
potential most promising.

The argument for the bias potential is the strongest thing in Sec. VI and is
currently three sentences. Expand it:

- It is used **only while training data is built**, never at deployment.
- It therefore does not need to be reweighted away, because the distribution it
  produces is not the result — the result is the local structure at a given
  charge.
- The charge is imposed by transport afterwards.
- Hence neither its acceptance rate nor its sector frequencies need to be
  correct. **This is the single most transferable idea in the paper** and it
  deserves more than a clause.

**Caveat that must travel with it:** our evidence that frequencies do not matter
is App. B, which bounds the dependence *loosely* (0.03 and 0.20 standard errors
against a resolution floor of about 0.9). State it as a design argument
supported by a weak null, not as a measured result. See also F6.

#### F4d — Coupling matching in 4D (new)

Not currently addressed beyond one clause ("couplings would have to be matched
numerically by scale setting [54, 55]").

In 2D we fix `beta_f` by the topology-matching condition of Eq. (9), which
requires the exact `<Q^2>`. In 4D that closed form does not exist, so the
matching has to come from scale setting (`w_0`, `t_0`, or `r_0`). Worth one
paragraph: what quantity would be matched, that it is standard practice, and
that the ladder's defining property — fixed physical volume while the spacing
halves — survives, because that is a statement about `L a`, not about `Q`.

#### F4e — Name the first 4D experiment (new)

The most useful thing that could be added, and currently absent. One short
paragraph specifying the smallest experiment that would test the construction in
4D: gauge group, approximate volume and coupling, how the coarse ensemble would
be produced, which charge definition, what the success criterion would be in the
absence of a closed form (agreement between differently-initialized chains, or
comparison against a long reference run — both already named in Sec. VI as
replacements for our exact-solvability criterion). This converts the outlook
from "here is what is hard" into "here is the next run", which is what Zhu is
asking for.

#### F4f — Say something about fermions (new)

Zhu's phrase is "full-QCD", not "SU(3) pure gauge". The draft never mentions
dynamical fermions except in the first sentence of Sec. VI. At minimum one
honest paragraph: the preconditioner acts on the gauge field only; a lifted
configuration would still need the fermion determinant handled by the HMC that
follows; the relevant precedent is refs [21, 22], which did RG-matched
coarse-to-fine initialization in theories **with** fermions and are already
cited. Note also that the economics improve in that setting, since the cost of a
trajectory rises steeply with dynamical fermions while the cost of one reverse
diffusion does not.

#### F4g — Why the argument gets *stronger* in 4D, not weaker (new, optional)

A closing paragraph worth considering: every quantity our method trades on moves
in our favour toward 4D. Freezing is more severe, configurations are more
expensive, so the relative value of a good starting configuration rises, while
the fixed cost of one reverse diffusion does not grow with the autocorrelation
time it is being compared against (App. H already makes the second half of this
argument in 2D). This is the natural note to end Sec. VI on and it directly
answers "you will finally go to it and it's our real world."

### F5 — Cite the forthcoming Aarts et al. paper when it appears

Lingxiao Wang (see §3) says a more systematic L-CNN + MAALA-DM study posts to
arXiv within the week. Add it to `main.bib` and cite alongside [9] once the
number exists. **Check before submission.**

### F6 — Optional: strengthen App. B so F4c can lean on it

The bias-potential argument in F4c rests on "coverage matters, correct sector
frequencies do not". App. B currently bounds that weakly. If there is appetite
for one more run before submission, the experiment that would settle it is
already specified in `CLAUDE.md`: retrain with a deliberately wrong sector
distribution (uniform over the same support, `seed_exact_sectors` off, so the
two mechanisms are not entangled as they are in every checkpoint that currently
exists) and compare lift quality. If lift quality does not move, the
exactly-solvable dependency is gone from the method and survives only in the
scoring — which is exactly the claim F4c wants to make, and the claim that makes
the 4D route credible.

**Effort:** one retrain plus one evaluation pass. **Value:** turns the most
transferable idea in the paper from an argument into a measurement. **Decision
needed:** whether this blocks submission or is left as stated future work.

---

## 3. Lingxiao Wang

### 3.1 What he said

A holding reply, not yet substantive feedback — he says his schedule is tight
and he will return to the manuscript next week. Four things in it are
nonetheless actionable:

1. **A more systematic L-CNN + MAALA-DM study posts to arXiv next week.**
   → F5. Watch for it and cite it.
2. **He and a postdoc are exploring diffusion models for inverse RG.** This is
   direct overlap with the core of our paper. Nothing to fix in the draft, but it
   is a reason not to let the submission drift: the relevant work is being done
   in parallel elsewhere and he has told us so plainly, which is a courtesy.
3. He singles out as the interesting part **the separation between topology
   transport in the Abelian sector and reconstruction of the non-Abelian degrees
   of freedom** in U(2). That is the `p(psi) p(q | psi)` factorization of
   Sec. III D. Worth noting that an outside reader independently picked this out
   as the novel element — it should probably be more prominent in the abstract
   and in Sec. I than it currently is.
4. He asks about extending the strategy to **4D SU(N)** — the same question as
   Zhu's, from a second reader, on the same day. Two independent requests for the
   same thing is a strong signal that F4 is the priority revision.

### 3.2 Pending

Full feedback expected the week of 2026-10-19. Do not consider the revision
closed before it arrives.

---

## 4. Suggested order of work

1. **F1** — name what ref [9] does. Cheap, immediate, answers the parenthesis.
2. **F4a-F4c** — rewrite the three existing Sec. VI obstacles as
   obstacle + candidate resolution.
3. **F4e** — name the first 4D experiment. This is what makes Sec. VI read as a
   programme.
4. **F2** — the complementarity paragraph. Write it after F4, when the trade-off
   is clear on the page.
5. **F4d, F4f, F4g** — scale setting, fermions, and the closing argument.
6. **F5** — cite the new paper once it posts.
7. **F6** — decide whether the sector-frequency ablation blocks submission.

Items 1-5 are writing, not computation, and touch no results. Nothing in F1-F5
invalidates any number currently in the draft.

---

## 5. Qianteng Zhu — clarification (2026-10-16)

> I've gone through the "Outlook" section. Although the content is quite detailed
> and thorough, it mainly points out the limitations of the current work rather
> than discussing future directions. I feel that simply stating what problems
> need to be solved is not enough; it would be better to discuss how to solve
> them. The proposed approaches can be rough, but they need to be reasonable and
> make sense.

This confirms F4 and sharpens it. Sec. VI is not missing proposals entirely — it
is unbalanced, and the imbalance is structural. Audit of the current text:

| obstacle | problem stated | solution proposed | verdict |
|---|---|---|---|
| 1. blocking does not preserve `Q`; no cheap `Q` definition | yes, at length | **none** | the real gap |
| 2. no cheap topology-changing update | yes | yes — PTBC / SNF / bias potential, with the bias potential argued for | adequate, could be expanded |
| 3. no exact solvability | yes | one subordinate clause listing three options | too thin to evaluate |

One of the three has a developed proposal, one has a clause, and the most
fundamental one has nothing. The section also *opens* with "The results rest on
three structural properties of the two-dimensional theories, and 4D SU(3) has
none of them", which frames everything following as limitation, and *ends* on the
division of labour rather than on a plan.

His bar is explicitly low on rigour ("can be rough") and high on specificity
("reasonable and make sense"). That is F4a-F4g, and within it **F4a (what
replaces telescoping) and F4e (name the first 4D experiment)** are what he is
actually missing.

---

## 6. Kai Zhou (2026-10-16)

*Resolution status for every item below is in §13. K1 and K5 now have
measurements rather than proposed actions; read §13 before acting on the
effort estimates at the end of this section.*

> Does Eq. (15) give the full determinant measure on a finite torus? Also, 25-30
> heatbath sweeps maybe not generally an exact conditional draw. Does the
> marginal winding update still preserve the U(2) target?
>
> Since Q is imposed explicitly, one could compare with a simple non-neural
> prolongation using the same coarse fields, charge adjustment and local updates,
> right?
>
> For Eq. (16), failure to thermalize within a budget does not give a lower bound
> on stationary 2\tau_int. The efficiency comparison might also need to include
> coarse-generation and lifting costs.

### K1 — CRITICAL: the non-neural prolongation ablation exists and is not in the paper

**The most consequential item in this file.** Kai asks for a comparison against a
non-neural prolongation using the same coarse fields, charge adjustment and local
updates. That experiment has been built and run:
`u2_2d/scripts/17_prolongator_baseline.py` and `21_prolongator_observables.py`,
with roughly twenty output directories under `out/u2_2d/prolongator_*`. Its own
docstring says the ablation closes a gap because otherwise "the baselines are
strawmen, and it is the first thing a referee says."

`grep -ic prolongat paper/current.tex` returns **0**.

Four non-learned arms, each receiving post-processing byte-identical to the
diffusion arm (coarse-charge enforcement, 30 conditional SU(2) sweeps): `tile`
(2x2 replication), `halve` (exact deterministic inverse of the blocking rule),
`flux` (blocking-consistent and flux-spreading), and `smear` (`flux` plus
heatbath/overrelaxation sweeps, count tuned per coupling).

Result at L = 64, beta = 416.524, no retherm — the deployed pipeline
(`out/u2_2d/prolongator_L64_noretherm/report.md`):

| arm | `t_therm` slowest | rel. err. of the RAW lift | abs. rel. dev. at t=0 |
|---|---|---|---|
| tile / halve / flux | > 400 | 3.6e-03 / 1.9e-01 / 9.7e-02 | — |
| **smear** | **0** | -9.65e-02 | **2.51e-06** |
| cold | > 400 | — | 4.83e-03 |
| **diffusion** | **0** | **+6.47e-05** | 8.21e-06 |

Read it in two halves, because they say opposite things:

- **On the raw lift the model wins decisively** — 6.47e-05 against the best
  geometric arm's 3.6e-03, a factor of 56.
- **After the post-processing every arm receives, the advantage inverts.** At
  t = 0 the diffusion arm is **3.3x worse than `smear`** (8.21e-06 against
  2.51e-06), and on extended loops the model is worse again (mean |z| 1.54
  against `flux`'s 0.13 in `prolongator_observables`; 2.11 against `tile`'s 0.47
  in `_v2`). The script's own conclusion: *"There is then no measured observable
  on which the model beats a geometric map."*
- **Topology is a control here, not a result.** `apply_coarse_charge` imposes the
  coarse charge on every arm, so `<Q^2>` and P(Q) coverage are identical by
  construction; a difference would indicate a bug.

**What this does and does not mean.** It does not show any number in the paper is
wrong — Sec. VI already says the model supplies the sector and not the local
structure, which is consistent with this. But the sector is imposed identically
on the geometric arms too, so the question "what does the model contribute that a
cheap deterministic map does not?" currently has no answer in the paper, and Kai
has asked it directly.

Three defences are available and should be checked before conceding:

1. **`smear` is tuned against the closed form.** Its sweep count is chosen per
   coupling to match the exact plaquette. In 4D there is no exact plaquette to
   tune against, so it is not a transferable competitor. Sec. V shows the learned
   lift working across 44 couplings with no per-coupling tuning. **This is the
   strongest available response and it is currently nowhere in the draft.**
2. **These runs are single-lift at L = 64.** The headline is a ladder to L = 128
   through successive lifts. Whether a geometric prolongator survives composition
   is untested; `45_multi_lift_compounding.py` tested composition for the learned
   lift only.
3. **The extended-loop comparison is at a superseded setting.** Both
   `prolongator_observables` runs use 10 rethermalization sweeps; the deployed
   pipeline uses 0. That table must be re-run at `n_retherm_sweeps = 0` before it
   is quoted in either direction.

Required action, in order:

- a. Re-run `21_prolongator_observables.py` at the deployed no-retherm setting.
- b. Run the geometric arms through the **full ladder** to L = 128, not one lift,
  so defence 2 is tested rather than asserted.
- c. Measure `smear` at a coupling where its sweep count is **not** tuned against
  exact (transfer the count from a neighbouring coupling) to size defence 1.
- d. Add a prolongator subsection to Sec. IV with whatever the answer is. If the
  honest answer is that local observables do not separate the arms, say so: the
  claim then rests on topology transport, cross-coupling robustness without
  tuning, and behaviour under composition — all defensible, and all either
  already measured or cheaply measurable.

**Do not submit without addressing this.** Two independent readers would ask it;
one already has.

### K2 — Eq. (15) and the finite torus

**Status: needs a precise sentence in the text; probably not a defect.**

Eq. (15), `w_det(alpha) = 2 I_1(z)/z` with `z = beta cos(alpha/2)`, is the
**single-plaquette** marginal from integrating SU(2) out of one plaquette. It is
not by itself the determinant measure on a finite torus, and the draft does not
claim that it is — App. D builds the finite-V distribution as
`P(Q) ~ integral dk exp(-2 pi i k Q) psi_det(k)^V`, the standard
character-expansion treatment of the torus (Bonati & Rossi, ref [37]), with the
`k` integral enforcing the global constraint.

Worth stating explicitly, since Kai is right that it is not obvious: the `V`-th
power is legitimate in 2D because plaquettes become independent after gauge
fixing, and the global constraint is restored by the `k` integral. There is also
a `Z_2` subtlety specific to U(2) — `U(2) = (U(1) x SU(2))/Z_2`, so the parity of
`Q` is tied to the ordered product of SU(2) plaquettes — which the
single-plaquette marginal does not manifestly carry.

**Action:** one or two sentences in App. D saying that Eq. (15) is a
single-plaquette marginal, that the finite-torus distribution is the `k`-integral
construction, and why the factorization is valid in 2D. Cite the existing
validation: the closed form reproduces heatbath to 1-2% in every sector at
beta = 2, 5, 8, and `det_topological_charge_distribution` was re-checked on a 16x
finer `k` grid with `<Q^2>` and P(odd) stable to 1e-6 relative.

### K3 — "25-30 heatbath sweeps maybe not generally an exact conditional draw"

**Status: he is right, and the current wording is wrong. Fix the wording.**

Sec. III D says heatbath sweeps "draw it exactly from `p(q | psi)`". Heatbath is
an exact *update* — it leaves `p(q | psi)` invariant and each single-link draw
comes from the exact conditional — but a finite number of sweeps from a
non-equilibrium start is not an exact *draw*. The internal docs already treat
`n_su2_sweeps` as "the move's ONE approximation"
(`marginal_winding_update` docstring).

**Action:** replace "draws it exactly" with the accurate statement — each sweep
is an exact update leaving the conditional invariant, and the finite sweep count
is the one approximation in the move — then cite the measurement that bounds it:
`34_marginal_move_bias.py`, 128 chains x 1280 draws, odd/exact = 1.00065
(z = +0.26) at the deployed 25 sweeps and 0.99994 (z = -0.02) at 100.

### K4 — "Does the marginal winding update still preserve the U(2) target?"

**Status: known open item, independently rediscovered. Needs an honest sentence.**

The move is a marginal-propose / conditional-resample composite: accept on
`w_det` alone, then redraw SU(2). That targets `p(psi, q) = p(psi) p(q | psi)`
exactly **only if** `w_det` is the exact marginal (K2) and the SU(2) redraw is an
exact conditional draw (K3). Kai's three sub-questions are therefore one
question, which is why he asked them together.

Measured: no detectable bias at the deployed setting across six cells
(`34_marginal_move_bias.py`), and all seven couplings return SAMPLED under the
calibrated verdict in `07_pq_sampling.py`. But `CLAUDE.md` records a standing
open item — a `+2.61` in `odd_z` at beta = 28, which the calibration shows the
test detects only 15-22% of the time at the observed deviation size, "neither
dismissible nor established".

**Scope limiter that must be stated:** the marginal move is used for the
**classical baseline arms**, not for the lift. Topology in the preconditioned
arms is transported, never proposed. A residual bias in this move would therefore
affect the baseline the method is measured against, not the method.

**Action:** a footnote or short App. B/G paragraph giving the composite-move
argument, the condition under which it is exact, the measured bound, and the
scope limiter.

### K5 — Eq. (16): a failed budget is not a lower bound on stationary 2 tau_int

**Status: he is right. A real methodological overreach, and it touches the
abstract.**

Sec. IV E takes a classical arm that fails the equilibration gate, calls its cost
infinite, and reports `F` as a lower bound equal to the coupling's budget divided
by the preconditioned cost. That is not a bound. Equilibration time and `tau_int`
are both governed by the spectral gap and are related, but "did not equilibrate
from a cold start within 200 trajectories" does not imply "stationary
`2 tau_int >= 200`". The budget is an experimental limit, not a property of the
chain.

This propagates: the abstract's "cheaper by a median factor of at least nine" is
the median of 24 such constructions, and Sec. IV E quotes "running from 1.5 to
200 with a median of 9.1".

**Preferred fix, which costs little:** stop calling them bounds. Report what was
observed — at these couplings no classical arm delivered an independent
configuration of the target within the budget it was given, so no finite
per-configuration cost can be quoted for it, while the preconditioned arm was at
the target from the first record. Relabel the Fig. 5 triangles as budget-limited
rather than lower bounds and rephrase the abstract. The qualitative claim
survives; the word "bound" and the median taken over bounded values do not.

**Alternative, if the numerical claim is wanted:** measure `tau_int` on a
*thermalized* classical chain at those couplings, started from the lift. That
gives a legitimate stationary `2 tau_int` and makes `F` well defined. More
expensive, but it would convert the strongest headline number into a measurement.

### K6 — "The efficiency comparison might also need to include coarse-generation and lifting costs"

**Status: already in the paper, but evidently not where a reader finds it.**

Sec. IV E states that a full-ladder configuration costs 2.4x a winding-HMC one
with base generation included, and 1.4x counting the top rung alone; App. H is
devoted to the overhead. Kai read the draft and raised it anyway, which is
evidence the placement is wrong: `F` is defined in Sec. IV A and used throughout,
while the caveat that it excludes the dominant cost arrives later and in prose.

**Action:** state the exclusion where `F` is defined, immediately after Eq. (16),
with a forward reference to App. H. Consider giving the 2.4x figure in the
abstract, which currently quotes only trajectory-counted comparisons.

### Summary of Kai's points

| | nature | effort |
|---|---|---|
| K1 prolongator ablation | **missing control; work exists but needs re-running and a new subsection** | days |
| K2 Eq. (15) on the torus | explain better | 1 hour |
| K3 "exactly" overstates | wording fix; the claim as written is wrong | 1 hour |
| K4 marginal move validity | explain better, state scope; known open item | 2 hours |
| K5 Eq. (16) lower bounds | **real overreach; touches the abstract** | half a day |
| K6 cost placement | move existing material earlier | 1 hour |

---

## 7. Revised priority across all reviewers

1. **K1** — the prolongator ablation. Blocking.
2. **K5** — drop the lower-bound construction. Blocking; it is in the abstract.
3. **F4a / F4e** — what replaces telescoping, and the first 4D experiment.
   Requested twice by Qianteng and once by Lingxiao.
4. **K3** — fix "draws it exactly".
5. **F1** — say what ref [9] does.
6. **K2, K4, K6** — clarifications.
7. **F2, F4b-F4g, F5, F6** — as previously ordered.

---

## 8. K1 addendum (SUPERSEDED IN PART BY §10 — read §10 first) — reconciling the two prolongator experiments, and a refuted defence

Added 2026-10-16 after checking what has actually been run. **Read this before
acting on K1 above**, because one defence proposed there does not survive the
existing data.

### 8.1 Has the enforced-charge classical ablation been done? Yes, in U(2)

`u2_2d/scripts/17_prolongator_baseline.py` line 218 calls `apply_coarse_charge`
on **every** arm, geometric ones included. So the experiment Kai asks for — same
coarse fields, same charge adjustment, same local updates, no model — is already
run, and its result is the table in K1: at the deployed no-retherm setting
`smear` reaches `t_therm = 0` and sits 3.3x closer to the exact plaquette at
t = 0 than the diffusion arm.

`u1_2d/scripts/37_tiling_baseline.py` is the U(1) analogue and does **not** apply
charge enforcement — which is precisely why `67_prolongator_topology.py` was
added later, described in its own docstring as "THE MISSING COLUMN ... added
after it inverted a day of conclusions".

So the two prolongator experiments measure different things and must not be
quoted against each other:

| | charge enforcement | what it measures | result |
|---|---|---|---|
| u1 `67_prolongator_topology` | **off** | what a prolongator produces unaided | `halve`/`flux` give `Q = 0` on every configuration; `tile` gives 14.4x exact; none usable |
| u2 `17_prolongator_baseline` | **on, all arms** | local map quality at fixed `Q` | `smear` beats the learned lift 3.3x on the plaquette at t = 0 |

Anyone reading only the second table will conclude the geometric arms handle
topology fine. They do not — they are handed it.

### 8.2 The "the model arrives with Q nearly right" defence is REFUTED

The natural defence is that enforcement has to do far more violence to a
geometric arm (`flux` sits at `Q = 0`, so the entire coarse charge must be
injected as instantons) than to the learned lift, which should arrive close.
That would be a quantitative statement about the model's contribution that
survives granting everyone the enforcement step.

**It does not hold.** Both halves of the measurement already exist:

- `u1_2d/scripts/49_topo_weight_match_rate.py` measures the **raw sector match
  rate with the instanton projection OFF** — the fraction of generated
  configurations whose charge already equals their coarse conditioner's.
- `67_prolongator_topology.py` reports the same quantity for the geometric arms
  in its `sector_match` column.

At the same case (`L = 32`, `beta_f = 14.1464`):

| arm | raw sector match rate | mean `|dQ|` | `<Q^2>` of the raw lift |
|---|---|---|---|
| diffusion (3 baseline seeds) | 0.226 – 0.258 | 1.21 – 1.32 | 4.3 – 4.7 |
| `tile` / `halve` / `flux` | 0.234 | — | 27.5 / 0.0 / 0.0 |
| `ape` | 0.266 | — | 0.125 |
| `smear_mh` | 0.250 | — | 0.172 |

Coarse `<Q^2>` is 1.758. **The learned lift's raw match rate is statistically
indistinguishable from the geometric arms'**, and its raw `<Q^2>` overshoots the
coarse value by about 2.5x. The two fail differently — `halve`/`flux` are
deterministically `Q = 0` so their match rate is just `P(Q_coarse = 0)`, while
the model produces topology of the wrong magnitude — but neither arrives close,
and `mean |dQ| ~ 1.25` for the model is not obviously better than injecting
`Q_coarse` into a `Q = 0` configuration.

**Consequence.** The instanton projection is doing the topological work for the
learned pipeline too, not only for the geometric arms. Sector transport is a
property of the **ladder design** — the coarse ensemble is sampled where
sampling works, and `apply_coarse_charge` imposes it — and not of the score
network. The paper should not be revised to claim otherwise, and the ΔQ
experiment proposed in an earlier draft of this file should **not** be run as a
defence; it has effectively been run and the answer is unfavourable.

Caveat worth one check: these numbers are U(1), at `beta_f = 14.1464`, on the
`topo_weight` checkpoint variants. The headline result is U(2), where the raw
match rate has not been measured. `36_transport_check.py`'s "100% of fine charges
equal their coarse charge" is measured **after** enforcement and is a check that
enforcement works, not evidence that the model gets `Q` right unaided. Measuring
the U(2) raw match rate is cheap and would close this properly; expect it to
agree with U(1).

### 8.3 What actually survives as the model's contribution

After the above, two defences remain, and both are real:

1. **Raw local structure.** 6.47e-05 against the best geometric arm's 3.6e-03 at
   `L = 64` — a factor of 56, measured, at the deployed setting. This is the
   model's genuine advantage and the paper already has the number.
2. **No per-coupling tuning.** `smear` only beats the lift because its sweep
   count is tuned per coupling against the exact plaquette. Sec. V shows the
   learned lift working across 44 couplings with nothing tuned. **This is the
   strongest available answer to Kai and it is currently nowhere in the draft.**

Two more are plausible but untested:

3. **Composition.** Whether a geometric prolongator survives three successive
   lifts to `L = 128` is unknown; `45_multi_lift_compounding.py` tested the
   learned lift only.
4. **Cost.** `smear` carries a build cost of 21 s against the diffusion arm's
   entry in the same column; the tuning runs needed to choose its sweep count are
   charged in `17_prolongator_baseline.py` but have not been compared against the
   training cost amortized per configuration.

### 8.4 Revised experiment list for K1

Replacing the list in K1. In priority order:

- **a. Transfer-tuned `smear`.** Choose `smear`'s sweep count at one coupling and
  apply it unchanged at a neighbouring one, then re-score. This directly sizes
  defence 2, which is the argument the paper needs. Cheap: the arms already
  exist, only the tuning protocol changes.
- **b. Re-run `21_prolongator_observables.py` at `n_retherm_sweeps = 0`** so the
  extended-loop comparison matches the deployed pipeline.
- **c. Geometric arms through the full ladder to `L = 128`**, testing defence 3.
- **d. U(2) raw sector match rate** with the projection off, to confirm §8.2
  carries from U(1) — needed so the paper can state the division of labour
  correctly rather than implying the network supplies topology.
- **e. Write the subsection.** The honest framing: the ladder supplies topology,
  the model supplies untuned UV reconstruction, and a per-coupling-tuned
  classical smoother is a competitive alternative for the second of those at a
  single coupling.

### 8.5 Note on how this was nearly got wrong, twice

`67_prolongator_topology.py`'s docstring records that it was **argued** rather
than measured that `flux` carries the coarse charge for free, and that measuring
it "inverted a day of conclusions". The ΔQ defence retracted in §8.2 was the same
class of error made in the opposite direction — a plausible mechanism asserted
about the model's behaviour, refuted by data that already existed. Both involve
topology, both sound obviously right, and both are wrong. Measure before
claiming anything about what a map does to `Q`.

---

## 9. K1 second addendum (SUPERSEDED BY §10 — read §10 first) — the honestly-timed comparison, and the missing hot-start control

### 9.1 The `build s` column in §8 was not a like-for-like timing

`17_prolongator_baseline.py` offers two learned arms. `diffusion` **loads stage
03's saved ladder output** — its build cost is a file read, which is why it
prints 0 s. `diffusion_raw` regenerates the lift in place, "so it is timed on the
same footing as the geometric arms" (the script's own words). The table quoted in
K1 and §8 used the `diffusion` arm, so it charged `smear` for its construction
and the model for nothing.

The timed run is `out/u2_2d/prolongator_L64_diffraw/`:

| arm | `t_therm` slowest | abs. rel. dev. at t = 0 | build s |
|---|---|---|---|
| `smear` (25 sweeps) | **9** | **4.22e-07** | **8** |
| `diffusion_raw` | 42 | 6.29e-05 | 31 |
| `diffusion` (precomputed) | 0 | 8.21e-06 | 0 (file read) |

**On the honest row the learned lift loses on all three axes**: roughly 4x more
expensive to build, 150x further from exact at t = 0, and 4.7x slower to
thermalize.

**Open discrepancy that must be resolved before any of these are quoted.** This
run has `n_retherm_sweeps = 0`, so "rel err pre-retherm" and "|dP/P| at t = 0"
should be the same number. For `diffusion_raw` they are (6.29e-05 both). For
`diffusion` they are not (6.47e-05 vs 8.21e-06). Either the saved stage-03
artifact is not the same object the raw path produces — different checkpoint,
different sampler settings, or a retherm tail baked in upstream — or one of the
two columns is computed differently for the loaded arm. Until that is explained,
the favourable `diffusion` row should not be used.

Note also that `smear`'s tuned count differs between runs (25 here, 50 in
`prolongator_L64_noretherm`), and so does its result (4.22e-07 vs 2.51e-06).
That is expected — the count is tuned per run against the exact plaquette — but
it means no single `smear` number is "the" result, and it is further evidence
that the tuning is doing real work. See the transfer test, §8.4(a).

### 9.2 Correction to §8.3

Defence 1 in §8.3 ("raw local structure, 56x") is **weaker than stated there**.
It is a property of the raw lift, and the deployed pipeline never ships the raw
lift — the conditional SU(2) sweeps always run. The honest description of what
the two routes do:

- the learned map produces a good configuration directly;
- `smear` produces a bad one (`flux`, -9.65e-02) and repairs it with cheap exact
  local updates.

Only the end states matter, and `smear`'s end state is better and cheaper. So the
list of surviving defences reduces to **one measured-but-untested item**
(per-coupling tuning, §8.4(a)) and **one untested item** (composition, §8.4(c)).
Topology is not a defence at all, per §8.2.

### 9.3 NEW, and the control that should be run first

**Arm: hot start -> `apply_coarse_charge` -> classical local smoothing -> HMC.**

Not present anywhere in the repo. The existing `hot` and `cold` arms receive no
charge enforcement, and every prolongator arm starts from the coarse field, so
nothing currently isolates the contribution of the coarse configuration's
*long-distance structure* as distinct from its *charge*.

Why it is the sharpest available test:

- If it performs like `flux` + enforce + `smear`, then the coarse configuration
  contributes **nothing but its topological charge**. The inverse-RG framing then
  reduces to "impose `Q` on a smoothed random configuration", which needs no
  diffusion model and no coarse ensemble beyond a charge draw. That would be a
  much smaller paper, and better to discover it ourselves.
- If it fails, the coarse long-distance structure is doing real work. **That is
  the paper's central premise and it is currently assumed, never shown.**

Either result is worth having. Not knowing is the exposure. Add it as an arm to
`17_prolongator_baseline.py`; the post-processing path already exists, only the
starting configuration changes.

### 9.4 The cost accounting this forces

Absent a qualitative win, the comparison becomes a cost analysis, and Sec. IV E
already half-concedes the outcome: "the campaign that produced the checkpoint
costs more than every classical burn-in that converges."

A fair accounting needs, on the learned side: training-data generation, training
wall-clock, and per-configuration sampler cost, amortized over the number of
configurations and couplings a single checkpoint serves. On the classical side:
the per-coupling tuning runs plus ~8 s per configuration. This has never been
assembled.

Expected shape of the answer, worth stating as the hypothesis the experiment
tests: **at a single coupling the classical route should win**, because tuning is
cheap and training is not; **across many couplings the learned route should
win**, because the checkpoint amortizes and the tuning does not. Sec. V already
has 44 couplings on the learned side and zero on the classical side, so the
comparison is one `smear` tuning sweep away from being makeable.

If that is how it comes out, it is a perfectly good result and a more honest one
than the paper currently claims — but it has to be measured, and it changes what
the abstract can say.

---

## 10. K1 third addendum (HEADLINE SUPERSEDED BY §11 — read §11 first) — the MATCHED run, which supersedes §8 and §9

**Sections 8 and 9 compared unmatched arms and reached the wrong conclusion.
This section supersedes both on the question of whether a classical prolongator
beats the learned lift.** Sections 8.1 (the two experiments measure different
things) and 8.2 (the raw sector match rate refutes the dQ defence) still stand.

### 10.1 Which runs are fair, and which are not

`17_prolongator_baseline.py` has four learned-side arms, and they are not
interchangeable:

| arm | what it is | fair? |
|---|---|---|
| `diffusion` | loads stage 03's saved ladder output | **No.** The code comment is explicit: loading it "would silently import ten rethermalization sweeps the geometric arms did not get." Do not use in the paper. |
| `diffusion_raw` | regenerates the lift in place, including `n_su2_sweeps` conditional SU(2) sweeps | Yes — a complete U(2) configuration, timed on the same footing |
| `diffusion_tuned` | `diffusion_raw` then `tune_smear`, the identical tuning `smear` gets | **Yes, and this is the matched comparison** |
| `smear` | `flux` then `tune_smear` | the classical competitor |

The contamination in `diffusion` is rethermalization sweeps — heatbath and
overrelaxation at fixed topology — **not** HMC trajectories. The ladder never
runs trajectories. So the arm is unfair but not catastrophically so; it simply
arrives with local updating the geometric arms were not given.

### 10.2 The matched result

`out/u2_2d/prolongator_L64_matched/`, L = 64, beta = 416.524, 0 retherm:

| arm | tuned sweeps | `t_therm` slowest | dev. at t = 0 | build s |
|---|---|---|---|---|
| `smear` | **15** | 6 | 2.47e-09 | 5 |
| **`diffusion_tuned`** | **5** | **1** | 1.50e-06 | 3 |
| `diffusion_raw` (untuned) | — | 24 | 6.37e-05 | 29 |
| `ape` | — | > 400 | 7.18e-05 | 2 |

**The learned lift needs one third the local-update budget to reach the exact
plaquette** — 5 tuned sweeps against `flux`'s 15 — and is cheaper to build and
reaches `t_therm` sooner. The two t = 0 deviations differ by three orders of
magnitude but both sit far inside the +-12.7 ppm equilibration band at this
volume (App. G, Table IV), so that column does not discriminate and should not
be quoted as though it does.

**The tuned sweep count is the right metric for this comparison.** It is what
the script was designed around: "the tuned sweep count is then a direct measure
of lift quality — how much local updating each starting point needs to reach the
exact plaquette." It is a single number, it is matched by construction, and it
does not depend on an error bar that is wider than either arm's deviation.

### 10.3 Consequence for the K1 response

The honest answer to Kai is therefore **not** that a classical prolongator wins.
It is:

- Yes, the ablation exists, with four non-learned arms receiving identical
  charge enforcement and post-processing.
- At matched tuning the learned lift needs 1/3 the local-update budget of the
  best classical prolongator at the benchmark coupling.
- Topology does not separate the arms, because enforcement supplies it to all of
  them — the sector comes from the ladder design, not from the network (§8.2).
- The open question is whether the 5-vs-15 margin holds away from a coupling
  where the classical arm's sweep count was tuned against the exact plaquette.

### 10.4 Revised experiment list, replacing §8.4 and §9.3

1. **Cold + `apply_coarse_charge` + `tune_smear`.** The control that isolates
   whether the coarse configuration contributes anything beyond `Q`. **Cold, not
   hot** — at beta = 416 the equilibrium is highly ordered (plaquette 0.9988), a
   cold start is 4.8e-03 away and a hot start never thermalizes within 400
   trajectories, so a hot arm would mostly measure how long heatbath takes to
   order a random field. If cold tunes to ~15 sweeps like `flux`, the coarse IR
   structure is contributing little beyond the charge; if it needs far more, it
   is doing real work. One new arm; the post-processing path already exists.
2. **Transfer-tuned `smear`.** Tune at one coupling, apply unchanged at a
   neighbour. Still the strongest untested defence. Note the tuned count already
   varies run to run — 50, 25, 15 — which is itself evidence that the tuning is
   doing work unavailable without a closed form.
3. **The matched run at a second coupling.** Currently beta = 416.524 only, so
   5-vs-15 could be a property of that point rather than of the method.

Dropped from earlier lists: the dQ measurement (refuted, §8.2) and the
hot-start arm (replaced by the cold-start control above).

### 10.5 Known bug affecting older prolongator outputs

The script records a fix: `smear` previously received `n_retherm` **on top of**
its tuned count, "which is why it always carried ~25 more sweeps than every
other arm and won comparisons it was not entitled to win." Determine which
output directories predate that fix before quoting any of them. The `_matched`
runs appear to postdate it; `_noretherm` and `_diffraw` should be checked.

### 10.6 Process note

Three successive readings of this ablation gave three different answers —
classical wins decisively, classical wins on honest timing, learned wins at
matched tuning — because the arms being compared were not the same each time.
The lesson for the write-up: **state which arm and which tuning protocol every
prolongator number comes from.** A table of these results without that column is
actively misleading, and the directory names alone do not carry it.

---

## 11. The prolongator beta scan (2026-10-16) — the measurement, and what it retires

Run after §10, and it **supersedes §10's headline** the way §10 superseded §8 and §9.
§10 reported "the learned lift needs 1/3 the local-update budget of the best
classical prolongator" (5 tuned sweeps against 15). That margin does not exist.
It was an artefact of the tuning estimator, which is fixed here, and the fixed
estimator plus a scan over eight couplings gives a different answer.

### 11.1 The estimator defect, and why it mattered

`tune_smear` chose its sweep count as an **argmin of |mean plaquette − exact|
over a stride of five**. Two independent defects:

* `check_every = 5` quantized every count to a multiple of five. The learned
  lift's "5" was therefore the **first grid point** — floor-limited, and in fact
  1 at most couplings when measured at single-sweep resolution. No margin finer
  than a factor of two was resolvable, and the reported 5-vs-15 and 5-vs-40
  ratios were comparing a floor against a measurement.
* The argmin had no notion of resolution. Once a configuration is inside the
  ensemble's own standard error the gap is pure noise, so the rule selected
  wherever noise happened to dip lowest. This is the same failure mode the
  project already fixed once, when the discrete `t_therm` threshold was replaced
  by a fitted estimator; it was reintroduced here.

The symptom was visible and was misread for weeks: `smear` returned **50, 25,
15 and 10 sweeps across four runs at the same coupling**. That was recorded in
§10.4 as "evidence that the tuning is doing work unavailable without a closed
form." It was evidence the estimator was unreproducible.

**The replacement** is a resolution-aware threshold crossing: the first `n` with
`gap <= 2 * SEM`, both measured across chains, every sweep checked. `n = 0` is a
real answer. The SEM is reported alongside so a margin can be read against the
resolution that produced it.

**Consequence to carry: the tuned sweep count is a bad endpoint for a good arm.**
At single-sweep resolution the learned lift crosses at n = 1 with gap/SEM of
1.1, 1.8, 1.2, 1.1, 2.4, 0.3, 1.9, 1.1 — i.e. it sits *on* the threshold, and
whether it reports 1 or 2 is decided by the threshold constant, not the physics.
The count has roughly one sweep of dynamic range. The informative quantity is
the **gap at n = 0**, which is `84_raw_seed_quality.py`'s endpoint and already
the project's standard for scoring a seed.

### 11.2 What was run

`17_prolongator_baseline.py`, extended with `--coarse-path` / `--beta` so it is
no longer limited to the two deployed ladder rungs, and with three new arms.
Eight couplings, L = 16 -> L = 32, coarse ensembles from `out/u2_2d/data_v2`,
fine beta from `topology_matched_fine_beta` so every point is a legitimate
inverse-RG step. 64 chains, 200 trajectories, `--n-retherm 0`, `--fixed-sweeps
25`. Output in `out/u2_2d/prolongator_scan/cb*`.

Fine beta 49.05 to 790.87 (model beta 12.3 to 197.7): six in-coverage points
including two essentially on a training rung and three in interpolation holes,
plus two past the top training rung (+29% and +90%).

**The arms, and which are deployable.** `tune_smear` consumes
`plaquette_exact`, which exists only because 2D U(2) is solvable. Every tuned
arm is therefore a **diagnostic**, not a configuration a practitioner could
run:

| arm | what it is | usable with no closed form |
|---|---|---|
| `diffusion_raw` | the learned lift, same post-processing as every other arm | yes |
| `diffusion_tuned` | `diffusion_raw` + resolution-aware tuned sweeps | **no** |
| `diffusion_fixed` | `diffusion_raw` + 25 transferred sweeps | yes |
| `smear` | `flux` + tuned sweeps | **no** |
| `smear_fixed` | `flux` + 25 transferred sweeps | yes |
| `cold_tuned` | ordered psi + enforced Q + tuned sweeps | **no** |
| `cold_fixed` | ordered psi + enforced Q + 25 transferred sweeps | yes |
| `cold` | plain cold HMC start, no enforcement | yes |

Comparing tuned arms against each other is legitimate for the ablation.
Quoting a tuned arm as the method's delivered cost is not.

### 11.3 The result

`t_therm` on the SLOWEST observable, so W(2x2), W(4x4) and W(8x8) are included:

| arm | sum t_therm over 8 couplings | median | t_therm = 0 | never converged |
|---|---|---|---|---|
| `cold_fixed` | **5** | 0.5 | 4/8 | 0 |
| `diffusion_tuned` | 21 | 0 | 5/8 | 0 |
| `diffusion_fixed` | 25 | **0** | 5/8 | 0 |
| `smear_fixed` | 28 | 0.5 | 4/8 | 0 |
| `cold_tuned` | 32 | 2 | 2/8 | 0 |
| `smear` | 51 | 5.5 | 0/8 | 0 |
| `diffusion_raw` | 147 | 10 | 0/8 | **3** |
| `cold` | 182 | -- | 0/8 | **7** |

**Read the median column before the sum.** `cold_fixed` is 2,1,1,0,0,0,1,0 and
`diffusion_fixed` is 0,11,8,0,0,0,0,6: by sum the cold control is 5x better, by
median the learned lift is. The sum is outlier-driven, and this file already
records that a single `t_therm` is rugged in coupling with ~10x scatter between
neighbours — visible here in `smear`'s 1,3,6,7,10,1,18,5. **The defensible
statement is that `diffusion_fixed` and `cold_fixed` are NOT SEPARATED by this
measurement**, both sitting at or near zero at most couplings. Do not write
"the cold control wins".

**Extended loops do not rescue the learned lift.** This was the open hope: the
plaquette is the most ultraviolet observable and therefore the axis where local
sweeps are strongest by construction, and u1's `59_pre_post_retherm.py` measures
local repair as a LOW-PASS filter (repair factor 64x at W(1x1) falling to 1.6x
at W(6x6)). If the classical arms degraded in the infrared the plaquette metric
would have been the wrong one. They do not: the table above is already the
slowest-loop number, and the classical arms reach zero on it.

### 11.4 Three corrections to the numbers as first reported

* **The build column understates the learned arms by ~14 s.**
  `diffusion_tuned` and `diffusion_fixed` reuse the lift cached by
  `diffusion_raw`, so their `build_seconds` charges only the sweeps. True cost
  is ~14-15 s of sampler plus tuning, so ~19 s against `cold_fixed`'s ~7 s.
  This is the same class of error as §9.1 (the `diffusion` arm charged nothing
  for a file read while `smear` was charged for construction) and §10.5 (the
  retherm-on-top bug). **Third occurrence. Any future prolongator table must
  carry a column saying what the build number includes.**
* **Eq. (16) has a ceiling of about 5 at these couplings.** The measured
  plaquette decorrelation interval is 4.93-4.96 trajectories at every point in
  the scan. So `F = interval / t_therm` cannot exceed ~5 for any arm with
  `t_therm >= 1`, and most arms sit at the bound with `t_therm = 0`. **The
  improvement factor on local observables is not a quantity that scales**, and a
  figure plotting it against beta will show a flat line at the ceiling with
  noise-driven dips. If F is to be the paper's headline it has to be the
  TOPOLOGICAL interval, which is orders of magnitude larger because the chain is
  frozen — and that interval is set by the ladder, not the lift.
* **Sweep counts need their chain count quoted.** The threshold is `2 * SEM`
  across chains, so the count answers "how many sweeps until indistinguishable
  at N chains". All arms within a run share N so comparisons are internally
  controlled, but a count from a 64-chain run is not comparable to one from an
  8-chain run (at 8 chains the same arms cross at 1-3 sweeps rather than 1-10).

### 11.5 The one striking positive

Past the training ceiling the raw learned lift fails completely: z(plaquette) at
record 0 is **109.5** at model beta 134 and **127.4** at model beta 198, and
neither converges within 200 trajectories. **Two to three sweeps bring both to
`t_therm = 0`.** Cheap exact local updates repair a lift that is 127 standard
errors from exact.

This cuts both ways and both should be written down. It means the coverage
ceiling is far less damaging to the delivered product than
`28_crossover_scan.py` suggests — the raw-lift collapse is repairable for 6-9
link touches. It also means the learned quality of the lift is not what sets the
delivered result, which is the same conclusion as §11.3 from the other side.

### 11.6 What the ablation now establishes, and what it retires

**Retired:**

* "The learned lift needs 1/3 the local-update budget" (§10.2). Estimator
  artefact.
* "No per-coupling tuning" as the model's strongest defence (§8.3, which called
  it "the strongest available answer to Kai"). The `*_fixed` arms kill it:
  because heatbath and overrelaxation are EXACT updates of the correct action,
  more sweeps are monotonically safe, so a practitioner needs no tuning — only
  generosity. 25 sweeps applied unchanged at all eight couplings lands every
  classical arm within 0.0-2.5 SEM of exact. There is no tuning advantage to
  claim.
* "Run-to-run variation in the tuned count is evidence the tuning does real
  work" (§10.4). It was evidence of a broken estimator.

**Established:**

* The learned lift produces a measurably better raw configuration: 3.3-127 SEM
  from exact against a cold start's 2.5e-03 to 4.3e-02 relative error. Real, and
  erasable by a move costing 3 link touches.
* In 2D, on local observables, the learned lift delivers no burn-in advantage
  over `cold_fixed` at roughly 3x the build cost.
* Charge enforcement plus cheap exact local sweeps is a complete solution to the
  2D preconditioning problem, at every coupling tested, in and out of coverage.

### 11.7 Why 2D cannot settle this, which is the honest framing

The reason the margin keeps collapsing is structural, not a defect in the model.
`retherm_sweeps` defaults to `update_phase=True, update_su2=True` with
`topological_updates=False` — heatbath plus two overrelaxations on BOTH sectors,
Q held fixed. Those are exact local updates of the full Wilson action restricted
to a topological sector, so in the many-sweep limit they sample `p(config | Q)`
exactly. At beta = 400+ the correlation length is about one lattice spacing, so
"the many-sweep limit" arrives in two sweeps.

So there are two exactness mechanisms in the pipeline, not one:

| mechanism | exact for | changes Q | cost per unit |
|---|---|---|---|
| HMC | the full measure | no, at these beta | `n_steps` touches (18-36) |
| heatbath + overrelaxation | the full measure at fixed Q | no, by construction | **3** touches |
| `conditional_su2_sweeps` | `p(q | psi)` at frozen psi | no, psi bit-for-bit | -- |

The preconditioner never has to be exact — that is HMC's job. It has to deliver
the right Q, which neither exact move can manufacture, and otherwise be close
enough that the burn-in is short. **In 2D the second requirement is met for 75
link touches by an ordered field, so there is no room left for a better
preconditioner: `t_therm` is already zero.**

The division of labour as measured, therefore:

* **Q** — the ladder's charge transport. NOT the network: §8.2 established the
  raw sector match rate is indistinguishable from the geometric arms. This is
  the piece nothing cheap replaces and it is the paper's real contribution.
* **Local structure at fixed Q** — cheap exact sweeps suffice in 2D.
* **Exactness** — HMC, or equivalently the sweeps.

**So the 2D results demonstrate that the mechanism works and that topology
transports exactly, configuration by configuration. They do not demonstrate that
the learned lift is necessary, and the paper should not imply they do.**

### 11.8 The scaling result, which is the cleanest number in the scan

Item (c) of §12.5, answered from the saved `tuning_history` with no new runs.
The resolution-aware tuned count at each coupling, i.e. the sweeps needed to
become indistinguishable from the exact plaquette at 64 chains:

| arm | 49.1 | 73.1 | 138.6 | 200.8 | 291.7 | 414.9 | 537.4 | 790.9 | max |
|---|---|---|---|---|---|---|---|---|---|
| `diffusion_tuned` | 1 | 1 | 1 | 1 | 2 | 1 | 2 | 3 | 3 |
| `cold_tuned` | 2 | 2 | 2 | 3 | 2 | 2 | 2 | 2 | **3** |
| `smear` | 3 | 5 | 5 | 5 | 6 | 8 | 9 | 10 | **10** |

**`smear` is the only arm whose requirement grows with beta** — monotone, 3.3x
across a factor of 16 in coupling. The cold control is FLAT at 2-3 and the
learned lift is flat at 1-3. The mechanism is not subtle: equilibrium becomes
more ordered as beta rises, so an ordered start gets relatively closer to it
while `flux`'s flux-spread lift gets relatively further.

Two consequences, and the first is the answer to "how does the improvement
factor scale":

* **What scales is the opposite of the desired claim.** The classical
  PROLONGATOR degrades up the ladder; the cold control and the learned lift do
  not. So a figure of margin-versus-beta shows the learned lift pulling away
  from `smear` and NOT from `cold_fixed` — and `cold_fixed` is the baseline that
  matters, because it is the cheap one.
* **A fixed count of 3 sweeps (9 link touches) suffices for the cold route at
  all eight couplings**, against `smear`'s 10. The 25 used for the `*_fixed`
  arms in §11.3 was ~8x over-generous, so the cold route's true cost is 9 link
  touches plus ~0 trajectories, not 75. Caveat before quoting 3: the tuned count
  is a stochastic crossing of a 2-SEM threshold, so a fixed 3 applied to a fresh
  ensemble will sometimes miss. Quote it as "single-digit sweeps", and if a
  number is needed, re-measure with a margin (e.g. first n with gap <= 1 SEM for
  three consecutive n) rather than reusing a crossing as a setting.

---

## 12. The instanton-insertion dependence — a retracted defence, and the claim that survives

Written the same day as §11, because §11's framing initially rested on an
argument that does not hold.

### 12.1 The argument, and why it is wrong

The natural defence of the learned lift after §11 is that each leg of the cheap
classical route breaks in 4D SU(3):

1. there is no analytic instanton insertion in SU(3), so you cannot stamp a
   sector onto a cold field at all;
2. local sweeps are a low-pass repair and 4D has a real infrared for that decay
   to matter to;
3. heatbath at fixed topology is not a practical route to 4D long-distance
   structure.

**Leg 1 is self-defeating and must be withdrawn.** `apply_coarse_charge` is
`wrap(sample + delta_q * instanton_field(L))` — a closed-form smooth instanton
for a compact abelian lattice field, iterated up to three times for wrap misses
(`u1_2d/pipeline/ladder.py:227`). And it is not applied only as a final stamp:
`generate_fine_from_coarse` installs it as a `step_callback` INSIDE
`sample_ancestral`, firing every `charge_projection_interval = 10` steps once
`sigma_next < charge_projection_sigma = 0.5`
(`u2_2d/pipeline/ladder.py:218-230`). So the reverse diffusion's entire
topology-correcting mechanism IS the analytic instanton insertion, used more
pervasively than `cold_fixed` uses it. An argument from its unavailability in 4D
is an argument against this method first.

Legs 2 and 3 are the same claim stated twice.

**So exactly one differentiator survives, and it is untested:** in 4D, cheap
exact local sweeps do not equilibrate the infrared, and a learned lift
conditioned on the sector does.

### 12.2 The real softening, and why it does not restore the defence

The insertion does not have to produce a good configuration — only to land
reliably in the target sector. Everything downstream samples `p(config | Q)`
correctly (HMC is Metropolis-exact; heatbath and overrelaxation are exact local
updates; neither can leave the sector), so an ugly inserted lump is annealed
away and the sector frequencies still come from the coarse ensemble. This is the
deployment-time analogue of the argument this project already makes for training
data, where `sector_augment` supplies coverage with deliberately wrong
frequencies and lift quality is unaffected.

That genuinely weakens the 4D requirement from "closed-form exact instanton" to
"any reliable way to reach a target sector" — for which there are candidates: a
discretized BPST instanton embedded through an SU(2) subgroup, or PTBC used to
manufacture global topological moves, which was its original purpose.

**But the softening applies identically to `cold_fixed`.** Whatever reaches the
sector in 4D, cold + that + sweeps is still available. It does not restore a
differentiator; it means neither route is dead in 4D.

### 12.3 What has to be written, and where

This lands precisely on the gap the §VI audit (§5 of this file) already
identified: of the three obstacles the Outlook names, the SECOND has a developed
proposal, the third has one subordinate clause, and **the first — the
blocking/Q-definition question, which is this one — has none**. Qianteng's
complaint that the Outlook states limitations rather than future directions is
the same observation.

So:

1. **The 4D generalization paragraph cannot lean on "no cheap classical
   alternative exists there."** It has to state that the transport step requires
   a sector-reaching move in SU(3), that we do not have one, and that this is a
   precondition for the whole approach rather than a detail.
   **CORRECTION (2026-10-20): the paper ALREADY DOES this and the original
   version of this item said otherwise.** `current.tex:1085-1100` states that
   the charge-setting construction is used twice (training-data coverage and
   imposing `Q_coarse` on the lift), that it exists because U(2) decomposes with
   the charge on the abelian factor, that "SU(3) has no such decomposition, and
   a cheap topology-changing update for it is the central open question here",
   and then lists four candidate replacements with citations -- PTBC
   (hasenbusch2017, bonanno2021, bonanno2024), the boundary-opening /
   stochastic-normalizing-flow route already scaled to 4D SU(3)
   (bonanno2025su3, bonanno2026), sector-jumping stochastic dynamics
   (rothkopf2026), and a bias of the generating action via multicanonical
   sampling or metadynamics (bergneuhaus1992, laio2016, eichhorn2026) -- naming
   the last as most promising. The false claim came from grepping for
   "instanton"; the passage says "charge-setting construction". **Grep for the
   concept, not the word, before asserting the paper omits something.**
2. **The 2D results should be presented as mechanism-demonstrated and
   topology-transported-exactly, not as lift-necessary.**
3. **A concrete proposal for obstacle 1 is the highest-value piece of new
   writing available**, and it does not need new computation: name the candidate
   sector-reaching moves, state what each would cost, and say which one the
   method would use. That converts the Outlook's weakest point into its
   strongest and answers Qianteng directly.

### 12.4 Why the 2D result should not be expected to carry to 4D SU(3)

§11 established that in 2D a classical preconditioner plus charge enforcement
plus single-digit local sweeps is not separated from the learned lift. The
obvious question — and the one Kai will ask next — is whether that kills the
method or is a property of two dimensions. **It is the latter, and the reason is
structural rather than a matter of degree, but it is REASONED AND NOT MEASURED
and must be labelled that way wherever it is written.**

The 2D classical route works because three things are simultaneously true of the
determinant sector, all of which follow from it being an ABELIAN field in which
`Q = sum_p wrap(arg det P) / 2 pi` is a sum of wrapped plaquette angles:

1. **The instanton insertion that sets the sector is exact and closed-form.**
   `apply_coarse_charge` adds `delta_q * instanton_field(L)`, a known smooth
   configuration, and three iterations fix any wrap-induced miss.
2. **Local updates leave Q untouched.** `retherm_sweeps` runs with
   `topological_updates=False`, and measured `<Q^2>` is unchanged to all printed
   digits across 0-40 sweeps. Note the precise reason, because it is
   coupling-dependent: at beta = 400+ the plaquette angles are small enough that
   no heatbath proposal takes one across pi, so the sector is dynamically
   inaccessible. At strong coupling heatbath WOULD change Q, so this is a
   high-beta property and not a symmetry.
3. **The correlation length is about one lattice spacing**, so local updates
   equilibrate everything except Q almost immediately — two sweeps, measured at
   eight couplings (§11.8).

**All three fail for SU(3) in four dimensions, and they fail independently:**

1. **There is no exact lattice instanton to insert.** A discretized BPST
   configuration embedded through an SU(2) subgroup is approximate; it is not a
   solution of the lattice equations and does not land in a sector exactly.
   (This leg costs OUR method too — see §12.1, which is why it cannot be used as
   a differentiator. It is listed here because it breaks the classical route's
   *cheapness*, not its availability: an approximate insertion needs an
   accept/reject or a relaxation stage that the 2D closed form does not.)
2. **Local smoothing does not preserve the topological charge.** This is the
   leg with no 2D analogue at all. Under cooling, smearing or gradient flow in
   4D SU(N), instantons of radius comparable to the lattice spacing shrink and
   fall through the lattice, so the charge of a configuration CHANGES under the
   very operation the classical route uses to repair it. "Prolong, enforce Q,
   then smooth" is therefore not a Q-preserving procedure in 4D the way it is
   here — the smoothing can undo the enforcement. **ACTION: this is standard
   lattice-QCD knowledge and the project has a standing rule preferring citable
   results to asserted ones. Find and cite the reference before this goes in the
   paper; do not assert it unsourced.**
3. **Local updates face a real correlation length.** The 2D result rests on
   two sweeps sufficing. In 4D SU(3) at physical couplings the correlation
   length spans several lattice spacings, local algorithms carry critical
   slowing down in it, and the infrared is where the division-of-labour
   measurement (`u1_2d/scripts/59_pre_post_retherm.py`) already shows local
   repair to be weakest — repair factor 64x at W(1x1) falling to 1.6x at
   W(6x6). A low-pass repair against a trivial infrared is sufficient; against a
   real one it is not.

**How to state this, and how not to.** The defensible sentence is: *the 2D
classical route exploits three properties of the abelian determinant sector,
each of which fails for SU(3) in four dimensions, so we do not expect the
comparison to transfer — but we have not measured 4D and this is a statement of
expectation.* Do NOT write that classical preconditioners fail in 4D, and do
NOT write "for some reason" — the mechanism is nameable and vagueness here
invites exactly the objection the section exists to answer.

**And note what this does for the Outlook, as corrected.** The §5 audit found
that of the three obstacles only the SECOND -- a cheap topology-changing update
-- has a developed proposal. That is exactly the obstacle the instanton
dependence belongs to, and `current.tex:1085-1100` does develop it: four
mechanisms, cited, with a stated preference. **So this argument needs no new
Outlook writing for obstacle 2.**

What items 1 and 2 above DO add is a requirement the existing passage omits: a
4D transport step needs a sector-reaching move **and** a repair stage that does
not undo it. The Outlook addresses only the first half. Since smoothing in 4D
does not preserve `Q`, a mechanism that reaches a sector is not sufficient by
itself, and naming that pair is a genuine addition -- one sentence, no new
computation. Obstacle 1 (blocking, and the definition of `Q` under it) remains
the one with no proposal; do not conflate the two.

### 12.5 Experiments this leaves worth running

In priority order, and the first is the only one that can change the headline:

* **a. The U(1) analogue of `cold_fixed`.** It does not exist anywhere in the
  repo: `37_tiling_baseline.py` applies no charge enforcement, and
  `67_prolongator_topology.py` measures the prolongators unaided (`halve` and
  `flux` give Q = 0 on every configuration). So cold + enforce + 25 fixed sweeps
  has never been run in u1 — and u1 is where the loop-size hierarchy is already
  measured, so it is the sharper test of whether "enough local sweeps" really
  gets you everything. Port `cold_psi` and `fixed_smear`; score on extended
  loops, not the plaquette.
* **b. Topological charge density and its correlator**, comparing interleaved
  projection against stamp-then-smooth. This is the only observable class that
  targets the design intent — UV structure generated conditional on the winding,
  rather than a winding annealed into an ordered field. Expect a null result in
  2D for the §11.7 reason, and note that a null result is itself the cleanest
  statement of why 2D is the wrong testbed.
* **c. The sweep count the `*_fixed` arms actually need.** 25 was chosen as
  generous. The `tuning_history` field now saved by `tune_smear` records
  gap/SEM at every sweep for the tuned arms, so the minimum sufficient count is
  readable from existing output with no new runs.
* **d. A second seed at the three couplings with outlier `t_therm`** (73.13,
  138.55, 537.38). This file records that a low-but-passing p-value is worth a
  second seed rather than a footnote; the same applies to a `t_therm` that
  breaks its neighbours' trend by 10x.

Dropped: the transfer-tuned `smear` test (§10.4 item 2). The `*_fixed` arms are
that test, run, and the answer is that transfer is not the classical route's
weak point — generosity substitutes for tuning.

---

## 13. Kai's four points — resolution record (2026-10-20)

§6 listed K1-K6 with proposed actions. Two of them now have measurements rather
than proposals, and the wording fixes have line numbers. **This section is the
resolution status; §6 remains the analysis and should be read first.**

| item | §6 status | status now |
|---|---|---|
| K1 non-neural prolongation | control missing, work exists | **RUN — §11. Answer is unfavourable and should be reported as such** |
| K2 Eq. (15) on the torus | needs a sentence | unchanged; exact edit below |
| K3 "draws exactly" | wording is wrong | unchanged; exact edit below |
| K4 marginal move validity | known open item | unchanged, and the open hint must be disclosed, not buried |
| K5 budget is not a bound | real overreach | **MEASURED — the stationary interval is 4.7-5.2 trajectories, so the bound overstates by ~2 orders of magnitude on local observables** |
| K6 cost placement | move material earlier | unchanged; and note the two cost comparisons point OPPOSITE ways |

### 13.1 K5 is now a measurement, not an argument

§6 K5 offered an alternative — "measure `tau_int` on a THERMALIZED classical
chain at those couplings... that gives a legitimate stationary `2 tau_int` and
makes `F` well defined." **That has now been done**, as a by-product of the §11
scan: `17_prolongator_baseline.py` records `tau_int_tail`, the mean per-chain
integrated autocorrelation time over the second half of each arm's history,
computed only on arms that actually equilibrated so the tail is stationary.

Stationary `2 tau_int` by observable, median over equilibrated arms:

| fine beta | plaquette | W(2x2) | W(4x4) | W(8x8) | max over loops |
|---|---|---|---|---|---|
| 49.1 | 4.81 | 3.87 | 3.33 | 2.27 | 4.81 |
| 73.1 | 4.93 | 4.08 | 3.31 | 2.45 | 4.93 |
| 138.6 | 4.88 | 3.80 | 3.40 | 2.75 | 4.88 |
| 200.8 | 4.93 | 4.09 | 3.78 | 3.27 | 4.93 |
| 291.7 | 5.17 | 4.16 | 3.89 | 3.44 | 5.17 |
| 414.9 | 4.99 | 3.87 | 3.72 | 3.09 | 4.99 |
| 537.4 | 5.12 | 4.08 | 4.14 | 3.39 | 5.12 |
| 790.9 | 4.69 | 4.07 | 3.89 | 3.31 | 4.69 |

**The interval maximized over loops is 4.69-5.17 trajectories and FLAT across a
factor of 16 in beta.** Two consequences:

* Where `F` is quoted as `>= budget / t_therm` with a budget of 400 or 2000
  trajectories, the local-observable interval is overstated by **roughly two
  orders of magnitude**. Kai's objection is not a technicality; it is the
  difference between `F ~ 80` and `F ~ 1`.
* **The plaquette has the LONGEST interval of the four**, and larger loops
  decorrelate faster (4.8 down to 2.3 at W(8x8)). So maximizing over loops, as
  Sec. IV A does, does not rescue the number — it selects the plaquette, which
  is already the slowest. An earlier assumption that extended loops would carry
  a longer interval is wrong.

**So Eq. (16) on local observables has a ceiling of about 5**, reached by any arm
with `t_therm <= 1`, and most arms in §11 sit at it with `t_therm = 0`. It is not
a quantity that scales with coupling, and a figure plotting it against beta shows
a flat line at the ceiling with noise-driven dips.

**The split that fixes this, and it is by OBSERVABLE not by arm:**

* On **topology** a frozen classical chain genuinely has no finite interval —
  §6's own note that "an arm whose charge never moves has no finite interval"
  (`current.tex:628`) is correct, and an unbounded `F` is defensible there.
* On **local observables** the interval is ~5 and is measured. `F` must be
  reported against that number, not against a budget.

The abstract's "cheaper by a median factor of at least nine" is a median over 24
budget-constructed bounds and **does not survive** on local observables. Report
the topological claim, which does, and quote the measured interval for the local
one.

### 13.2 The exact wording edits, with line numbers

**K2, `current.tex:582-590`.** The text already says "Integrating SU(2) out of
*one plaquette* by the one-link integral gives the marginal weight of the
determinant plaquette angle", and Eq. (15)'s only role is to fix `beta_1` via the
minimum-KL projection at `current.tex:1311`. So the draft does not claim what
Kai asks about — but it reads ambiguously enough that a careful reader asked.
Add one clause: that Eq. (15) is a single-plaquette marginal used only to define
`beta_1`, and that the finite-torus measure is the character expansion of
App. exact, which is what every validation number is scored against.

**K3, `current.tex:596-598`.** Currently: heatbath sweeps "draw it exactly from
`p(q | psi)` while leaving `psi`, and hence `Q`, unchanged." The second half is
exactly true (`update_phase=False` returns `psi` bit-for-bit). The first half is
wrong. Replace with: each heatbath update is an exact draw from the link's exact
conditional, so the sweeps leave `p(q | psi)` invariant and have it as their
stationary distribution; the finite sweep count is the one approximation. Then
cite `34_marginal_move_bias.py`: odd/exact = 1.00065 (z = +0.26) at the deployed
25 sweeps, 0.99994 (z = -0.02) at 100, and 0.99386 (z = -2.40) at 5.

### 13.3 K4 — what must be disclosed rather than buried

The marginal winding update is a marginal-propose / conditional-resample
composite, so it targets `p(psi, q)` exactly only if `w_det` is the exact
marginal (K2) and the SU(2) redraw is exact (K3). Since K3 is finite-sweep, the
move's correctness is **measured, not proved**, and the measurement has a loose
end that should be stated in print:

* no detectable bias at the deployed setting across six cells at L=8;
* charge conjugation (`U -> U*` sends `Q -> -Q`, so `P(Q)` is exactly even and
  `<sign Q>` must vanish) scatters within +-2 sigma with mixed signs at all seven
  couplings — and this test needs NO closed form, so it cannot be blamed on the
  reference;
* **but** a sub-percent odd-weight deviation at L=16, beta=28 sits at z = +2.61,
  and the verdict's calibrated power at that effect size is only 15-22%. Neither
  dismissible nor established. Settling it needs ~5-10x the statistics at that
  one coupling.

**Write the third bullet down.** It is the kind of item a referee finds and a
reviewer who was told about it forgives.

### 13.4 K6 — and the thing §6 did not say

§6's action (state the exclusion where `F` is defined) stands. What §6 missed is
that **the two cost comparisons point in opposite directions**, and reporting
only one is what makes the section read as special pleading:

* **Local observables:** including base generation, at L=64, beta=416.5,
  HMC+winding delivers an independent configuration in 0.212 s and the ladder in
  0.410 s — the ladder is **2.39x SLOWER**. Training cost is on top.
* **Topology:** reaching the same sector coverage costs **2.94x less** at the top
  rung and **6.37x less** at the middle rung than the classical route with its
  expensive odd-charge move.

Report both, separately, and say which observable each belongs to. The honest
headline is that the method buys topology and loses on local observables, which
is also exactly what §11 found by a different route.

### 13.5 The through-line for the reply, and for the paper

Three of Kai's four points are concessions and the fourth (K2) is a clarity fix.
They are not independent: K2 and K3 are the two premises the marginal move's
correctness rests on (K4), and K5 and K6 are the same error in two places —
quoting a number whose denominator or excluded cost was never measured. The
single discipline that prevents all of them is the one this file keeps
rediscovering: **before quoting a ratio, ask what value it would take if nothing
were wrong, and whether both its terms were measured on the same footing.**
