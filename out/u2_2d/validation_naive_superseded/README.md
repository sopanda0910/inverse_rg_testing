# SUPERSEDED -- naive-SEM validation

Kept as the record of what was replaced on 2026-08-22. The validation of record
is `../validation/`, which uses tau_int-aware error bars.

Every `z` in here is built on `sigma / sqrt(N)`, which assumes independent
configurations. A ladder ensemble comes from a fixed number of HMC chains, so
that SEM is too small and these `|z|` are too large by roughly 7-8%
(`mean |z|` 0.522 against the corrected 0.484 at L = 32; 0.789 against 0.728 at
L = 64). Do not quote these numbers.
