"""Holdout evaluation. Owner: teammate 1.   Run:  python -m scripts.evaluate [--gate-sample 1000]

Leakage rules: inference sees only test_inputs (ticket_id, subject, body); labels are joined
only for scoring; the test split's answers were never written to disk.
Writes reports/metrics.json.
"""
import argparse
import json
import time

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, f1_score

from src import config, gate, retrieval, triage
from src.data import LABELS, build_text, load_test_inputs, load_test_labels


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate-sample", type=int, default=1000, help="test tickets to run retrieval+gate on")
    args = ap.parse_args()

    inputs = load_test_inputs()
    t0 = time.perf_counter()
    preds = triage.predict_batch(inputs["subject"].tolist(), inputs["body"].tolist())
    triage_ms = (time.perf_counter() - t0) * 1000 / len(inputs)

    labels = load_test_labels().set_index("ticket_id").loc[inputs["ticket_id"]]  # scoring only
    metrics = {"n_test": len(inputs), "triage_ms_per_ticket": round(triage_ms, 2)}
    for label in LABELS:
        y_true, y_pred = labels[label].tolist(), [p[label]["label"] for p in preds]
        metrics[label] = {"macro_f1": round(f1_score(y_true, y_pred, average="macro"), 4),
                          "accuracy": round(accuracy_score(y_true, y_pred), 4)}
        print(f"\n=== {label} ===\n{classification_report(y_true, y_pred, zero_division=0)}")

    is_hpi = ((labels["priority"] == "high") & (labels["type"] == "Incident")).to_numpy()
    pred_hpi = np.array([p["priority"]["label"] == "high" and p["type"]["label"] == "Incident" for p in preds])
    metrics["high_priority_incident"] = {"support": int(is_hpi.sum()),
                                         "classifier_recall": round(float(pred_hpi[is_hpi].mean()), 4)}

    # Gate (pre-generation rules) on a sample: escalation recall on true HP incidents + overall escalation rate
    rng = np.random.default_rng(config.SEED)
    idx = rng.choice(len(inputs), size=min(args.gate_sample, len(inputs)), replace=False)
    escalated, r1, r3, top1, lat = [], [], [], [], []
    for i in idx:
        text = build_text(inputs["subject"].iloc[i], inputs["body"].iloc[i])
        t = time.perf_counter()
        hits = retrieval.search(text)
        pre = gate.pre_check(text, preds[i], hits)
        lat.append((time.perf_counter() - t) * 1000)
        escalated.append(bool(pre["rules"]))
        r1.append("R1" in pre["rules"])
        r3.append("R3" in pre["rules"])
        top1.append(hits[0]["score"] if hits else 0.0)
    escalated, r1, r3 = np.array(escalated), np.array(r1), np.array(r3)
    hp = is_hpi[idx]
    metrics["gate_sample"] = {
        "n": len(idx), "retrieval_backend": retrieval.active_backend(), "tau_sim": config.TAU_SIM,
        "escalation_rate": round(float(escalated.mean()), 4),
        "r1_severity_rate": round(float(r1.mean()), 4),
        "r3_no_precedent_rate": round(float(r3.mean()), 4),
        "hp_incident_escalation_precision": round(float(hp[escalated].mean()), 4) if escalated.any() else None,
        "top1_similarity_p5_p50": [round(float(np.percentile(top1, q)), 3) for q in (5, 50)],
        "hp_incident_escalation_recall": round(float(escalated[is_hpi[idx]].mean()), 4) if is_hpi[idx].any() else None,
        "retrieval_gate_ms_p50": round(float(np.percentile(lat, 50)), 1),
        "retrieval_gate_ms_p95": round(float(np.percentile(lat, 95)), 1),
    }

    config.REPORTS.mkdir(exist_ok=True)
    (config.REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
