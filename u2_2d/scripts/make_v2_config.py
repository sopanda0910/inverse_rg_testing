"""Generate the challenger config: same physics, separate output paths.

The incumbent `det_score_net.pt` and every directory of record it produced stay
untouched, so the retrain is a CHALLENGER that has to earn its place against the
four pre-declared criteria rather than a destructive overwrite. The 2026-08-20
coverage retrain is why this is worth the disk: it improved L=64 extended loops
and regressed L=32, the density gap and seed quality, and it was only possible to
see that because the incumbent was still there to compare against.
"""
import pathlib, re

src = pathlib.Path("u2_2d/configs/default.yaml")
s = src.read_text(encoding="utf-8")

subs = [
    ("  out_dir: out/u2_2d/data\n", "  out_dir: out/u2_2d/data_v2\n"),
    ("  checkpoint_path: out/u2_2d/checkpoints/det_score_net.pt\n",
     "  checkpoint_path: out/u2_2d/checkpoints/det_score_net_v2.pt\n"),
    ("  out_dir: out/u2_2d/ladder\n", "  out_dir: out/u2_2d/ladder_v2\n"),
    ("  out_dir: out/u2_2d/validation\n", "  out_dir: out/u2_2d/validation_v2\n"),
]
for old, new in subs:
    assert old in s, f"anchor missing: {old!r}"
    s = s.replace(old, new, 1)

header = """# CHALLENGER CONFIG -- generated from default.yaml, 2026-08-20.
# Identical physics; only the output paths differ, so the incumbent
# det_score_net.pt and its directories of record survive for comparison.
# Regenerate with scripts/make_v2_config.py after editing default.yaml.
"""
pathlib.Path("u2_2d/configs/v2.yaml").write_text(header + s, encoding="utf-8")
print("wrote u2_2d/configs/v2.yaml")
for _, new in subs:
    print("   ", new.strip())
