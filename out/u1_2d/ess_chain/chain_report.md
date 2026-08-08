# ESS chain report

Knobs used from sweep point `cw2`: `--consistency-weight 2`

| variant | case | ESS/N (fiber) | log-w std (fiber) | i-MH acc |
|---------|------|---------------|-------------------|----------|
| baseline (pre-chain knobs) | 16:14.1464 | 0.0158 | 17.50 | 0.02 |
| baseline (pre-chain knobs) | 16:55.0237 | 0.0163 | 41.98 | 0.05 |
| baseline (pre-chain knobs) | 32:55.0237 | 0.0156 | 63.16 | 0.11 |
| baseline (pre-chain knobs) | 32:218.58 | 0.0156 | 161.06 | 0.06 |
| sweep-best knobs [cw2] | 16:55.0237 | 0.0361 | 37.37 | 0.03 |
| mlft (Tier 2) | 16:14.1464 | 0.0197 | 29.27 | 0.10 |
| mlft (Tier 2) | 16:55.0237 | 0.0346 | 87.92 | 0.10 |
| mlft (Tier 2) | 32:55.0237 | 0.0156 | 251.43 | 0.13 |
| mlft (Tier 2) | 32:218.58 | 0.0156 | 941.95 | 0.06 |
| rklft (Tier 3) | 16:14.1464 | 0.0156 | 18.29 | 0.08 |
| rklft (Tier 3) | 16:55.0237 | 0.0365 | 21.09 | 0.13 |
| rklft (Tier 3) | 32:55.0237 | 0.0156 | 62.99 | 0.03 |
| rklft (Tier 3) | 32:218.58 | 0.0156 | 554.98 | 0.06 |

baseline row = original run with pre-sweep default knobs; sweep-best
row isolates the knob-only gain (same checkpoint); mlft adds Tier-2
ML fine-tuning; rklft adds Tier-3 reverse-KL on top of mlft.
Success metric: log-w std (fiber) down, ESS/N and i-MH acceptance up.