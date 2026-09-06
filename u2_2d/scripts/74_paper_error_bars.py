import json, math, sys
import numpy as np
from scipy import stats
sys.path.insert(0, ".")
from u2_2d.model.det_lift import model_beta
import yaml

# ---- (a) bootstrap CI on the gap-to-rung Spearman correlation ----
def rungs_for(cfg_path):
    d = yaml.safe_load(open(cfg_path))
    mbs = [model_beta(r["beta"]) for r in d["data"]["rungs"]]
    for b in d["data"].get("random_rungs", []):
        bs = np.exp(np.linspace(math.log(b["beta_min"]), math.log(b["beta_max"]), b["n"]))
        mbs += [model_beta(float(x)) for x in bs]
    return sorted(mbs)

CFG = {"default":"u2_2d/configs/default.yaml","cov60":"u2_2d/configs/cov60.yaml",
       "wide":"u2_2d/configs/wide.yaml","wide_dense":"u2_2d/configs/wide_dense.yaml"}
rung_sets = {t: rungs_for(p) for t,p in CFG.items()}
rows = json.load(open("out/u2_2d/_gap_rows_scratch.json"))
CAP = 1e6
g, t = [], []
for r in rows:
    if r["t_therm"] is None: continue
    lg = min(abs(math.log(r["model_beta"]) - math.log(rr)) for rr in rung_sets[r["tag"]])
    if lg <= 0.05: continue
    tt = r["t_therm"]
    tt = CAP if (isinstance(tt,float) and math.isinf(tt)) else tt
    g.append(lg); t.append(tt)
g, t = np.array(g), np.array(t)
rho, p = stats.spearmanr(g, t)
rng = np.random.default_rng(0)
boots = []
for _ in range(5000):
    idx = rng.integers(0, len(g), len(g))
    if len(np.unique(g[idx])) < 3: continue
    boots.append(stats.spearmanr(g[idx], t[idx]).statistic)
boots = np.array([b for b in boots if np.isfinite(b)])
lo, hi = np.percentile(boots, [2.5, 97.5])
print(f"gap-to-rung Spearman: rho = {rho:.3f}  p = {p:.2e}  n = {len(g)}")
print(f"  bootstrap 95% CI: [{lo:.3f}, {hi:.3f}]   (5000 resamples)")

# ---- (b) Wilson binomial CIs on the BAD-FIT rates ----
def wilson(k, n, z=1.96):
    ph = k/n; d = 1 + z*z/n
    c = (ph + z*z/(2*n))/d
    h = z*math.sqrt(ph*(1-ph)/n + z*z/(4*n*n))/d
    return c-h, c+h

print("\nBAD-FIT rates, Wilson 95% CI:")
for label, k, n in [("u2 cold start", 158, 176), ("u2 seed", 0, 176),
                    ("u1 cold start", 98, 176), ("u1 hot start", 121, 176),
                    ("u1 seed", 12, 176)]:
    lo, hi = wilson(k, n)
    print(f"  {label:<16s} {k:3d}/{n}  = {100*k/n:5.1f}%   CI [{100*lo:4.1f}%, {100*hi:4.1f}%]")
