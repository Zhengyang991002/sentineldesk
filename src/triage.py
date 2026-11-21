"""Multi-task triage classifier. Owner: teammate 1.

CONTRACT (do not change the return shape; pipeline/gate/UI depend on it):
    predict(subject, body) -> {
        "type":     {"label": "Incident", "confidence": 0.81, "probs": {"Incident": 0.81, ...}},
        "queue":    {"label": ..., "confidence": ..., "probs": {...}},
        "priority": {"label": ..., "confidence": ..., "probs": {...}},
    }
    predict_batch(subjects, bodies) -> list of the same dicts (used by evaluate.py).

Active model: SentinelDesk ensemble (src/sentinel_classifier.py) = TF-IDF + LogisticRegression blended
with kNN votes over the KB (char n-gram TF-IDF + multilingual embeddings, so German tickets can match
English precedents), temperature-calibrated. Loaded from ARTIFACTS/sentinel_model/
(model.joblib + kb.parquet + kb_emb.npy; the kNN index is KB-only, never test). Needs scikit-learn==1.9.1.

Fallback: if that folder is missing or fails to load, the baseline below is used:
shared TF-IDF (word 1-2gram + char_wb 3-5gram) + LogisticRegression(class_weight="balanced"),
one model per label, fit on load_kb("fit") ONLY. C is picked per label by val Macro-F1 from C_GRID.
Train with:  python -m src.triage   (writes ARTIFACTS/triage.joblib and REPORTS/triage_val.md)
"""
import logging

from src import config
from src.data import LABELS, build_text, load_kb

log = logging.getLogger(__name__)

SENTINEL_DIR = config.ARTIFACTS / "sentinel_model"
MODEL_PATH = config.ARTIFACTS / "triage.joblib"
_sentinel = None
_sentinel_failed = False
_models = None


def _load_sentinel():
    global _sentinel, _sentinel_failed
    if _sentinel is None and not _sentinel_failed and (SENTINEL_DIR / "model.joblib").exists():
        try:
            from src.sentinel_classifier import TriageModel
            _sentinel = TriageModel.load(str(SENTINEL_DIR))
        except Exception:  # e.g. scikit-learn version mismatch: fall back to the baseline
            log.exception("Could not load %s; falling back to %s", SENTINEL_DIR, MODEL_PATH)
            _sentinel_failed = True
    return _sentinel


def active_model() -> str:
    if _load_sentinel() is not None:
        return "sentinel"
    return "baseline" if _load() is not None else "stub"


def hpi_threshold() -> float | None:
    """Threshold for P(Incident) * P(high), tuned on val for >=0.90 recall. None if the
    calibrated model is not active (baseline probabilities are not calibrated for it)."""
    model = _load_sentinel()
    return float(model.s["gate"]["HPI_THRESHOLD"]) if model is not None else None


def hpi_score(pred: dict) -> float:
    """High-priority-incident score from a predict() result: P(type=Incident) * P(priority=high)."""
    return pred["type"]["probs"].get("Incident", 0.0) * pred["priority"]["probs"].get("high", 0.0)


def _predict_sentinel(model, subjects, bodies) -> list[dict]:
    from src.sentinel_classifier import build_text as sentinel_text  # same text building as training
    texts = [sentinel_text(s, b) for s, b in zip(subjects, bodies)]
    out = [dict() for _ in texts]
    idx = [i for i, t in enumerate(texts) if t]
    if idx:
        probs, _, _ = model.predict_proba([texts[i] for i in idx])
    for label in LABELS:
        classes = model.classes[label]
        for j, i in enumerate(idx):
            p = probs[label][j]
            best = int(p.argmax())
            out[i][label] = {"label": classes[best], "confidence": float(p[best]),
                             "probs": {c: float(x) for c, x in zip(classes, p)}}
        for i in set(range(len(texts))) - set(idx):  # empty ticket: uniform, zero confidence
            out[i][label] = {"label": classes[0], "confidence": 0.0, "probs": {c: 0.0 for c in classes}}
    return out


def _load():
    global _models
    if _models is None and MODEL_PATH.exists():
        import joblib
        _models = joblib.load(MODEL_PATH)
    return _models


def predict_batch(subjects, bodies) -> list[dict]:
    sentinel = _load_sentinel()
    if sentinel is not None:
        return _predict_sentinel(sentinel, list(subjects), list(bodies))
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


C_GRID = [2.0, 8.0, 32.0]


def _vectorizer():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=200_000)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True,
                                 max_features=300_000)),
    ])


def train() -> None:
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, classification_report, f1_score
    from sklearn.pipeline import Pipeline

    kb_fit, kb_val = load_kb("fit"), load_kb("val")
    x_fit = [build_text(s, b) for s, b in zip(kb_fit["subject"], kb_fit["body"])]
    x_val = [build_text(s, b) for s, b in zip(kb_val["subject"], kb_val["body"])]
    vec = _vectorizer().fit(x_fit)
    X_fit, X_val = vec.transform(x_fit), vec.transform(x_val)
    print(f"fit={len(x_fit)} val={len(x_val)} features={X_fit.shape[1]}")

    models, report = {}, ["# Triage baseline: validation (KB val part)\n"]
    for label in LABELS:
        best = None
        for c in C_GRID:
            clf = LogisticRegression(C=c, max_iter=3000, class_weight="balanced").fit(X_fit, kb_fit[label])
            pred = clf.predict(X_val)
            f1 = f1_score(kb_val[label], pred, average="macro")
            print(f"{label:9s} C={c:<5} val macro_f1={f1:.4f} acc={accuracy_score(kb_val[label], pred):.4f}")
            if best is None or f1 > best[0]:
                best = (f1, c, clf, pred)
        f1, c, clf, pred = best
        models[label] = Pipeline([("tfidf", vec), ("clf", clf)])
        report += [f"## {label}: C={c}, macro_f1={f1:.4f}, acc={accuracy_score(kb_val[label], pred):.4f}\n",
                   "```", classification_report(kb_val[label], pred, digits=3, zero_division=0), "```\n"]

    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    config.REPORTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, MODEL_PATH, compress=3)
    (config.REPORTS / "triage_val.md").write_text("\n".join(report), encoding="utf-8")
    print(f"saved {MODEL_PATH} and {config.REPORTS / 'triage_val.md'}")


if __name__ == "__main__":
    train()
