"""End-to-end orchestration. Owner: integrator.  Quick test:  python -m src.pipeline"""
import time

from src import gate, generate, lang, pii, retrieval, triage
from src.data import build_text


def run(subject, body) -> dict:
    t0 = time.perf_counter()
    raw = build_text(subject, body)
    if not raw:
        raise ValueError("Ticket body is empty")
    language = lang.detect(raw)
    masked, pii_found = pii.mask(raw)

    t1 = time.perf_counter()
    tri = triage.predict(subject, body)
    t2 = time.perf_counter()
    hits = retrieval.search(masked)
    t3 = time.perf_counter()

    pre = gate.pre_check(raw, tri, hits)
    if {"R3", "R5"} & set(pre["rules"]):  # no precedent or adversarial: do not draft
        draft = {"reply": generate.holding_reply(language), "cited_ids": [], "unsupported_requests": [],
                 "source": "holding", "error": None}
        post = None
    else:
        draft = generate.draft(masked, language, hits, tri)
        post = gate.post_check(draft, hits, language)
    t4 = time.perf_counter()

    ms = lambda a, b: round((b - a) * 1000, 1)
    return {
        "language": language, "masked_text": masked, "pii": pii_found,
        "triage": tri, "hits": hits, "gate": gate.decide(pre, post), "draft": draft,
        "latency_ms": {"triage": ms(t1, t2), "retrieval": ms(t2, t3), "generate": ms(t3, t4), "total": ms(t0, t4)},
    }


if __name__ == "__main__":
    import json
    out = run(None, "Our VPN has been down since 8am and the hospital cannot reach the EMR system. Contact me at a.b@x.com")
    out["hits"] = [{k: h[k] for k in ("ticket_id", "score", "language")} for h in out["hits"]]
    print(json.dumps(out, indent=2, ensure_ascii=False)[:3000])
