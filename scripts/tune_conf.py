"""Tune TAU_CONF on the val split: R2 fires if type OR priority confidence < tau.
For each tau: share of tickets R2 escalates, and triage accuracy (type AND priority both right)
inside vs outside the escalated group. Run: python -m scripts.tune_conf"""
import numpy as np

from src import triage
from src.data import load_kb

val = load_kb("val")
preds = triage.predict_batch(val["subject"].tolist(), val["body"].tolist())
tc = np.array([p["type"]["confidence"] for p in preds])
pc = np.array([p["priority"]["confidence"] for p in preds])
ok = np.array([p["type"]["label"] == t and p["priority"]["label"] == q
               for p, t, q in zip(preds, val["type"], val["priority"])])
hp = ((val["type"] == "Incident") & (val["priority"] == "high")).to_numpy()
hp_pred = np.array([p["type"]["label"] == "Incident" and p["priority"]["label"] == "high" for p in preds])

print(f"val={len(val)}  overall type+priority accuracy={ok.mean():.3f}")
print(f"high-priority Incident recall (classifier alone)={hp_pred[hp].mean():.3f}  n={hp.sum()}")
print(f"{'tau':>5} {'R2 rate':>8} {'acc kept':>9} {'acc flagged':>12} {'HP-Inc caught (pred or R2)':>27}")
for tau in (0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7):
    flag = (tc < tau) | (pc < tau)
    caught = (hp_pred | flag)[hp].mean()
    print(f"{tau:>5} {flag.mean():>8.1%} {ok[~flag].mean():>9.3f} {ok[flag].mean() if flag.any() else float('nan'):>12.3f} {caught:>27.3f}")
