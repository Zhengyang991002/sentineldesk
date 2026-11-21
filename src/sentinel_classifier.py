"""
SentinelDesk - Triage classifier (TF-IDF LogisticRegression + kNN votes, calibrated ensemble).

kNN votes come from one or more "sources" (state["knn_sources"]):
    "char"  cosine over the char_wb 3-5gram TF-IDF (robust to German compounds)
    "emb"   cosine over multilingual sentence embeddings (src.retrieval.embed,
            paraphrase-multilingual-MiniLM-L12-v2): a German ticket can match English precedents
    "word"  cosine over the word 1-2gram TF-IDF (legacy models; weights key "knn")
The probabilities of LR and every kNN source are averaged with per-target weights tuned on val.

Usage in the app:
    from sentinel_classifier import TriageModel
    model = TriageModel.load("sentinel_model")   # folder with model.joblib + kb.parquet (+ kb_emb.npy)
    result = model.triage(subject="VPN down", body="Since 7am nobody can connect...")

Retrain from the CSV (uses ONLY the 80% modelling split; the 20% test split is never touched):
    python -m src.sentinel_classifier train data/raw/tickets.csv artifacts/sentinel_model
Quick test from the terminal:
    python -m src.sentinel_classifier demo artifacts/sentinel_model
"""
import itertools
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.sparse import hstack
from scipy.special import logsumexp, softmax
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, recall_score
from sklearn.preprocessing import normalize

TARGETS = ["type", "queue", "priority"]
RANDOM_STATE = 42
KNN_SOURCES = ["char", "emb"]   # sources used by train()
EMB_FILE = "kb_emb.npy"         # KB embeddings saved next to model.joblib, row-aligned with kb.parquet


# --------------------------------------------------------------------------- utils
def clean_text(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return str(s).replace("\\n", "\n").strip()


def build_text(subject, body):
    return (clean_text(subject) + "\n" + clean_text(body)).strip()


def embed_texts(texts, batch_size=16):
    """L2-normalised multilingual embeddings (same model and truncation as src.retrieval)."""
    from src import retrieval
    vecs = np.array(list(retrieval.get_embedder().embed([t[:retrieval.MAX_CHARS] for t in texts],
                                                         batch_size=batch_size)), dtype="float32")
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True).clip(min=1e-12)


def fit_temperature(probs, y):
    logp = np.log(np.clip(probs, 1e-12, 1))

    def nll(T):
        z = logp / T
        z = z - logsumexp(z, axis=1, keepdims=True)
        return -z[np.arange(len(y)), y].mean()

    return float(minimize_scalar(nll, bounds=(0.05, 10), method="bounded").x)


def apply_temperature(probs, T):
    return softmax(np.log(np.clip(probs, 1e-12, 1)) / T, axis=1)


def detect_language(text):
    """Returns (reply language en/de, raw most likely language)."""
    try:
        from langdetect import DetectorFactory, detect_langs
        DetectorFactory.seed = 0
        cand = {l.lang: l.prob for l in detect_langs(text)}
        top = max(cand, key=cand.get)
        return ("de" if cand.get("de", 0) > cand.get("en", 0) else "en"), top
    except Exception:
        return "en", "unknown"


def _top_k(Q, KT, k, chunk=512):
    """Top-k cosine neighbours. KT = the KB matrix already transposed (features x kb); rows of Q
    and of the KB are L2-normalised; sparse or dense. Pre-transposing matters: transposing a
    sparse 22k x 50k matrix on every query costs ~2.5 s."""
    idx_all, sim_all = [], []
    for st in range(0, Q.shape[0], chunk):
        S = Q[st:st + chunk] @ KT
        S = S.toarray() if hasattr(S, "toarray") else np.asarray(S)
        idx = np.argpartition(-S, k, axis=1)[:, :k]
        ss = np.take_along_axis(S, idx, 1)
        o = np.argsort(-ss, 1)
        idx_all.append(np.take_along_axis(idx, o, 1))
        sim_all.append(np.take_along_axis(ss, o, 1))
    return np.vstack(idx_all), np.vstack(sim_all)


