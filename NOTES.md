Here are the key things that make this different
from the other current diffusion model papers: 1.
You falsified the MALA exactness claim, and it’s
your sharpest single result. §25.6(c): running MALA
on the exact Boltzmann target from model output,
across 50 steps × 64 configurations × 8 settings,
〈Q²〉 was bit-identical before and after — zero sector
changes, in every setting. Acceptance ratio ≈ 1.0 the
whole way, which is exactly the trap: MALA looks
like it certifies the sampler while being structurally
incapable of touching topology.
And by the mechanism from the last exchange,
that isn’t an empirical accident — it’s forced.
MALA’s proposal is a small continuous displace-
ment. Changing Q requires crossing a plaquette
through π. Any step size large enough to reach that
surface has acceptance ≈ 0;
any step size that accepts cannot reach it. MALA
is exact with respect to the local measure and
vacuous with respect to the sector. That statement
generalizes to the whole MALA-adjusted diffusion
class.
You scored the thing against the exact answer;
they scored it against a frozen chain. Their success
criterion is a wider Q distribution than HMC. Both
of their arms reject overwhelmingly, in opposite
directions, with the correct answer sitting between
them. ”Width is not correctness” is a methodological
contribution independent of any architecture. Keep
the caveat that this is digitized from a workshop
version they flagged as in-progress — in the body,
not a footnote.

Transport vs. generation, and the reason it’s
credible is that your model fails the same way theirs
does. Your raw model over-produces charge by
2.5–5.4× at strong coupling — the same failure
mode. So the claim is not ”our network is better.”
It is: score-based samplers on this theory systemati-
cally over-produce topological charge, and imposing
Q through the ladder identity is the fix. That’s a
far stronger paper than a benchmark win, and it’s
honest.
The observable/density dissociation. Plaquette
agreement to 2 parts in 104 while the KL is 450–2100
nats/configuration. No diffusion-LGT paper has
this, and it’s what licenses the whole reporting
protocol.
Different ancestor. They are a direct generative
sampler. You are Endres et al. multiscale thermal-
ization with a learned prolongator and an exact trans-
port identity replacing their measured Q-correlation
≥ 0.8. Different lineage, different claim, and it makes
the priority question against Zhu mostly moo