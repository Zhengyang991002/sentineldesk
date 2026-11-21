"""Precedent retrieval over the KB (fit part). Owner: RAG.

CONTRACT:
    search(text, k=TOP_K) -> [
        {"ticket_id": "TKT-01234", "score": 0.83, "language": "en", "subject": str,
         "answer": str, "type": str, "queue": str, "priority": str},
        ...  # sorted by score desc; score = cosine similarity
    ]
    active_backend() -> "embedding" | "tfidf"   # tfidf only when the embedding files are missing

Build the embedding index:
    python -m src.retrieval --chunks 2   # quick dev index (2,048 tickets)
    python -m src.retrieval              # full KB; resumes finished chunks
Try a query:
    python -m src.retrieval --query "Mein VPN funktioniert seit heute Morgen nicht mehr"
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
_emb = None


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


# ---------- search ----------

def _s(value) -> str:
    return "" if value is None or (isinstance(value, float) and value != value) else str(value)


def _hit(rows, i, score) -> dict:
    row = rows.iloc[int(i)]
    return {"ticket_id": row["ticket_id"], "score": float(score), "language": row["language"],
            "subject": _s(row["subject"]), "answer": _s(row["answer"]),
            "type": row["type"], "queue": row["queue"], "priority": row["priority"]}


def _emb_index():
    """FAISS inner-product index over saved embeddings (= cosine, vectors are normalised).
    Rows are aligned to the KB by ticket_id, not by position. Returns None if not built yet."""
    global _emb
    if _emb is None and EMB_PATH.exists() and IDS_PATH.exists():
        import faiss
        vecs = np.ascontiguousarray(np.load(EMB_PATH), dtype="float32")
        ids = np.load(IDS_PATH)
        if len(vecs) != len(ids):
            raise RuntimeError(f"{EMB_PATH.name} has {len(vecs)} rows but {IDS_PATH.name} has {len(ids)}")
        kb = load_kb("fit").set_index("ticket_id", drop=False)
        missing = [t for t in ids if t not in kb.index]
        if missing:
            raise RuntimeError(f"{len(missing)} embedded ids are not in the local KB (e.g. {missing[0]}): "
                               "embeddings were built from a different split; rerun prepare_data or rebuild")
        if len(ids) < len(kb):
            print(f"[retrieval] WARNING: partial index, {len(ids)}/{len(kb)} KB tickets embedded")
        index = faiss.IndexFlatIP(vecs.shape[1])
        index.add(vecs)
        _emb = (index, kb.loc[ids].reset_index(drop=True))  # row i <-> vecs[i]
    return _emb


def _tfidf_index():
    """Fallback only: word TF-IDF cosine over the fit KB (no cross-lingual matching)."""
    global _tfidf
    if _tfidf is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        kb = load_kb("fit")
        texts = [build_text(s, b) for s, b in zip(kb["subject"], kb["body"])]
        vec = TfidfVectorizer(sublinear_tf=True, min_df=2, max_features=200_000, ngram_range=(1, 2))
        _tfidf = (vec, vec.fit_transform(texts), kb)
    return _tfidf


def active_backend() -> str:
    return "embedding" if _emb_index() is not None else "tfidf"


def search(text: str, k: int = config.TOP_K) -> list[dict]:
    emb = _emb_index()
    if emb is not None:
        index, rows = emb
        scores, pos = index.search(embed([text[:MAX_CHARS]]), k)
        return [_hit(rows, i, s) for i, s in zip(pos[0], scores[0]) if i >= 0]
    vec, matrix, kb = _tfidf_index()
    scores = (matrix @ vec.transform([text]).T).toarray().ravel()
    top = scores.argsort()[::-1][:k]
    return [_hit(kb, i, scores[i]) for i in top]


def _show(query: str) -> None:
    t = time.perf_counter()
    hits = search(query)
    print(f"backend={active_backend()}  ({(time.perf_counter() - t) * 1000:.0f} ms)\nquery: {query}")
    for h in hits:
        print(f"  {h['ticket_id']}  {h['score']:.3f}  [{h['language']}] {h['queue']:<28} {h['subject'][:60]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=None, help="embed only the first N chunks (quick dev index)")
    ap.add_argument("--query", help="search the index instead of building it")
    args = ap.parse_args()
    if args.query:
        _show(args.query)
    else:
        build(args.chunks)
