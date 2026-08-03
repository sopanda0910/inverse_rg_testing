# ESS chain report

Knobs used from sweep point `sigmin0.03`: `--sigma-min-coef 0.03`

| variant | case | ESS/N (fiber) | log-w std (fiber) | i-MH acc |
|---------|------|---------------|-------------------|----------|
| baseline (pre-chain knobs) | 16:14.1464 | 0.0230 | 17.90 | 0.08 |
| baseline (pre-chain knobs) | 16:55.0237 | 0.0203 | 42.10 | 0.08 |
| baseline (pre-chain knobs) | 32:55.0237 | 0.0185 | 84.33 | 0.08 |
| baseline (pre-chain knobs) | 32:218.58 | 0.0156 | 163.73 | 0.06 |
| sweep-best knobs [sigmin0.03] | 16:55.0237 | 0.0309 | 23.99 | 0.14 |
| mlft (Tier 2) | 16:14.1464 | 0.0156 | 29.02 | 0.03 |
| mlft (Tier 2) | 16:55.0237 | 0.0156 | 41.33 | 0.08 |
| mlft (Tier 2) | 32:55.0237 | 0.0156 | 131.75 | 0.03 |
| mlft (Tier 2) | 32:218.58 | 0.0156 | 293.62 | 0.08 |
| rklft (Tier 3) | 16:14.1464 | 0.0156 | 23.89 | 0.11 |
| rklft (Tier 3) | 16:55.0237 | 0.0157 | 24.07 | 0.06 |
| rklft (Tier 3) | 32:55.0237 | 0.0156 | 75.05 | 0.03 |
| rklft (Tier 3) | 32:218.58 | 0.0156 | 2202.04 | 0.05 |

baseline row = original run with pre-sweep default knobs; sweep-best
row isolates the knob-only gain (same checkpoint); mlft adds Tier-2
ML fine-tuning; rklft adds Tier-3 reverse-KL on top of mlft.
Success metric: log-w std (fiber) down, ESS/N and i-MH acceptance up.