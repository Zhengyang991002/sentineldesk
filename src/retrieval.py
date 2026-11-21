"""Precedent retrieval over the KB (fit part). Owner: teammate 2.

CONTRACT:
    search(text, k=TOP_K) -> [
        {"ticket_id": "TKT-01234", "score": 0.83, "language": "en", "subject": str,
         "answer": str, "type": str, "queue": str, "priority": str},
        ...  # sorted by score desc; score = cosine similarity in [0, 1]-ish
    ]

TODO(teammate 2):
  - build(): embed load_kb("fit") with fastembed
    TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"), L2-normalise,
    save embeddings .npy + faiss.IndexFlatIP to ARTIFACTS. Truncate text (~512 chars) to save time.
    Run with:  python -m src.retrieval   (slow on weak CPUs: run on the fastest laptop, share artifacts/)
  - Replace the TF-IDF STUB below with the FAISS index; keep TF-IDF as a fallback if artifacts are missing.
  - Demo cross-lingual: a German query should retrieve English precedents.
"""
from src import config
from src.data import build_text, load_kb

_tfidf = None


def _tfidf_index():
    """STUB/fallback: word TF-IDF cosine over the fit KB. Works with no embeddings."""
    global _tfidf
    if _tfidf is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        kb = load_kb("fit")
        texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
        vec = TfidfVectorizer(sublinear_tf=True, min_df=2, max_features=200_000, ngram_range=(1, 2))
        _tfidf = (vec, vec.fit_transform(texts), kb)
    return _tfidf


def _s(value) -> str:
    return "" if value is None or (isinstance(value, float) and value != value) else str(value)


def _hit(kb, i, score) -> dict:
    row = kb.iloc[i]
    return {"ticket_id": row["ticket_id"], "score": float(score), "language": row["language"],
            "subject": _s(row["subject"]), "answer": _s(row["answer"]),
            "type": row["type"], "queue": row["queue"], "priority": row["priority"]}


def search(text: str, k: int = config.TOP_K) -> list[dict]:
    vec, matrix, kb = _tfidf_index()
    scores = (matrix @ vec.transform([text]).T).toarray().ravel()
    top = scores.argsort()[::-1][:k]
    return [_hit(kb, i, scores[i]) for i in top]


def build() -> None:
    raise NotImplementedError("teammate 2: implement embedding + FAISS build here")


if __name__ == "__main__":
    build()