# --------------------------------------------------------------------------- model
class TriageModel:
    def __init__(self, state, kb, kb_emb=None):
        self.s = state
        self.kb = kb.reset_index(drop=True)
        self.classes = state["classes"]
        self.inc = self.classes["type"].index("Incident")
        self.high = self.classes["priority"].index("high")
        self.kb_y = {t: self.kb[t].map({c: i for i, c in enumerate(self.classes[t])}).values for t in TARGETS}
        self.sources = state.get("knn_sources", ["word"])
        # precedents / similarity gate use the embedding index when there is one
        self.primary = "emb" if "emb" in self.sources else self.sources[0]
        self.kb_vecs = {}
        for src in self.sources:
            if src == "emb":
                if kb_emb is None:
                    raise ValueError("this model uses embedding kNN: pass kb_emb (rows aligned with kb)")
                if len(kb_emb) != len(self.kb):
                    raise ValueError(f"kb_emb has {len(kb_emb)} rows, kb has {len(self.kb)}")
                self.kb_vecs[src] = np.ascontiguousarray(kb_emb, dtype="float32")
            else:
                self.kb_vecs[src] = self._query_vecs(src, self.kb["text"])
        # transposed once here, reused by every query (see _top_k)
        self._kb_T = {src: (v.T.tocsr() if hasattr(v, "tocsr") else np.ascontiguousarray(v.T))
                      for src, v in self.kb_vecs.items()}

    # ---- persistence
    @classmethod
    def load(cls, folder):
        emb_path = os.path.join(folder, EMB_FILE)
        kb_emb = np.load(emb_path) if os.path.exists(emb_path) else None
        return cls(joblib.load(os.path.join(folder, "model.joblib")),
                   pd.read_parquet(os.path.join(folder, "kb.parquet")), kb_emb)

    def save(self, folder):
        os.makedirs(folder, exist_ok=True)
        joblib.dump(self.s, os.path.join(folder, "model.joblib"), compress=3)
        self.kb.to_parquet(os.path.join(folder, "kb.parquet"), index=False)
        if "emb" in self.kb_vecs:
            np.save(os.path.join(folder, EMB_FILE), self.kb_vecs["emb"])

    # ---- components
    def _features(self, texts):
        return hstack([self.s["vec_word"].transform(texts), self.s["vec_char"].transform(texts)]).tocsr()

    def _query_vecs(self, source, texts):
        texts = list(texts)
        if source == "emb":
            return embed_texts(texts)
        vec = {"word": "vec_word", "char": "vec_char"}[source]
        return normalize(self.s[vec].transform(texts))

    def _knn(self, texts, k, source=None, Q=None):
        source = source or self.primary
        if Q is None:
            Q = self._query_vecs(source, texts)
        return _top_k(Q, self._kb_T[source], k)

    def _knn_probs(self, idx, sims, tau=0.05, smooth=0.02):
        w = softmax(sims / tau, axis=1)
        out = {}
        for t in TARGETS:
            n = len(self.classes[t])
            p = np.zeros((len(idx), n))
            lab = self.kb_y[t][idx]
            for j in range(idx.shape[1]):
                p[np.arange(len(idx)), lab[:, j]] += w[:, j]
            out[t] = (1 - smooth) * p + smooth / n
        return out

    def components(self, texts, k=None):
        """Per-component probabilities: {"tfidf": {t: P}, <source>: {t: P}}, plus primary-source knn idx/sims."""
        k = k or self.s["knn_k"]
        X = self._features(texts)
        comp = {"tfidf": {t: self.s["lr"][t].predict_proba(X) for t in TARGETS}}
        knn = {}
        for src in self.sources:
            idx, sims = self._knn(texts, k, src)
            comp[src] = self._knn_probs(idx, sims)
            knn[src] = (idx, sims)
        return comp, knn

    def _blend(self, comp, t):
        w = self.s["weights"][t]
        out = w["tfidf"] * comp["tfidf"][t]
        for src in self.sources:
            out = out + w.get(src, w.get("knn", 0.0) if src == "word" else 0.0) * comp[src][t]
        return out

    def predict_proba(self, texts, calibrated=True):
        """Batch prediction. Returns ({target: probs}, knn_idx, knn_sims) (knn = primary source)."""
        comp, knn = self.components(texts)
        out = {}
        for t in TARGETS:
            p = self._blend(comp, t)
            out[t] = apply_temperature(p, self.s["temps"][t]) if calibrated else p
        idx, sims = knn[self.primary]
        return out, idx, sims

    # ---- main entry point for the app
    def triage(self, subject, body, n_precedents=5):
        t_all = time.perf_counter()
        text = build_text(subject, body)
        if not text:
            raise ValueError("Empty ticket")
        lang, lang_raw = detect_language(text)
        probs, idx, sims = self.predict_proba([text])
        if idx.shape[1] < n_precedents:
            idx, sims = self._knn([text], n_precedents)
        cal = {t: probs[t][0] for t in TARGETS}
        pred = {t: self.classes[t][int(cal[t].argmax())] for t in TARGETS}
        conf = {t: float(cal[t].max()) for t in TARGETS}
        score = float(cal["type"][self.inc] * cal["priority"][self.high])
        top1 = float(sims[0, 0])
        g = self.s["gate"]

        reasons = []
        if score >= g["HPI_THRESHOLD"]:
            reasons.append(f"Possible high-priority incident (score {score:.2f} >= {g['HPI_THRESHOLD']:.2f})")
        if conf["queue"] < g["CONF_THRESHOLD_QUEUE"]:
            reasons.append(f"Low routing confidence ({conf['queue']:.0%} < {g['CONF_THRESHOLD_QUEUE']:.0%})")
        if top1 < g["SIM_THRESHOLD"]:
            reasons.append(f"No similar historical precedent (similarity {top1:.2f} < {g['SIM_THRESHOLD']:.2f})")
        if lang_raw not in ("en", "de"):
            reasons.append(f"Unsupported language detected ({lang_raw})")

        precedents = [{
            "ticket_id": self.kb["ticket_id"].iat[i], "similarity": round(float(s), 3),
            "subject": self.kb["subject"].iat[i], "queue": self.kb["queue"].iat[i],
            "language": self.kb["language"].iat[i], "answer": self.kb["answer"].iat[i],
        } for i, s in zip(idx[0, :n_precedents], sims[0, :n_precedents])]

        return {
            "language": lang, "type": pred["type"], "queue": pred["queue"], "priority": pred["priority"],
            "confidence": conf,
            "probabilities": {t: dict(zip(self.classes[t], np.round(cal[t], 3).tolist())) for t in TARGETS},
            "hpi_score": round(score, 3), "escalate": bool(reasons),
            "status": "Escalate to On-Call Engineer" if reasons else "Auto-Draft Ready",
            "reasons": reasons, "precedents": precedents,
            "latency_ms": round((time.perf_counter() - t_all) * 1000, 1),
        }


