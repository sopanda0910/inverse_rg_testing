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

---

## 14. Lingxiao Wang — meeting 2026-10-23, with proposed fixes for approval

From `TODO.md`, written up during the meeting. Nine items; each gets the
diagnosis and a specific proposed edit. **Nothing here is applied yet.**

**Note the convergence before reading the list.** L3 and L7 are the SAME defect
Kai raised as K5, arrived at independently. Three readers have now hit the
`t_therm`/interval treatment, which makes it the highest-priority change in the
paper regardless of effort.

### L1 — "We shouldn't state it is an inverse RG since we aren't actually doing inverse RG"

**He is right about what we do, and the phrase oversells it.** The RG map is
many-to-one -- it integrates degrees of freedom out -- so it has no inverse. What
the model actually does is sample from the CONDITIONAL distribution of the fine
field given its blocked image, along a coupling-matched trajectory. That is a
well-defined object and a legitimate one; it is just not an inversion.

Four occurrences (`grep -ci "inverse renormalization\|inverse RG"` = 4):

| line | what it describes | action |
|---|---|---|
| 62 (abstract) | **our own operation** | **change** |
| 129 | other authors' use of inverse RG transformations | keep |
| 131 | `cotler2023`, diffusion/inverse-RG-flow connection | keep |
| 132 | "the inverse RG step has itself been..." (others' work) | keep |

So only ONE sentence describes us, which makes this cheap.

**PROPOSED FIX.** Abstract line 62: "it performs one inverse
renormalization-group step, upsampling a coarse configuration to a fine one"
-> "it performs one RG-matched upsampling step, generating a fine configuration
conditioned on a coarse one". Keep lines 129-132 verbatim: they describe the
literature, where the term is established, and dropping them would lose the
connection to `cotler2023` that motivates the architecture. Then sweep §II-§III
for any remaining self-description in those terms.

**Do NOT rename the repository or the code.** `inverse_rg_testing`, `det_lift`
and friends are identifiers, not claims.

### L2 — "Make the cold/hot start definition more clear"

Cold and hot appear ~10 times (abstract, §III, §IV, the benchmark tables) and
are **never defined**. A reader outside the group cannot tell whether "hot"
means Haar-random links, random in the algebra, or a high-temperature
equilibrated ensemble.

**PROPOSED FIX.** One sentence at first use in the methods section, giving the
construction and what each is for:

> A *cold* start sets every link to the identity, the ordered extreme
> ($\langle\frac12\mathrm{Re\,Tr}P\rangle = 1$, $Q = 0$); a *hot* start draws
> each link independently from Haar measure, the disordered extreme. They
> bracket the equilibrium ensemble, which at the couplings studied here sits far
> closer to the cold end.

Then add the measured justification for why cold is the meaningful classical
baseline and hot is only a bracket: at $\beta = 416.524$ the equilibrium
plaquette is $0.9988$, so a cold start is $4.8\times10^{-3}$ away while a hot
start is $O(1)$ away and does not thermalize within 400 trajectories (it sits
flat at $6\times10^{-2}$). Without that, a reader wonders why the hot arm is
reported at all.

### L3 — "We use a finite thermalization"

**This is Kai's K5 from the other direction** and the two fixes must be written
once, not twice. `t_therm` is a FIRST CROSSING against a per-record band WITHIN A
FINITE TRAJECTORY BUDGET. The budget is a property of the experiment, not of the
chain, and **nothing about the stationary $\tau_{\rm int}$ follows from failing
to cross it** -- which is exactly what Sec. IV E currently infers
(`current.tex:816-819`).

**PROPOSED FIX**, merging with §13.1:

1. Where `t_therm` is defined, state plainly that it is a finite-budget
   crossing, that an arm which does not cross is reported as `> budget` against
   its own budget, and that no bound on $\tau_{\rm int}$ is implied.
2. Delete the lower-bound construction at `current.tex:816-819`. Replace the
   budget substitution with the MEASURED stationary interval (§13.1:
   $2\tau_{\rm int} = 4.69$--$5.17$ trajectories, flat across $\beta = 49$ to
   $791$ at $L = 32$).
3. Relabel Fig. 5's triangles: they are not lower bounds. See L8.
4. Rephrase the abstract's "cheaper by a median factor of at least nine", which
   is a median over 24 of those constructions.

### L4 — "Fix the figure, explain why there are more FiLM blocks" (Fig. 1)

**Diagnosed, and there are two readings. Confirm which he meant before editing.**

The deployed U(1) checkpoint really is `depth = 4, hidden = 56, 324,954`
parameters, so the caption's "4 FiLM blocks of width 56" is CORRECT about the
model. The confusion is in the drawing (`u1_2d/scripts/57_schematics.py`):

* **Reading A -- he counted boxes.** Line 159 draws **five** boxes:
  `xs = [0.0 + i * pitch for i in range(5)]`. They are pipeline STAGES, not
  blocks -- (1) noisy links + coarse field, (2) gauge-invariant features,
  (3) *"4 FiLM blocks, width 56"*, (4) scalar head, (5) plaquette curl. Only box
  3 is the FiLM stack. Five boxes beside a caption saying "4 FiLM blocks" is an
  easy mis-read.
* **Reading B -- he counted FiLM consumers.** The FiLM embedding box spans boxes
  3 and 4 and sends an arrow into EACH (`for x in (xs[2], xs[3])`). The code's
  own comment says it "must span both consumers of the embedding, the residual
  blocks and the head's force gate". So FiLM modulation enters in **two** places
  while the caption mentions only the residual stack. That is a genuine
  omission, not just a drawing artefact.

**PROPOSED FIX, which covers both readings:**

1. Caption enumerates the stages explicitly, so "five boxes" cannot be read as
   "five blocks": *"Left to right: input, gauge-invariant features, the stack of
   four FiLM-modulated residual blocks, the scalar head, and the curl that makes
   the output gauge-covariant."*
2. Caption states the second FiLM consumer: *"The $(\log\sigma, \log\beta)$
   embedding modulates both the residual stack and the head's Wilson-force
   gate."*
3. In the figure, label box 3 "**stack of 4** FiLM blocks" rather than "4 FiLM
   blocks", and label the two embedding arrows.
4. Give the U(2) numbers in the caption the same treatment
   (`hidden = 64`, `403,394` parameters, same depth).

### L5 — "Maybe we don't want to use ppm, use standard HMC uncertainties and a z-score"

**He is right, and this is already the project's own standing rule being
violated in the paper's prose.** The internal standard
(`84_raw_seed_quality.py`) is to report BOTH `Z = |mean - exact|/SEM` and the
relative deviation, with the rule: *at fixed coupling the ratio is comparable
between arms, because both face the identical spread; ACROSS couplings use z.*

The paper has 26 ppm occurrences and the abstract is ppm-only -- "35 parts per
million against a cold start's 1200", "6 parts per million against 25" -- which
is exactly the across-coupling, across-volume case where a bare ratio is least
defensible. A lattice reader also simply expects a mean with its statistical
error.

**PROPOSED FIX.**

1. **Abstract and every cross-coupling or cross-volume comparison lead with
   $z$**, with the relative deviation in parentheses where it adds something.
2. Keep ppm at FIXED coupling where both arms face the same per-configuration
   spread and the ratio is meaningful.
3. **Never quote a ppm ratio across couplings or volumes.**
4. **Check the $6$ vs $25$ figure before it survives into the revision.** That is
   a factor of 4 after 400 trajectories at $L = 128$, and this project has
   already quoted one seed error that was at the ensemble's sampling floor. The
   $35$ vs $1200$ pair, a factor of 34, is safe.

### L6 — "Don't use 'lifted configuration'; use upsampling or similar"

Pervasive: 68 "lift", 25 "lifted", 11 "lifted configuration". The term is ours
and carries no meaning outside the group.

**PROPOSED FIX**, and it should be consistent with L1's replacement:

| current | proposed |
|---|---|
| lifted configuration | **upsampled configuration** |
| the lift (the operation) | **the upsampling step** |
| the lift (the model's output) | **the upsampled configuration** |
| lifted chain | **preconditioned chain** |

"Preconditioned chain" for the HMC run is worth keeping -- it matches the title
and the central claim, and distinguishes the CHAIN from the CONFIGURATION it
started from, a distinction the current text blurs.

**Prose only.** `det_lift`, `lift_batch`, `generate_fine_from_coarse` and the
rest are identifiers and stay.

### L7 — "Show improvement factors compared to local observables and IR observables"

**Same defect as K5 and L3, and we already have the measurement.** Stationary
$2\tau_{\rm int}$, median over equilibrated arms, from the §11 scan:

| fine beta | plaquette (UV) | W(2x2) | W(4x4) | W(8x8) (IR) |
|---|---|---|---|---|
| 49.1 | 4.81 | 3.87 | 3.33 | 2.27 |
| 200.8 | 4.93 | 4.09 | 3.78 | 3.27 |
| 414.9 | 4.99 | 3.87 | 3.72 | 3.09 |
| 790.9 | 4.69 | 4.07 | 3.89 | 3.31 |

**PROPOSED FIX: report $F$ in three columns -- UV (plaquette), IR (largest
Wilson loop), and topology ($\langle Q^2\rangle$)** -- rather than one number
maximized over loops.

**CORRECTED 2026-10-24 -- do NOT lead with "larger loops decorrelate faster".**
An earlier version of this item proposed that as a headline. It is most likely a
SIGNAL-TO-NOISE ARTEFACT, not a statement about the theory. `tau_int` is built
from the NORMALIZED autocorrelation `rho(t) = C(t)/C(0)`, so an observable
carrying a large trajectory-to-trajectory-independent component has that
component inflate `C(0)`, shrink `rho(t)` at every lag, and pull `tau_int`
toward its uncorrelated floor of 0.5. Large Wilson loops have exactly that:
per-configuration spread grows ~374x from W(1x1) to W(4x4), much of it
short-distance noise HMC refreshes in one trajectory. Measured `tau_int` is
1.15-1.7 at W(8x8) against 2.4-2.6 at the plaquette -- the large loop is the one
sitting near the floor.

**Before this appears in the paper, check it properly**: plot `rho(t)` for each
loop and ask whether the decay RATE differs or only the intercept. If only the
intercept, the correlated mode is common to all scales and the ranking is pure
dilution. Report the interval per observable because the cost formula needs it,
but do not dress the ordering up as physics.
The infrared slowness is real but it lives in THERMALIZATION, not decorrelation:
`t_therm` is maximized over loops and the largest loop is what sets it, while
local repair is a low-pass filter whose effectiveness falls 64x to 1.6x from
W(1x1) to W(6x6). Interval and thermalization order the scales OPPOSITELY, and
saying so is a better result than the single number we currently report.

Topology is the third column and the only one where a frozen classical chain
honestly has no finite interval -- so that is where an unbounded $F$ belongs,
and nowhere else.

### L8 — "Explain why we are doing winding HMC. The money plot is not clear"

Two separate asks.

**(a) Justify the baseline, early and explicitly.** `current.tex:276` asserts
winding HMC "is the classical baseline of record here" without saying why. The
reason is strong and should be stated where $F$ is defined: plain HMC is
TOPOLOGICALLY FROZEN at these couplings -- zero sector changes in 3000
trajectories at $\beta = 14.15/55.02/218.58$ -- so it has no finite topological
interval at all, and benchmarking against it would be a strawman that flatters
us. The winding update reproduces exact $\langle Q^2\rangle$ to 2% with
$\tau_{\rm int}(Q^2) \approx 1.2$--$2.9$ for a 1-18% overhead. A properly tuned
PTBC ladder costs 25-121x more and exists to manufacture a global topological
move for theories that LACK one; this theory has an exact one, so importing that
comparison measures nothing. **One short paragraph; all three numbers already
exist.**

**(b) The money plot (fig64) carries too many encodings.** Currently: three
checkpoints x two volumes x three marker shapes (circles measured, triangles
lower bounds, crosses no-factor) x dotted per-checkpoint ceiling lines x
chain-bootstrap error bars, all in one panel pair.

**PROPOSED FIX:**

1. **Remove the triangles as plotted.** They are the K5 artefact -- budget-built
   "lower bounds" that are not bounds. Either drop those couplings from the
   numeric axis and mark them in a rug or annotation strip reading "no classical
   equilibration within budget", or give them a measured value from the new
   stationary interval. **This is a correction, not a cosmetic change.**
2. **Facet by observable class** per L7: a UV panel, an IR panel, a topology
   panel. The topology panel is where the method's claim actually lives and it
   is currently buried in a maximized number.
3. **One checkpoint per panel, or small multiples.** Three checkpoints x two
   volumes in one axes is the main legibility problem.
4. Name the baseline in the axis label ("improvement factor over winding HMC"),
   so the plot stands alone.
5. Keep the training-ceiling lines -- they are the figure's best feature and
   they carry the abstract's last sentence.

### L9 — Timeline

Lattice conferences next **May** and **July**; workshops next **November**. The
revision implied by §13 and §14 is weeks, not months, so the May deadline is the
binding one. **Decide which venue is the target before starting, because it
determines whether the 4D SU(N) discussion (§12.4) is a paragraph of outlook or
a programme with preliminary numbers.**

### 14.1 Suggested order

1. **L3 + L7 + L8(a) together** -- one coherent rewrite of the $F$ definition,
   its measurement, and its baseline. Three reviewers, one defect; highest value.
2. **L5** -- $z$ throughout, ppm only at fixed coupling. Mechanical, touches the
   abstract, and verify the $6$ vs $25$ number while doing it.
3. **L8(b)** -- redraw fig64 once (1) has settled what it should contain.
4. **L1, L6** -- terminology sweeps, mechanical, do them in one pass.
5. **L2, L4** -- two captions and one definition. Confirm L4's reading with
   Lingxiao first.

---

## 15. Decisions taken 2026-10-24, and the facts behind them

Follows §14. These are settled, not proposals -- §14's items stay as written
except where contradicted here.

### 15.1 The architecture, stated exactly (closes L4)

Read off `u1_2d/model/score_net.py` and the deployed checkpoint's
`model_kwargs`, so the Fig. 1 caption can be rewritten without guessing.

* **`depth = 4`** -- four `FiLMResBlock`s. This is the "4 FiLM blocks".
* **`hidden = 56`** (U(1)) / **`64`** (U(2)) -- the CHANNEL COUNT, which the
  caption calls "width". The stem maps `[B, 6 + cond_channels, L, L]` ->
  `[B, hidden, L, L]`; each block is two `3x3` circular convolutions at
  `hidden -> hidden`; the head collapses `hidden -> 1`. Reproduces 324,954 and
  403,394 parameters respectively.
* **`emb_dim = 128`**, and **sigma and beta are treated SYMMETRICALLY**:
  `cat([sigma_embed(log sigma), beta_embed(log beta)])`, 64 dims each, through a
  two-layer MLP. The log is because sigma spans the noise schedule and beta
  spans the ladder, both over orders of magnitude; a sinusoidal basis on a
  linear scale wastes its resolution. **An earlier reading of this file assumed
  the two were handled differently. They are not.**
* **The coarse field enters TWICE, and this is the design point the paper never
  states.** Spatially, as input channels concatenated with the gauge-invariant
  features; and GLOBALLY, as `emb = emb + cond_film_proj(cond.mean(dim=(-2,-1)))`
  -- the spatial mean of the conditioning channels projected into the FiLM
  embedding. The global path is what carries the coarse winding density
  `2 pi Q / V`. It is ADDITIVE and ZERO-INITIALISED (`nn.init.zeros_` on weight
  and bias) so it is an exact no-op at initialisation, cannot destabilise a
  recipe that trained without it, and does not change `emb_dim` or break
  checkpoint compatibility.
* **The embedding has five consumers**: the four block modulations, plus
  `force_gate = nn.Linear(emb_dim, 1)`, also zero-initialised, which gates an
  ANALYTIC Wilson force added to the head's output:
  `h = h + gate * (-(beta * sigma) * sin(plaq))`. At `sigma -> 0` the exact
  scaled score is `sigma * curl(-beta sin theta_p)`, so the network is handed
  its own small-noise limit and learns only the envelope. **That is a physics
  prior, not an architectural detail, and it deserves a sentence in the text
  independently of the caption fix.**

So: four FiLM blocks is correct; one shared embedding; three inputs to it
(log sigma, log beta, coarse global mean); five consumers of it.

### 15.2 Statistics: z with N_eff, and no ppm as the currency (settles L5)

**Decision: z is the reporting currency. ppm survives only as a single absolute
number used to anchor the physical scale, never as a comparative statistic and
never as a ratio across couplings or volumes.**

The error, by case, and all three already exist in the codebase:

| case | estimator | why |
|---|---|---|
| **record 0** (raw seed quality -- the headline) | plain across-chain SEM, `sigma / sqrt(n_chains)` | chains are independent replicas and NO Monte Carlo time has elapsed, so there is no autocorrelation to correct for. This is the cleanest case in the paper and it needs no machinery |
| equilibrated means | `autocorr_aware_mean_err` (tau_int-aware) | already the validation of record; `out/u2_2d/validation/` holds these and the naive-SEM run is kept superseded |
| ratios, anything non-Gaussian | `chain_bootstrap` | calibrated, with an exact fast path for the mean |

**The reference contributes NO error.** The character expansion is exact at
finite volume and numerically converged -- recomputed on a 16x finer k grid, 4x
wider k cut and 4x finer alpha grid, stable to 1e-6 relative at every coupling
tested. Say this in the text: it means z is a statement about the measurement
alone, which is stronger than the usual situation where both sides carry error.

**Always print `N_eff` beside any `mean |z|`.** The 41 scored observables are
strongly correlated -- participation ratio **3.77** at L = 32, **3.25** at
L = 64, and only **1.45** on the thirteen extended loops. So `SE(mean |z|)` on
the extended-loop column is ~0.50, not 0.09, and three previously-quoted
"significant" moves were overstated by 3.3x. `validate.report.compare` already
records `n_effective` on every summary it writes.

### 15.3 Seed quality is reported at record 0, and `t_therm` is demoted to a gate

**Decision, and it is the most consequential one here.** The paper currently
lets `t_therm` carry the seed-quality claim. It should not, for reasons the
project already established internally but never applied to the manuscript:

* the band is `+-2 SEM` ACROSS CHAINS, so it narrows with more chains and with
  falling `sigma_cfg` -- it depends on volume and coupling, and the paper
  already concedes values at different rungs "are not comparable at face value",
  which is a confession that it is not a measurement;
* it is a FIRST crossing, so it can fire on a fluctuation;
* it is measured to be **rugged in coupling, reproducibly** -- ~10x scatter
  between adjacent couplings, confirmed across two independent rounds and two
  independent implementations;
* at large volume it can admit an arm whose settled mean is still many SEM from
  exact;
* and the alternative fails the other way: the Detmold-Endres-style exponential
  relaxation fit is **INVERTED for good seeds**, because a seed already at
  target has no transient to resolve, so the fit returns `inf` or is vetoed and
  the best possible seed is scored a failure.

**So neither estimator ranks seeds soundly, and the replacement is the project's
own standard** (`u2_2d/scripts/84_raw_seed_quality.py`), which the paper does
not currently use:

    Z = max over {plaquette, W(2x2), W(4x4)} of |mean - exact| / SEM,  at RECORD 0

Fit-free, so it inherits none of the failure modes above. **`t_therm` stays in
the paper as a GATE** -- did this arm reach the target band within its budget,
yes or no -- and as the denominator of a cost, but it stops being the thing that
says how good a starting configuration is.

### 15.4 The comparison is against FINITE-VOLUME exact values, and it barely matters

Lingxiao asked whether we compare against infinite- or finite-volume exact
values. Checked:

* `u2_2d/validate/observables.py:158` passes `lattice_size`, so **the validation
  of record is finite-volume**. `plaquette_exact(beta, L)` likewise.
* The difference is negligible. Infinite-volume area law against finite volume:

| beta, L | loop | infinite-V | finite-V | relative difference |
|---|---|---|---|---|
| 105.651, 32 | 4x4 | 0.73598390 | 0.73598390 | -5.6e-10 |
| 105.651, 32 | 8x8 | 0.29340888 | 0.29340889 | -1.3e-08 |
| 416.524, 64 | 4x4 | 0.92583603 | 0.92583603 | -3.0e-11 |
| 416.524, 64 | 8x8 | 0.73474446 | 0.73474446 | -5.3e-10 |

1e-12 to 1e-8 relative, at least five orders of magnitude below the measurement
precision. The reason is structural: in 2D the plaquettes are independent after
gauge fixing, so the area law is essentially exact and the finite-volume
correction enters only through the global torus constraint, which is
exponentially suppressed.

**CORRECTED 2026-10-24: this table does NOT belong in the paper.** An earlier
version of this item proposed it as a justification. There is nothing to
justify -- the simulation is at finite `L`, so the exact finite-volume value is
simply the correct reference, and defending it would imply it were a choice.
Using the infinite-volume law is what would need an argument.

**ACTIONS.** (i) State in ONE CLAUSE which reference is used ("against the exact
finite-volume values"), so a reader knows, and stop there. The table stays here,
in this file, for the internal purpose it actually serves: it is the reason the
inconsistency below never corrupted a result and no re-run is needed.
(ii) Fix the one inconsistency:
`17_prolongator_baseline.py` calls `wilson_loop_exact(beta, a * b)` with no
`lattice_size`, so it scores the plaquette against finite volume and every
Wilson loop against the infinite-volume law. Harmless at this precision but it
should not be left for someone to find.

### 15.5 The loop-decorrelation ordering is REAL -- the dilution hypothesis is refuted

**Measured 2026-10-24 and the hypothesis this section used to advance is
WRONG.** §14/L7 originally proposed leading with "the plaquette has the longest
interval and larger loops decorrelate faster"; §15.5 then retracted that as
"most likely a signal-to-noise artefact". The check says the original claim was
right and the retraction was wrong.

**The test, and why it discriminates.** `tau_int` is built from the NORMALIZED
autocorrelation `rho(t) = C(t)/C(0)`. Under the dilution hypothesis a large loop
carries extra trajectory-to-trajectory-INDEPENDENT variance, which inflates
`C(0)` and therefore scales `rho(t)` at EVERY lag by one common factor. So
rescaling each curve by its own `rho(1)` would make the curves COLLAPSE. They
do not.

Rescaled `rho(t)/rho(1)`, equilibrated tail, L = 32, beta = 105.651:

| loop | t=2 | t=3 | t=4 |
|---|---|---|---|
| plaquette | 0.708 | 0.507 | 0.376 |
| W(2x2) | 0.637 | 0.416 | 0.277 |
| W(4x4) | 0.574 | 0.352 | 0.218 |
| W(8x8) | **0.490** | **0.250** | **0.130** |

Monotone separation AFTER the level difference is removed, so the decay RATE
differs and not merely the intercept.

**Resolved and replicated.** Chain-resampling bootstrap on the
plaquette-minus-W(8x8) difference in rescaled `rho(2)`: **0.218 +- 0.020
(10.7 sigma)** at L = 32 and **0.121 +- 0.010 (12.4 sigma)** at L = 64. All four
arms at each volume -- cold_fixed, smear_fixed, diffusion_raw, diffusion_fixed
-- reproduce the curve to about +-0.01, which is an independent replication
since they are different starting configurations.

**And there is a mechanism.** In 2D a Wilson loop of area A is essentially a
product of many nearly-independent plaquettes; each refreshes under HMC
somewhat independently, so the composite decorrelates faster than any one of
them. Both effects are present -- large loops have a lower `rho(1)` AND a
faster-decaying shape -- but only the second would survive the rescaling, and it
does.

**So the ordering may be reported as a result.** The useful form pairs it with
its opposite: interval and thermalization order the scales OPPOSITELY. The
infrared decorrelates FASTER (tau_int 4.8 -> 2.3 across the loop range at
L = 32) but equilibrates SLOWER, because `t_therm` is set by the largest loop
while local repair is low-pass (u1's repair factor falls 64x to 1.6x from
W(1x1) to W(6x6)). Reporting a single interval maximized over scales hides
both halves.

**Process note, because this is the second such episode in one session.** A
plausible mechanism was proposed, written into this file as probable, and
refuted by a cheap measurement. The other was an alarm that `tab:u2_observables`
was stale, which dissolved once the right source directory
(`seed_benchmark_noretherm`, as its own caption specifies) was identified. The
rule that would have prevented both: **state the discriminating test before
stating the hypothesis, and run it first when it is cheap.** Here the test cost
two 600-trajectory runs and twenty minutes.

Note also what made the check affordable: `17_prolongator_baseline.py` now takes
`--save-series`, so a further change to any of these estimators is a reanalysis
rather than a re-run.

### 15.6 Front matter

* Shivam Panda: `shivam.panda@univ.ox.ac.uk`, Department of Physics, University
  of Oxford. **Confirm with the department before circulating** that listing the
  departmental affiliation is appropriate for this work -- see the plan for who
  to ask.
* Jinchen He: three affiliations, already filled.
* **Yong Zhao: still commented out** (`current.tex:61`). Requested 2026-10-24.
* **REVTeX `superscriptaddress` makes this all-or-nothing**: an author left
  without `\affiliation` silently inherits the NEXT author's institution, so a
  half-filled block produces a wrong paper rather than an obviously broken one.
  Fill all three in one commit and check the rendered superscripts against
  intent before circulating.

---

## 16. The cost question, and why "better seed" and "cheaper configurations" are different claims (2026-10-24)

Raised by the question "shouldn't they go hand in hand?". They do not, and the
reason is structural rather than a defect. It reframes what the paper should
claim, so it is written down here rather than left in a conversation.

### 16.1 A factory versus a per-item process

The cost of N configurations:

    classical       t_therm(cold)  +  N x interval
    preconditioned  N x (lift + repair + t_therm(preconditioned))

A classical chain pays its burn-in ONCE and then emits a configuration every
`interval` trajectories forever, so its marginal cost tends to the interval,
about 4-6 trajectories here, and the burn-in amortizes to nothing. The
preconditioner amortizes NOTHING: every configuration descends from an
independent coarse one, so each needs its own reverse diffusion, its own repair
and its own equilibration.

**Consequence, and it is the thing that makes the two claims independent: a
PERFECT preconditioner -- `t_therm` identically zero -- still loses at large N
if the lift alone costs more than one interval.** Being a better starting point
improves a term the classical route pays once. That is why the seed can be
30-130x closer to exact (SS 15, fig66) while the pipeline is 2.4x slower per
configuration (0.410 s against winding HMC's 0.212 s at L = 64, beta = 416.5).

### 16.2 Where the factory argument fails, which is the method's actual case

The amortization assumes the factory WORKS. Where the classical chain is
frozen -- above beta ~ 100 at L = 32 and beta ~ 40 at L = 64, measured in
`fig67_thermalization` -- its marginal cost is not the interval at all: it emits
correlated configurations from one topological sector forever, so it has no
product and no finite per-configuration cost. The preconditioner's per-item cost
is then the only finite number in the comparison.

So the defensible claim is the one Sec. IV E already makes: **break-even at best
where a good classical sampler exists, and the only option where one does not.**
That is not a hedge; it is what a preconditioner buys.

### 16.3 The 512-vs-1024 difference is NOT the stale-count bug -- RETRACTED

An earlier version of this section diagnosed
`out/u2_2d/sampler_steps/sampler_steps.json` (`n_configs: 512` against
`default.yaml`'s 1024) as a third instance of the stale-configuration-count bug
documented in CLAUDE.md, and predicted the per-configuration cost would halve on
a re-run. **It did not, and the diagnosis was wrong.** Re-run at 1024
(`out/u2_2d/sampler_steps_1024/`):

| sampler steps | 512 s/config | 1024 s/config | change |
|---|---|---|---|
| 18 | 0.1032 | 0.0763 | -26% |
| 25 | 0.1535 | 0.0878 | -43% |
| 50 | 0.1670 | 0.1339 | -20% |
| 100 | 0.2681 | 0.2325 | -13% |
| 200 | 0.4703 | 0.4179 | -11% |

A stale COUNT would divide the same wall-clock by half the configurations and
give a flat factor of two. This is 11-43% with a clear GRADIENT, largest where
the sampler is cheapest, which is the signature of a fixed per-pass overhead
amortizing better over more configurations. `14_sampler_steps.py` reads
`n_configs` from the config and actually lifts that many, so it was never
exposed to the bug; only `13_cost_comparison.py`'s `--rung-configs` default was.

Lesson worth keeping, since the wrong diagnosis was reached from a real
coincidence (0.470 against a recorded 0.240 is close to a factor of two):
**check the SHAPE of a discrepancy before naming its cause.** A division error
is flat; an overhead effect has a gradient.

### 16.4 The cost/accuracy trade at reduced sampler steps -- MEASURED

Against winding HMC's 0.212 s per independent configuration, at 1024
configurations:

| sampler steps | s/config (top rung) | ratio | rung-0 plaquette rel. err | rung-0 W(2x2) z |
|---|---|---|---|---|
| 18 | 0.0763 | **0.36** | +1.72e-04 | +7.4 |
| 25 | 0.0878 | **0.41** | +3.51e-04 | **+14.0** |
| 50 | 0.1339 | 0.63 | +2.02e-04 | +5.2 |
| 100 | 0.2325 | 1.10 | +1.44e-04 | +2.9 |
| 200 (deployed) | 0.4179 | 1.97 | +1.18e-04 | **+2.1** |

**The trade is real and it is not small.** At 25 steps the ladder is 2.4x
CHEAPER per configuration than winding HMC, and its raw lift is 14 standard
errors off on W(2x2) against 2.1 at 200 steps -- a factor of 6.7 -- with the
plaquette 3x worse as well. So "cheaper per configuration" and "a good lift"
are themselves in tension, on top of the factory/per-item tension of SS 16.1.

**Read rung 0, not the top rung.** The top-rung plaquette is flat across the
whole range (-9.0e-05 to +7.5e-05, no trend), which would suggest step count
costs nothing. It compounds two lifts and crosses zero near 18 steps, exactly as
CLAUDE.md warns, so it is insensitive by construction and tuning on it picks a
bad setting.

**Two things this run does NOT settle.** The z values use a naive
across-configuration SEM while the validation of record is tau_int-aware, so
the absolute numbers are inflated -- though every row gets identical treatment,
so the 14.0 -> 2.1 comparison holds. And the run applied NO rethermalization
(`rel_err_pre_retherm` equals `rel_err` in every row), so it cannot say whether
the deployed 10 sweeps close the gap. CLAUDE.md's claim that 25 steps shows "no
measurable change in local observables after retherm" predates this run and was
made on a different column; **it should be re-measured before 25 steps is
recommended.**

**The 1.38x-faster figure in CLAUDE.md is superseded**: it came from the
512-configuration run (ratio 0.72 at 25 steps). The corrected value is 2.4x.

### 16.5 What none of the three figures measures

`fig65` (improvement factor), `fig66` (accuracy at fixed budget) and `fig67`
(trajectories to equilibrate) all score the RAW lift.
`28_crossover_scan.py` calls `generate_fine_from_coarse` with
`n_su2_sweeps = 30` and NO rethermalization, while the deployed ladder applies
`n_retherm_sweeps: 10` on top.

That matters because fig67's bottleneck is specifically the PLAQUETTE -- the
preconditioned arm starts 4.5-19.4 standard errors off on it at L = 64 and
`t_therm` tracks that almost exactly (the one coupling with z = 0.6 has
`t_therm` = 0), while W(2x2) and W(4x4) are mostly 0-10 records. The plaquette
is the most ultraviolet observable and precisely what cheap local sweeps repair:
the project has measured **two retherm sweeps, six link touches, reaching
|z| <= 2 at every coupling tested**, against 920-2560 link touches for the
trajectory route.

So fig67 charges the preconditioned arm 27-47 records of HMC to remove a bias
that about two sweeps would remove for a thousandth of the cost. **The honest
statement is that the raw lift's UV bias is real and expensive to remove BY HMC,
and that nobody would remove it that way.** A `t_therm` measured on the
delivered product does not exist yet; `28_crossover_scan.py` has no
`--n-retherm`, the retherm living in `03_run_ladder.py`.

Sec. IV already warns that scoring post-retherm "cannot separate a good model
from a good repair". That is the right caution for ACCURACY. It is the wrong one
for COST, where the repair is exactly what should be counted, because it is part
of the method and it is cheap.

---

## 17. The loop-size scan (2026-10-28): UV/IR is the wrong axis, and F was floored

The coverage scan was re-run with **W(8x8) added** and at **14 couplings at both
volumes** instead of 14 and 8. W(8x8) could not be recovered from the old runs:
the scan stores observables only, no configurations along the trajectory, so the
larger loop needed new HMC. The cached lifts under `seeds/` were reused.

L = 32 is complete (`out/u2_2d/coverage_scan_w8/`); L = 64 is running.

### 17.1 Difficulty falls MONOTONICALLY with loop size, at BOTH volumes

Cold arm, fraction of couplings at which it never equilibrates within budget,
by the scan's own discrete criterion (`t_therm_threshold_old`: |z| <= 2 for
five consecutive records):

| observable | L=32 winding | L=32 plain | L=64 winding | L=64 plain* |
|---|---|---|---|---|
| plaquette | **8/14** | **8/14** | **13/14** | 9/11 |
| W(2x2) | 8/14 | 7/14 | 13/14 | 10/11 |
| W(4x4) | 5/14 | 6/14 | 10/14 | 6/11 |
| **W(8x8)** | **2/14** | **2/14** | **6/14** | 4/11 |

\* L=64 plain is 11 of 14 couplings: that wave was killed mid-run (see 17.7)
and the three missing points are the three HARDEST, so its column is
optimistic and must not be compared against the 14-coupling columns yet.

**The ordering transfers to L=64 and the margin widens.** The largest loop is
the easiest at both volumes, and the cold arm's plaquette failure rate goes
8/14 -> 13/14 from L=32 to L=64 while W(8x8) goes 2/14 -> 6/14.

**The preconditioned arm fails 0/14 on every local observable, at both volumes
and in both rounds.** That is on the unambiguous criterion -- `inf` means the
band was never reached -- and it is the cleanest single statement in the scan.

Two measured causes for the loop-size ordering, both already in this file:
large loops carry far more per-configuration spread, so the `+-2` s.e. band is
wider and easier to clear; and they decorrelate faster, which is a difference
in the DECAY RATE of `rho(t)` and not signal-to-noise dilution (10.7 sigma at
L = 32, 12.4 at L = 64, SS 15.5).

**So "ultraviolet versus infrared" is backwards for this theory.** The ordering
is plaquette hardest, large loops easiest. The honest axis is LOOP SIZE.

Note this is a statement about 2D, not about the programme: after gauge fixing
there is very little long-distance structure here for a large loop to probe,
which is the same fact that lets cold + charge + a few exact sweeps reach
equilibrium at all (SS 11.7). In 4D the label would mean something.

**APPLIED to the paper**: `sec:scoring` no longer says the loops probe
"ultraviolet (UV) and infrared structure"; `sec:u2obs` now states the measured
ordering explicitly; "no classical arm reaches both the UV and the topological
target" is now "both the local and the topological target".

### 17.2 RETRACTED: topology is NOT the only unconditional failure

**This section previously read "charge fails 14/14 at both samplers, at every
coupling, at both volumes" and called that the claim to lead with. It is
wrong, and the paper carried it for one revision.**

The number had no source. `t_therm_threshold_old` in the scan JSON runs over
`LOCAL` only -- the four Wilson loops -- and has no `charge` key at all;
`90_standard_timescales.py`'s `therm_*` fields do cover charge but its own
in-code comment marks them unusable (the one-sigma walk-back scores a
perfectly equilibrated seed at ~397 records against the scan's 0-11).

Scored on the SAME footing as the loop rows -- `28_crossover_scan.
thermalization_time` applied to `Q^2` against the exact `<Q^2>` from the closed
form, which is exactly what the loop rows do against `wilson_loop_exact`
(`artifacts/charge_therm.py`, no new HMC):

| arm | L=32 winding | L=32 plain | L=64 winding | L=64 plain* |
|---|---|---|---|---|
| cold start | **1/14** | **12/14** | **0/14** | **11/11** |
| diffusion seed | 0/14 | 4/14 | 0/14 | 2/11 |

The two rounds are different in kind, not in degree:

* **Plain HMC is totally frozen.** Above beta ~ 14 its `<Q^2>` is `0.000` to
  three decimals at every coupling and its parity-flip count is exactly zero.
  The `inf` is not a budget artefact; there is no sector motion to be slow.
* **The winding arm reaches the exact `<Q^2>` essentially everywhere**, with
  423-5698 parity flips. The single L=32 failure is beta = 1623, where the
  marginal move itself dies (0 flips) -- already on record in CLAUDE.md as the
  move's decay at the top of the range.

So the retracted sentence was true only against plain HMC, which is **not**
this project's declared baseline (CLAUDE.md: "the classical baseline of record
is HMC + winding update, not PTBC and not plain HMC"). Stating it against the
winding arm overclaimed against the strongest sampler we run.

**CAVEAT that applies to the whole charge row, in both directions.** `<Q^2>`
is a single moment, so matching it to 2 s.e. is a far weaker test than matching
`P(Q)` -- CLAUDE.md is explicit that sector-change counts and `tau_int(Q^2)`
both report HEALTHY on parity-frozen chains. The row says the winding arm's
`<Q^2>` arrives, not that its topology is correctly sampled. It is scored this
way because every loop row is also a single-mean test, so the comparison is
internally consistent; it is not a replacement for the `P(Q)` goodness-of-fit
machinery in stage 07.

The diffusion seed's own plain-round failures (4/14, 2/11) are real and not an
estimator artefact: at those couplings the transported `<Q^2>` sits off exact
(beta = 88.76: 0.719 against 1.196; beta = 537: 0.031 against 0.132) and plain
HMC cannot move it. In the winding round they vanish, 0/14 at both volumes.

**What survives, and it is sharper than what was retracted**: the division of
labour in 17.3, which holds against the strongest classical sampler rather than
against the weakest.

### 17.3 The winding move buys topology and essentially nothing else

Local-observable failure counts, winding against plain, from 17.1:

| | plaquette | W(2x2) | W(4x4) | W(8x8) |
|---|---|---|---|---|
| L=32 | 8 vs 8 | 8 vs 7 | 5 vs 6 | 2 vs 2 |

Within one coupling at every loop size. Meanwhile the charge row moves from
12/14 failures to 1/14. The winding update buys topological mobility and
essentially nothing else, which is what it was designed to do.

Worth stating, because it justifies winding HMC as the baseline without
flattering it: it is the strongest classical sampler precisely and only where
the method claims an advantage. The L=64 comparison is deferred until the plain
wave is complete -- at 11 of 14 couplings its local column is optimistic by
construction, and comparing 13/14 against 9/11 would read the missing hard
couplings as a win for plain HMC.


### 17.4 fig65's local-observable panels were floored -- CORRECTED

`91_money_split_figure.py` divided each panel's interval by THAT OBSERVABLE'S
own `t_therm`. For the larger loops that value is 0 at many couplings, gets
charged as one trajectory to keep the ratio finite, and so reports a floor as
an improvement. The denominator must be the SLOWEST observable, because a
configuration is not usable when W(4x4) has converged and the plaquette has
not. Measured at L = 64: preconditioned `t_therm` is 0 on W(4x4) at five of
eight couplings while the plaquette is 44-94 trajectories.

Corrected (median F), on the OLD grid, as first measured:

| panel | per-observable (wrong) | slowest (correct) |
|---|---|---|
| L=32 W(4x4) vs plain | 3.29 | **0.42** |
| L=64 W(4x4) vs plain | 6.14 | **0.19** |
| L=64 plaquette vs winding | 0.09 | 0.08 |
| topology vs winding | 10.1 / 6.8 | unchanged |

Local-observable F falls by a factor of 10-15. Topology is unaffected, because
the preconditioned charge is correct at `t = 0` by transport and its
denominator was never the issue.

**Final values, on the W(8x8) grid and after the SS 18 gate fix:**

| panel | vs plain | vs winding | n of 14 |
|---|---|---|---|
| L=32 plaquette | 0.29 | 0.36 | 5 |
| L=32 W(4x4) | 0.18 | 0.21 | 5 |
| L=32 topology | 25.6 | 11.4 | 2 / 13 |
| L=64 plaquette | 0.22 | 0.11 | 1 |
| L=64 W(4x4) | 0.16 | 0.09 | 1 |
| L=64 topology | **all 14 unbounded** | 6.4 | 0 / 14 |

Read the `n` column before the medians. After SS 18 the local panels carry
five points at L = 32 and ONE at L = 64, because at the other couplings the
classical arm never equilibrated and no factor can be quoted. The honest
summary of the local half is therefore not "we lose" but **"the comparison
exists at 5 of 14 and 1 of 14 couplings, and where it exists we lose"** -- the
13 of 14 classical failures ARE the result, not a gap in it.

Topology is the opposite: at L = 64 against plain HMC every one of the 14
couplings is unbounded, and against the winding move the factor is finite at
all 14 with a median of 6.4.

### 17.5 Per-observable relaxation times need their own guard

`28_crossover_scan.fit_relaxation_time` applies its tail-bias check only when
the point estimate is exactly zero. A cold start at strong coupling drops FAST
from far away to a plateau that is still wrong, which fits a sharp exponential
and returns a small NON-ZERO tau that escapes the check. Measured, L = 64,
beta = 636.85, cold, plaquette: starts 648 sigma from exact, ends 12.3 sigma
from exact with `t_therm = inf`, and the fit returns **tau = 2.24 +- 0.07
trajectories** while `_tail_is_biased` returns True and is never consulted.

The scan's stored `t_therm` is NOT affected -- it uses the joint fit across
observables, which returns `nan` for these arms. Only a per-observable re-fit
is exposed. `u2_2d/scripts/94_per_observable_tau.py` therefore applies the
guard UNCONDITIONALLY, which is strictly more conservative and cannot turn a
non-converging chain into a fast one. With it:

Re-run on the W(8x8) grid, which has 14 couplings x 4 observables = 56 cells
per volume against the old grid's 42 and 24 (`artifacts/per_obs_tau_w8.json`):

| arm | L=32 finite / never | L=64 finite / never |
|---|---|---|
| cold start | 18 / 38 | **2 / 54** |
| diffusion seed | 42 / 14 | 41 / 15 |

**CORRECTED: the cold arm's L=64 count is 2 of 56, not zero.** The earlier
"ZERO finite tau at L = 64, across all 24 observable-coupling cells" was true
of the 24-cell grid it was measured on and is false on the 56-cell one. The
spirit survives -- the cold arm essentially never resolves a relaxation time at
L = 64 -- but the absolute form does not, and it should not be quoted.

**The two exceptions are coherent rather than noise: both are W(8x8)**, at
beta = 25.29 (tau = 0, i.e. inside the band from the first record) and
beta = 1206.16 (tau = 2). W(8x8) is the observable 17.1 identifies as the
easiest at both volumes, so the one place the cold arm resolves a decay rate at
L = 64 is the one place 17.1 predicts it should. That is a cross-check between
two independent estimators, not a leak.

Note also that the seed's `inf` cells (14-15 per volume) are NOT the inverted
mode: `guarded_tau` returns `inf` when the settled half is significantly biased
from target, so a seed `inf` is a genuine failure, and `tau = 0` is the seed's
success case. They cluster where coverage runs out -- beta = 790.87 at L = 32
is `inf` on all four observables at model beta ~198, far past the ceiling.

**Why that matters for the volume question.** `tau` is a decay RATE and carries
no band dependence, where `t_therm = tau * ln(b0/band)` is a crossing and
does. So the band tightening explains why `t_therm` grows with volume -- but it
does NOT explain the L = 64 cold failures, because tau is band-free and still
infinite at 54 of 56 cells. That removes the "the criterion merely got
stricter" reading.

### 17.6 Two estimator fields that must not be consumed

Both were reached for while building 17.1-17.2 and both are wrong for the job.
Recorded here because the next person to want a per-observable thermalization
number will reach for the same two.

* **`t_therm_per_observable`** (the scan's per-observable exponential fit).
  Scored as a failure table it puts the DIFFUSION SEED at 5/14 failures on the
  plaquette against the cold arm's 1/14 -- the ranking inverted. That is the
  inverted-estimator failure mode already on record: a seed already at target
  has no transient to resolve, so the fit returns `nan` and is scored a
  failure, while a start far from target relaxes visibly and is scored a
  success. `nan` from this field is AMBIGUOUS between "never arrived" and "was
  already there", so it cannot support a failure count in either direction.
* **`therm_*` in `_standard_timescales.json`**. Its one-sigma walk-back
  requires the bias to stay inside a 1 s.e. band for the whole remaining
  window; a record falls outside by chance ~32% of the time, so over ~80
  records the last chance excursion sits near the end and a perfectly
  equilibrated chain scores roughly its own budget. The script's own comment
  says so and the fields are written anyway. They are `null` throughout the
  W(8x8) run because `nanmax` over the observables returns `inf`.

The field that IS right for a failure count is `t_therm_threshold_old`, because
`inf` from it means one thing only: the band was never reached. 17.1 and 17.2
both use it, and 17.2 extends it to charge by calling the same function.

### 17.7 Wave d was killed, not crashed -- and the resume needs a separate tag

The L=64 plain wave stopped after 11 of 14 couplings. The log ends mid-scan
with no traceback and no `COMPLETE` line, and the queue wrapper never printed
`wave d done` -- a crash leaves a traceback and a clean exit leaves the line,
so both halves died together. That is the `KILL_ON_JOB_CLOSE` signature
CLAUDE.md documents for the editor-attached shell, and the fix it prescribes is
Task Scheduler. Relaunched the three missing couplings as task `u2_w8_tail`
(`artifacts/resume_w8_d.ps1`), which gets `LimitFlags=0x0` and survives.

**The resume writes to a separate tag and out-dir on purpose.**
`28_crossover_scan.py` re-writes `{stem}.json` from its own in-memory `rows`
after every coupling, so running `--betas` against the real tag would have
truncated the 11 finished rows to 3 -- destroying the part that survived in
order to recover the part that did not. `artifacts/merge_w8_d.py` folds the
rows and renames the series files afterwards.

Also added `--base` to `90_standard_timescales.py`, whose scan directory was
hardcoded to `coverage_scan_relaxation/`, so the W(8x8) grid can be scored
without editing the file.

### 17.8 Still open

* L = 64 plain is 11/14 and its three missing couplings are the three hardest,
  so its column in 17.1 is optimistic and the L=64 sampler comparison in 17.3
  is deferred. L = 64 winding is complete at 14/14.
* A literature search found no precedent for a thermalization criterion whose
  threshold tightens with volume. What the literature does instead is fit a
  relaxation time, which is band-free by construction -- which is why 17.5
  matters and why the paper should report tau alongside `t_therm`.
* `fit_relaxation_time` itself is unchanged. Extending its guard to every fit
  outcome would be the proper fix, but it is a validated estimator with its own
  regression tests and the per-observable path is the only consumer exposed.

---

## 18. One figure's equilibration gate dropped failures -- and two did not (2026-10-28)

Found while trying to reconcile `sec:money`'s "twenty-four cases" against the
W(8x8) grid. **The first diagnosis written here was wrong and is corrected
below**; the error is instructive, so both the defect and the misdiagnosis are
recorded.

### 18.1 The defect, and why it needs TWO steps to appear

Three figures reduce a per-observable `t_therm` dict to one number before
gating on it, all with the same shape:

```python
vals = [v for v in (d or {}).values() if v is not None]
return max(vals) if vals else None
```

Taken alone this is HARMLESS, because `28_crossover_scan.py` writes
non-convergence as `Infinity`, not `null` -- verified, zero literal nulls in
1056 cells. `Infinity` survives the `is not None` filter, `max()` returns it,
and the gate `not np.isfinite(...)` catches it correctly.

It becomes a defect only when something converts the sentinel FIRST.
`91_money_split_figure._scan_tt` does exactly that:

```python
arm: {o: (None if v is None or not np.isfinite(v) else float(v) * re_)
      for o, v in d.items()}
```

`inf` becomes `None`, and `_worst` then filters it away -- so `max()` returns
**the slowest observable that converged**, not the slowest observable, and the
gate fires only when EVERY observable failed. A classical arm counts as a
supplier of independent configurations of the target at couplings where its
plaquette never equilibrated at all. At `beta = 1065.4`, `L = 32` the cold arm
never arrived on the plaquette, W(2x2) or W(4x4), and the rule credited it with
**21 trajectories** from W(8x8) alone.

This is the SAME floor error that `91`'s own comment three lines above `_worst`
was written to prevent -- "the denominator must be the slowest observable,
because a configuration is not usable when W(4x4) has converged and the
plaquette has not" -- displaced from the denominator into the gate, where the
comment did not follow it.

**fig64 (`89_money_figure.py`) and fig67 (`93_thermalization_figure.py`) read
the RAW JSON and so never had it.** fig67's 1/14 cold-arm count at `L=64`
printed correctly all along, which is what first contradicted the misdiagnosis.
fig64's `worst` was rewritten to propagate explicitly anyway; that change is a
verified NO-OP (0 disagreements in 1056 cells) kept only because the explicit
form cannot acquire the bug if a sentinel conversion is ever added upstream.

### 18.2 Scale, in fig65 only

Cold arm counted as having equilibrated, before and after:

| cell set | before | after |
|---|---|---|
| L=32 winding | 12/14 | **5/14** |
| L=32 plain | 12/14 | **5/14** |
| L=64 winding | 8/14 | **1/14** |
| L=64 plain | 8/14 | **1/14** |

The SEED is unaffected -- it has no non-finite cell at any coupling or volume --
so the correction changes which couplings are comparable, not the
preconditioned cost. fig65's local panels now carry five points at `L = 32` and
one at `L = 64` (see SS 17.4).

### 18.3 The paper's factor statistics never matched its own figure

Separate from the bug, and real. `sec:money`'s case COUNTS reproduce fig64
exactly -- eighteen measured cases over six distinct couplings -- but four
statistics in the same sentence do not. Recomputed with arithmetic verified
against the figure's own per-checkpoint medians (1.36 / 0.75 / 1.02 at `L=32`
and 1.12 / 0.61 / 0.48 at `L=64`, all reproduced to the digit by
`artifacts/f_stats.py`):

| | published | fig64's actual output |
|---|---|---|
| median F | 1.4 | **0.85** |
| range | 0.1 to 18 | **0.08 to 11.9** |
| below one | 6 of 18 | **10 of 18** |
| charged at the 1-trajectory floor | 3 of 18 | **1 of 18** |

Provenance of the published four could not be reconstructed: they match neither
the current output, nor the output without the `record_every` conversion
(which would double every F to a pooled median of 1.7), nor any single
checkpoint's column except that `1.4` is close to `default`'s `L=32` median of
1.36. They are corrected rather than explained.

The conclusion needed a word changed, not a reversal: at a median of 0.85 with
ten of eighteen below one, "break-even at best" became **"slightly below
break-even"**, still the expected result where a good classical sampler exists.

"Twenty-four cases" above `beta ~ 90` also does not reproduce -- the figure's
accounting gives 30 cells over 14 distinct couplings -- and is replaced by that,
stated in the same (checkpoint, volume, coupling) units the "eighteen" uses so
the two are checkable against each other.

### 18.4 What survived verification unchanged

Worth listing, because the rest of this section is corrections:

* **"Every case in which winding HMC equilibrates lies below `beta ~ 90`"** is
  EXACTLY true and sharp: the measured couplings are 10.9, 13.9, 24.6, 25.3,
  44.0 and 88.8, highest 88.8. At `L = 64` the boundary is far lower -- only
  `beta = 25.3`, the lowest coupling on the grid -- so `beta ~ 90` is an
  `L = 32` statement and the volume dependence is real.
* **"Two couplings below the crossover"** (`beta = 58.0` at `L=32`,
  `beta = 41.5` at `L=64`) = 6 cells across three checkpoints, correct on
  fig64's grid. On the W(8x8) grid two MORE sub-90 couplings exist at `L = 64`
  (67.5, 71.4) and both fail, so this count is grid-specific and must be
  re-read if fig64 is rebuilt on the wider grid.
* **The floor-charged case is the largest value quoted** -- `wide_dense`,
  `L=32`, `beta=44.0`, seed `t_therm = 0` charged as 1, F = 11.86, the maximum
  of the eighteen. The hedge in the text does exactly what it claims.
* `sec:money`'s plain-HMC paragraph ("finite only at `beta = 10.9` and `13.9`
  at `L=32`; at every `L=64` coupling its charge does not move") matches the
  independent charge table in SS 17.2 exactly, at 12/14 and 14/14.

### 18.5 Why fig64 was NOT rebuilt on the W(8x8) grid

fig64 spans three checkpoints for its range column and four for density; the
W(8x8) re-run covers `wide_dense` only. Rebuilding it on the new grid means
re-running the scan for `default`, `wide` and `cov60` too. So fig64 stays on
`coverage_scan_relaxation/` while fig65/66/67 are on `coverage_scan_w8/`. The
two grids disagree about how many sub-90 couplings `L = 64` has (2 against 4),
which is the one place a reader could be misled, and SS 18.4 flags it.

### 18.6 The lesson, including from the misdiagnosis

`None` in a reduction is not a missing value to be skipped; here it was the
LARGEST possible value. But the sharper lesson is that **neither half of this
bug is wrong on its own** -- normalising `inf` to `None` is reasonable, and
filtering `None` out of a reduction is reasonable -- and it only bites where one
feeds the other. Grep for a sentinel conversion UPSTREAM of a filtering
reduction, not for either pattern alone.

And on the misdiagnosis: the first version of this section asserted the bug in
all three figures, with a "94 of 176 cells" table for fig64. That number came
from a check script which replicated the `inf -> None` conversion itself before
applying the two rules, so it measured a hypothetical rather than the deployed
code. **fig67 printing the correct 1/14 is what exposed it.** A figure that
disagrees with your diagnosis is evidence about the diagnosis, not noise.

---

## 19. arXiv preparation (2026-11-05): the Overleaf merge, and what tracking caught

### 19.1 The merge direction, and why it was not the obvious one

`paper/latest.tex` came back from Overleaf 84 lines SHORTER than
`paper/current.tex`, and a line diff against the committed base showed ~3600
changed lines on each side -- almost all of it re-wrapping. Normalising the
wrapping first (`artifacts/merge/normalize.py`) cut that to 63 real changes on
the Overleaf side and 142 on ours, which is what made a merge possible at all.

**`current.tex` was the base, not `latest.tex`.** The Overleaf copy predates
this session, so merging it wholesale would have reinstated three corrections:
the UV/IR framing (measured backwards -- the cold arm fails on the plaquette at
8 of 14 couplings and on W(8x8) at 2), the improvement-factor statistics
(median 1.4 / 6 of 18 / twenty-four cases, against the figure's actual 0.85 /
10 of 18 / thirty), and the expanded architecture caption.

Ported in: `preprintnumbers`, `\preprint{FERMILAB-PUB-26-0786-T}`, Yong Zhao's
Argonne affiliation, and the finalised acknowledgments with the `\JH{}` review
wrappers removed. Zero live review macros remain, and the definitions are gone
too, so a stray `\JH{...}` can no longer typeset a reviewer note in blue.

**Both of us independently renamed lifted -> upsampled and both produced the
same artefact**, "a upsampled". Three instances were fixed by exact match and a
FOURTH was missed because the article sat at the end of a line and the noun at
the start of the next, so `\ba upsampled\b` could not see it. It was found by
re-running the search on whitespace-collapsed text. **Any post-rename grammar
sweep of a wrapped LaTeX source has to flatten the whitespace first.**

### 19.2 Registering the untracked figures immediately found two stale ones

`49_assemble_appendix_figures.py` tracked 41 figures and reported 10 untracked,
and its own doc says untracked means UNEXAMINED. Among the ten was
`fig64_money.png`, which the paper cites as `\fig{money}`. So nothing was
watching the paper's central cost figure for staleness -- and when its input
`_standard_timescales.json` was rewritten on 2026-10-24, the checker could not
say whether the figure predated it. That had to be reconstructed by hand, and
the reconstruction produced a false alarm before it produced an answer.

All ten are now tracked and placed in sections. The check went from
`41 tracked, 0 stale, 10 untracked` to `51 tracked, 2 stale, 0 untracked`, and
**the two it flagged were real**: fig60 and fig61 were older than the Oct 24
rewrite and have been regenerated. The directory is now consistent.

**Three number collisions are recorded in the manifest rather than fixed**, as
renaming output files would strand every path already quoted in notes:

* `89_money_figure.py` writes BOTH `fig64_money` and `fig65_cost`
* `91_ladder_volume_figure.py` and `91_money_split_figure.py` are both `91`
* `93_therm_bootstrap.py` and `93_thermalization_figure.py` are both `93`

So the figure number no longer identifies the script, and three different
scripts write a `fig65_*`. Every manifest entry now names its generator.

### 19.3 Which figures went into the paper, and which did not

fig66 and fig67 are IN, after the cost-accounting section, with text. They
answer the objection that section invites -- it reports thirty cases as
classical failures, and a reader may fairly ask what the advantage is there:

* **fig67** plots the two timescales directly instead of as a ratio, so a
  non-equilibrating arm reads as a triangle rather than as an absent point.
  Cold equilibrates at 5/14 (L=32) and 1/14 (L=64) under either sampler;
  the preconditioned chain at 14/14 at both, in a median of 13-18 and 38-54
  trajectories against intervals of 4.0-7.1.
* **fig66** reports an endpoint that stays defined when no ratio does -- how
  much closer to exact each arm is when its budget runs out. The advantage
  grows with volume (plaquette median 2.0 at L=32, 6.2 at L=64 against plain
  HMC) and its topology column against WINDING HMC sits at one, which is the
  same retraction as SS 17.2 arriving by a third route.

**fig65_money_split is deliberately OUT.** After the SS 18 gate fix its local
panels carry five points at L=32 and one at L=64, so most of the figure is the
absence of a comparison, and what it does show is already in fig64 and fig67.
It stays tracked as a diagnostic.

### 19.4 In flight

Twelve scans are running (`u2_regrid`, concurrency 3, ~16 h) to put
`default`, `wide` and `cov60` on the W(8x8) grid, so fig64 can be rebuilt
where figs 65-67 already live and the paper stops describing two grids. The
one cross-grid discrepancy this removes is the number of sub-beta=90 couplings
at L=64 -- 2 on the old grid against 4 on the new, with both of the extra ones
failing. `u2_after_regrid` waits on the queue and then re-scores timescales,
regenerates the bootstrap bands, rebuilds every figure and reprints the
paper's quoted counts.

`--base` was added to `89_money_figure.py` and `93_therm_bootstrap.py` so that
rebuild is a flag rather than an edit; both were verified to reproduce their
published numbers exactly on the default grid before being trusted on the new
one (fig64 medians 1.36 / 0.75 / 1.02 at L=32 and 1.12 / 0.61 / 0.48 at L=64,
unchanged).
