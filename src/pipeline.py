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

    # Who decides escalation:
    #   1. Similar resolved cases exist -> the ML model decides (escalate iff R1 very high severity);
    #      Gemini only drafts the grounded reply.
    #   2. No similar resolved case (R3) -> the Gemini agent decides (escalate or answer on its own).
    #   3. Agent fails, or the ticket looks adversarial (R5) -> escalate (no precedent to fall back on).
    pre = gate.pre_check(raw, tri, hits)
    holding = {"reply": generate.holding_reply(language), "cited_ids": [], "unsupported_requests": [],
               "source": "holding", "error": None}
    agent_out, agent_error = None, None
    if "R3" not in pre["rules"]:
        decided_by = "ml"
    elif "R5" in pre["flags"]:  # adversarial text never reaches the LLM
        decided_by, agent_error = "rule", "skipped: possible prompt injection"
    else:
        try:
            agent_out = generate.agent(masked, language, hits, tri, gate.signals(raw, tri, hits))
            decided_by = "agent"
        except Exception as exc:
            decided_by, agent_error = "rule", f"{type(exc).__name__}: {exc}"

    decision = gate.decide(pre, None, decided_by=decided_by, agent=agent_out, agent_error=agent_error)
    if decision["status"] == "ESCALATE":
        draft, post = holding, None
    else:
        if agent_out is not None:
            draft = agent_out
        elif "R5" in pre["flags"]:
            draft = generate.extractive(language, hits)
        else:
            draft = generate.draft(masked, language, hits, tri)
        post = gate.post_check(draft, hits, language)
        decision = gate.decide(pre, post, decided_by=decided_by, agent=agent_out, agent_error=agent_error)
    t4 = time.perf_counter()

    ms = lambda a, b: round((b - a) * 1000, 1)
    return {
        "language": language, "masked_text": masked, "pii": pii_found,
        "triage": tri, "hits": hits, "gate": decision, "draft": draft,
        "latency_ms": {"triage": ms(t1, t2), "retrieval": ms(t2, t3), "generate": ms(t3, t4), "total": ms(t0, t4)},
    }


def warmup() -> float:
    """Load the language detector, classifier, embedding model and FAISS index once. Returns ms."""
    t0 = time.perf_counter()
    lang.detect("warm up the language detector")
    triage.predict(None, "warm up")
    retrieval.search("warm up the embedding model and index", k=1)
    return round((time.perf_counter() - t0) * 1000, 1)


if __name__ == "__main__":
    print(f"warmup: {warmup()} ms ({retrieval.active_backend()} retrieval, {triage.active_model()} classifier)")
    import json
    out = run(None, "Our VPN has been down since 8am and the hospital cannot reach the EMR system. Contact me at a.b@x.com")
    out["hits"] = [{k: h[k] for k in ("ticket_id", "score", "language")} for h in out["hits"]]
    print(json.dumps(out, indent=2, ensure_ascii=False)[:3000])
