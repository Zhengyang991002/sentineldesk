"""Multi-task triage classifier. Owner: teammate 1.

CONTRACT (do not change the return shape; pipeline/gate/UI depend on it):
    predict(subject, body) -> {
        "type":     {"label": "Incident", "confidence": 0.81, "probs": {"Incident": 0.81, ...}},
        "queue":    {"label": ..., "confidence": ..., "probs": {...}},
        "priority": {"label": ..., "confidence": ..., "probs": {...}},
    }
    predict_batch(subjects, bodies) -> list of the same dicts (used by evaluate.py).

Baseline: shared TF-IDF (word 1-2gram + char_wb 3-5gram) + LogisticRegression(class_weight="balanced"),
one model per label, fit on load_kb("fit") ONLY. C is picked per label by val Macro-F1 from C_GRID.
Train with:  python -m src.triage   (writes ARTIFACTS/triage.joblib and REPORTS/triage_val.md)
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