# --------------------------------------------------------------------------- training
def _weight_grid(names, step=0.1):
    """All weight vectors over `names` on a simplex grid (sum = 1)."""
    n = int(round(1 / step))
    for combo in itertools.product(range(n + 1), repeat=len(names) - 1):
        if sum(combo) <= n:
            yield dict(zip(names, [c / n for c in combo] + [(n - sum(combo)) / n]))


def train(csv_path, out_dir, target_hpi_recall=0.90, target_auto_acc=0.80, knn_k=10, sources=KNN_SOURCES):
    """Fit on the 80% modelling split only: train part (90%) fits the models, val part (10%) tunes
    ensemble weights, temperatures and gate thresholds. The 20% test split is never loaded."""
    t0 = time.time()
    df = pd.read_csv(csv_path)
    for c in ["subject", "body", "answer"]:
        df[c] = df[c].map(clean_text)
    df["text"] = [build_text(s, b) for s, b in zip(df["subject"], df["body"])]
    # identical split to the EDA notebook / challenge snippet
    df = df.sample(frac=1.0, random_state=RANDOM_STATE).reset_index(drop=True)
    df["ticket_id"] = [f"TKT-{i:05d}" for i in range(len(df))]
    kb_df = df.iloc[:int(len(df) * 0.8)].copy().reset_index(drop=True)
    del df  # the remaining 20% is the evaluation split: not used here
    is_val = np.random.RandomState(RANDOM_STATE).rand(len(kb_df)) < 0.10
    tr, va = kb_df[~is_val].copy(), kb_df[is_val].copy()

    kb_emb = None
    if "emb" in sources:  # first, while memory is free (ONNX needs contiguous buffers)
        print(f"  embedding {len(kb_df)} KB tickets...", flush=True)
        kb_emb = embed_texts(kb_df["text"].tolist())
        print(f"  embeddings done ({time.time() - t0:.0f}s)", flush=True)

    classes = {t: sorted(tr[t].unique()) for t in TARGETS}
    yof = lambda f, t: f[t].map({c: i for i, c in enumerate(classes[t])}).values

    vec_word = TfidfVectorizer(min_df=2, ngram_range=(1, 2), sublinear_tf=True, max_features=200_000)
    vec_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True, max_features=200_000)
    Xtr = hstack([vec_word.fit_transform(tr["text"]), vec_char.fit_transform(tr["text"])]).tocsr()
    lr = {}
    for t in TARGETS:
        print(f"  training {t}...", flush=True)
        lr[t] = LogisticRegression(max_iter=2000, C=4, class_weight="balanced").fit(Xtr, yof(tr, t))
    del Xtr

    cols = ["ticket_id", "subject", "body", "answer", "text", "type", "queue", "priority", "language"]
    names = ["tfidf"] + list(sources)
    state = {"vec_word": vec_word, "vec_char": vec_char, "lr": lr, "classes": classes, "knn_k": knn_k,
             "knn_sources": list(sources),
             "weights": {t: {n: 1 / len(names) for n in names} for t in TARGETS}, "temps": {t: 1.0 for t in TARGETS},
             "gate": {}}
    m = TriageModel(state, tr[cols], kb_emb[~is_val] if kb_emb is not None else None)  # kNN index = train only

    # --- tune ensemble weights, temperatures and gate on VALIDATION
    comp, knn = m.components(va["text"].tolist())
    for t in TARGETS:
        y = yof(va, t)
        mix = lambda w: sum(w[n] * comp[n][t] for n in names)
        w = max(_weight_grid(names), key=lambda w: f1_score(y, mix(w).argmax(1), average="macro"))
        state["weights"][t] = {n: round(v, 2) for n, v in w.items()}
        state["temps"][t] = fit_temperature(mix(w), y)
    pv = {t: apply_temperature(m._blend(comp, t), state["temps"][t]) for t in TARGETS}
    sv = knn[m.primary][1]

    inc, high = classes["type"].index("Incident"), classes["priority"].index("high")
    yt = (yof(va, "type") == inc) & (yof(va, "priority") == high)
    score = pv["type"][:, inc] * pv["priority"][:, high]
    ths = np.linspace(0.01, 0.9, 180)
    ok = [th for th in ths if recall_score(yt, score >= th) >= target_hpi_recall]
    conf = pv["queue"].max(1)
    correct = pv["queue"].argmax(1) == yof(va, "queue")
    order = np.argsort(-conf)
    cum = np.cumsum(correct[order]) / np.arange(1, len(order) + 1)
    good = np.where(cum >= target_auto_acc)[0]
    state["gate"] = {"HPI_THRESHOLD": float(max(ok) if ok else ths[0]),
                     "CONF_THRESHOLD_QUEUE": float(conf[order][good[-1]]) if len(good) else 1.0,
                     "SIM_THRESHOLD": float(np.quantile(sv[:, 0], 0.05))}

    # val metrics (in-sample for the tuned weights: optimistic, for reference only)
    state["val_metrics"] = {f"{t}_{k}": round(float(v), 4) for t in TARGETS for k, v in [
        ("macro_f1", f1_score(yof(va, t), pv[t].argmax(1), average="macro")),
        ("accuracy", (pv[t].argmax(1) == yof(va, t)).mean())]}

    # --- final model: kNN index over the whole 80% KB (train + val), never the test split
    final = TriageModel(state, kb_df[cols], kb_emb)
    final.save(out_dir)
    print(f"Saved to {out_dir} in {time.time() - t0:.0f}s")
    print("weights:", state["weights"], "\ntemperatures:", state["temps"], "\ngate:", state["gate"])
    print("val metrics:", state["val_metrics"])
    return final


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "train":
        train(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "demo":
        model = TriageModel.load(sys.argv[2])
        for s, b in [("VPN down - hospital EMR offline", "Since 7am our VPN is completely down. Doctors cannot reach the EMR. Please help immediately."),
                     (None, "Hallo, ich habe eine doppelte Abbuchung auf meiner letzten Rechnung gefunden. Können Sie das prüfen?"),
                     ("", "Do your products integrate with Salesforce? We are evaluating options for next quarter.")]:
            r = model.triage(s, b)
            print(f"\n{b[:60]}...\n  {r['type']} | {r['queue']} | {r['priority']} | conf {r['confidence']['queue']:.0%} | "
                  f"{r['status']} {r['reasons']} | {r['latency_ms']} ms")
            print("  precedents:", [(p["ticket_id"], p["similarity"]) for p in r["precedents"][:3]])
    else:
        print(__doc__)
