"""Multi-task triage classifier. Owner: teammate 1.

CONTRACT (do not change the return shape; pipeline/gate/UI depend on it):
    predict(subject, body) -> {
        "type":     {"label": "Incident", "confidence": 0.81, "probs": {"Incident": 0.81, ...}},
        "queue":    {"label": ..., "confidence": ..., "probs": {...}},
        "priority": {"label": ..., "confidence": ..., "probs": {...}},
    }
    predict_batch(subjects, bodies) -> list of the same dicts (used by evaluate.py).

TODO(teammate 1):
  - train(): TF-IDF (word 1-2gram + char 3-5gram) + LogisticRegression(class_weight="balanced"),
    one model per label, fit on load_kb("fit") ONLY; print val Macro-F1; joblib.dump to ARTIFACTS.
  - Replace the STUB below with the loaded models. Run training with:  python -m src.triage
"""
from src import config
from src.data import LABELS, build_text, load_kb

MODEL_PATH = config.ARTIFACTS / "triage.joblib"
_models = None


def _load():
    global _models
    if _models is None and MODEL_PATH.exists():
        import joblib
        _models = joblib.load(MODEL_PATH)
    return _models


def predict_batch(subjects, bodies) -> list[dict]:
    texts = [build_text(s, b) for s, b in zip(subjects, bodies)]
    models = _load()
    if models is None:  # STUB until the trained model exists
        stub = {"type": "Incident", "queue": "Technical Support", "priority": "medium"}
        return [{k: {"label": v, "confidence": 0.0, "probs": {v: 0.0}} for k, v in stub.items()} for _ in texts]
    out = [dict() for _ in texts]
    for label in LABELS:
        clf = models[label]
        probs = clf.predict_proba(texts)
        for row, p in zip(out, probs):
            best = int(p.argmax())
            row[label] = {"label": str(clf.classes_[best]), "confidence": float(p[best]),
                          "probs": {str(c): float(x) for c, x in zip(clf.classes_, p)}}
    return out


def predict(subject, body) -> dict:
    return predict_batch([subject], [body])[0]


def train() -> None:
    kb_fit, kb_val = load_kb("fit"), load_kb("val")
    raise NotImplementedError("teammate 1: implement training here")


if __name__ == "__main__":
    train()
