"""Evaluate the active triage model (artifacts/sentinel_model) per language: EN vs DE.

Uses ONLY the model's own validation split (never test):
  - Recreates the split exactly as sentinel_classifier.train(): over the 80% KB,
    RandomState(42).rand(n) < 0.10 -> val. (NB: this is NOT the `split` column of data/kb.parquet.)
  - The saved model indexes train+val for kNN, so for evaluation the kNN index is rebuilt with the
    train part only; otherwise each val ticket would retrieve itself (similarity 1.0).
  - Caveat: ensemble weights, temperatures and gate thresholds were tuned on this same val split,
    so absolute numbers are slightly optimistic. The EN vs DE comparison is still fair.

Run:  python -m scripts.eval_by_language      Writes reports/eval_by_language.md
"""
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score

from src import config
from src.lang import detect
from src.sentinel_classifier import TARGETS, TriageModel, apply_temperature

SENTINEL_DIR = config.ARTIFACTS / "sentinel_model"


def main() -> None:
    full = TriageModel.load(str(SENTINEL_DIR))
    kb = full.kb
    is_val = np.random.RandomState(42).rand(len(kb)) < 0.10  # same draw as train()
    tr, va = kb[~is_val].reset_index(drop=True), kb[is_val].reset_index(drop=True)
    kb_emb = full.kb_vecs.get("emb")
    m = TriageModel(full.s, tr, kb_emb[~is_val] if kb_emb is not None else None)  # kNN index = train only
    print(f"train={len(tr)} val={len(va)}  kNN sources={m.sources}  "
          f"val by language: {va['language'].value_counts().to_dict()}")

    texts = va["text"].tolist()
    comp, knn = m.components(texts)
    probs = {t: apply_temperature(m._blend(comp, t), m.s["temps"][t]) for t in TARGETS}
    sims = knn[m.primary][1]
    gate = m.s["gate"]

    pred = {t: np.array(m.classes[t])[probs[t].argmax(1)] for t in TARGETS}
    conf = {t: probs[t].max(1) for t in TARGETS}
    top1 = sims[:, 0]
    inc, high = m.classes["type"].index("Incident"), m.classes["priority"].index("high")
    hpi_score = probs["type"][:, inc] * probs["priority"][:, high]
    lang_pred = np.array([detect(t) for t in texts])

    lines = ["# Triage model by language (model's validation split, kNN index = train only)\n",
             f"train={len(tr)}, val={len(va)}. Thresholds: TAU_CONF={config.TAU_CONF}, "
             f"queue conf gate={gate['CONF_THRESHOLD_QUEUE']:.2f}, SIM_THRESHOLD={gate['SIM_THRESHOLD']:.2f}, "
             f"HPI={gate['HPI_THRESHOLD']:.2f}\n"]

    rows = []
    for lang in ["en", "de", "all"]:
        mask = np.ones(len(va), bool) if lang == "all" else (va["language"] == lang).to_numpy()
        r = {"lang": lang, "n": int(mask.sum())}
        for t in TARGETS:
            y = va[t].to_numpy()[mask]
            r[f"{t}_acc"] = accuracy_score(y, pred[t][mask])
            r[f"{t}_f1"] = f1_score(y, pred[t][mask], average="macro")
            for name, p in comp.items():  # each ensemble component on its own
                r[f"{t}_{name}_acc"] = accuracy_score(y, np.array(m.classes[t])[p[t][mask].argmax(1)])
            r[f"{t}_conf"] = conf[t][mask].mean()
        # src/gate.py R2: type or priority below TAU_CONF
        r["R2_low_conf_rate"] = ((conf["type"][mask] < config.TAU_CONF) | (conf["priority"][mask] < config.TAU_CONF)).mean()
        r["R3_low_sim_rate(TAU_SIM)"] = (top1[mask] < config.TAU_SIM).mean()
        r["top1_sim_median"] = np.median(top1[mask])
        y_hpi = ((va["type"] == "Incident") & (va["priority"] == "high")).to_numpy()[mask]
        r["hpi_recall"] = recall_score(y_hpi, hpi_score[mask] >= gate["HPI_THRESHOLD"]) if y_hpi.any() else np.nan
        r["lang_detect_acc"] = (lang_pred[mask] == va["language"].to_numpy()[mask]).mean()
        rows.append(r)
    df = pd.DataFrame(rows).set_index("lang").T
    lines += ["## Overview\n", df.round(3).to_string(), ""]

    # Per-queue accuracy by language (where is DE weaker?)
    q = va.assign(ok=(pred["queue"] == va["queue"].to_numpy()), conf=conf["queue"])
    per_q = q.groupby(["queue", "language"]).agg(n=("ok", "size"), acc=("ok", "mean"), conf=("conf", "mean")).unstack()
    lines += ["## Queue accuracy by queue x language\n", per_q.round(3).to_string(), ""]

    # Type accuracy per class by language
    tt = va.assign(ok=(pred["type"] == va["type"].to_numpy()), conf=conf["type"])
    per_t = tt.groupby(["type", "language"]).agg(n=("ok", "size"), acc=("ok", "mean"), conf=("conf", "mean")).unstack()
    lines += ["## Type accuracy by class x language\n", per_t.round(3).to_string(), ""]

    # Billing tickets specifically (the reported case)
    b = (va["queue"] == "Billing and Payments").to_numpy()
    rows = []
    for lang in ["en", "de"]:
        mk = b & (va["language"] == lang).to_numpy()
        rows.append({"lang": lang, "n": int(mk.sum()),
                     "type_acc": (pred["type"][mk] == va["type"].to_numpy()[mk]).mean(),
                     "type_conf": conf["type"][mk].mean(),
                     "queue_acc": (pred["queue"][mk] == "Billing and Payments").mean(),
                     "R2_rate": ((conf["type"][mk] < config.TAU_CONF) | (conf["priority"][mk] < config.TAU_CONF)).mean(),
                     "top1_sim_median": np.median(top1[mk])})
    lines += ["## Billing and Payments tickets\n", pd.DataFrame(rows).set_index("lang").round(3).to_string(), ""]

    # The dataset's `language` label is noisy: ~25-30% of "de" tickets are written in English.
    # Group by (label, language actually detected in the text) to see the real German gap.
    d = pd.DataFrame({"label": va["language"], "detected": lang_pred, "top1": top1,
                      "R2": (conf["type"] < config.TAU_CONF) | (conf["priority"] < config.TAU_CONF),
                      **{f"{t}_acc": pred[t] == va[t].to_numpy() for t in TARGETS}})
    agg = dict(n=("R2", "size"), type_acc=("type_acc", "mean"), queue_acc=("queue_acc", "mean"),
               priority_acc=("priority_acc", "mean"), R2_rate=("R2", "mean"), top1_sim_median=("top1", "median"))
    lines += ["## By dataset label x detected language\n", d.groupby(["label", "detected"]).agg(**agg).round(3).to_string(), "",
              "## By detected language (what the text really is)\n", d.groupby("detected").agg(**agg).round(3).to_string(), ""]

    out = config.REPORTS / "eval_by_language.md"
    config.REPORTS.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
