"""Precedent retrieval over the KB (fit part). Owner: RAG.

CONTRACT:
    search(text, k=TOP_K) -> [
        {"ticket_id": "TKT-01234", "score": 0.83, "language": "en", "subject": str,
         "answer": str, "type": str, "queue": str, "priority": str},
        ...  # sorted by score desc; score = cosine similarity
    ]

Build the embedding index:
    python -m src.retrieval --chunks 2   # quick dev index (2,048 tickets, ~5 min on the Intel Mac)
    python -m src.retrieval              # full KB (~50 min on the Intel Mac); resumes finished chunks
"""
import argparse
import math
import time

import numpy as np

from src import config
from src.data import build_text, load_kb

EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_CHARS = 512   # ~128 tokens, the model's window
CHUNK = 1024      # tickets per saved part file (resumable build). Changing it invalidates emb_parts/
PARTS_DIR = config.ARTIFACTS / "emb_parts"
EMB_PATH = config.ARTIFACTS / "kb_emb.npy"
IDS_PATH = config.ARTIFACTS / "kb_emb_ids.npy"

_tfidf = None
_embedder = None


def _kb_texts(kb) -> list[str]:
    return [build_text(s, b)[:MAX_CHARS] for s, b in zip(kb["subject"], kb["body"])]


def get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding(EMB_MODEL)
    return _embedder


def embed(texts: list[str]) -> np.ndarray:
    """L2-normalised float32 embeddings, shape (n, 384)."""
    vecs = np.array(list(get_embedder().embed(texts, batch_size=64)), dtype="float32")
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True).clip(min=1e-12)


def build(max_chunks: int | None = None) -> None:
    kb = load_kb("fit")
    texts = _kb_texts(kb)
    n_chunks = math.ceil(len(texts) / CHUNK)
    todo = n_chunks if max_chunks is None else min(max_chunks, n_chunks)
    PARTS_DIR.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    for c in range(todo):
        part = PARTS_DIR / f"part_{c:03d}.npy"
        if part.exists():
            continue
        np.save(part, embed(texts[c * CHUNK:(c + 1) * CHUNK]))
        print(f"chunk {c + 1}/{n_chunks} saved ({time.perf_counter() - t0:.0f}s elapsed)", flush=True)

    done = 0
    while (PARTS_DIR / f"part_{done:03d}.npy").exists():
        done += 1
    vecs = np.concatenate([np.load(PARTS_DIR / f"part_{c:03d}.npy") for c in range(done)])
    np.save(EMB_PATH, vecs)
    np.save(IDS_PATH, kb["ticket_id"].to_numpy().astype(str)[: len(vecs)])
    print(f"index: {len(vecs)}/{len(texts)} KB tickets embedded, dim={vecs.shape[1]} -> {EMB_PATH.name}")


# ---------- search (Step 2 replaces this TF-IDF version with FAISS) ----------

def _tfidf_index():
    """Fallback: word TF-IDF cosine over the fit KB. Works with no embeddings."""
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=None, help="embed only the first N chunks (quick dev index)")
    build(ap.parse_args().chunks)
