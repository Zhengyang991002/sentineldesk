"""Grounded reply generation. Owner: teammate 3.

CONTRACT:
    draft(text, target_lang, hits, triage) -> {
        "reply": str,                    # in target_lang ("en" | "de"), cites [TKT-xxxxx]
        "cited_ids": ["TKT-01234", ...], # must be a subset of hits' ticket_ids
        "unsupported_requests": [str],   # things the user asked for that no precedent supports
        "source": "llm" | "fallback",
        "error": str | None,
    }
    holding_reply(target_lang) -> str    # safe acknowledgement when we must not draft (R3/R5)

TODO(teammate 3):
  - _llm_draft(): call Claude (config.LLM_MODEL) via the official `anthropic` SDK with structured JSON
    output. Prompt rules: use ONLY the numbered evidence, cite ticket IDs, reply in target_lang,
    never invent prices / SLA / refunds / legal promises, list anything unsupported in
    unsupported_requests. Text passed in is already PII-masked by the pipeline.
  - On any API error/timeout, return the extractive fallback below (demo must never crash).
"""

HOLDING = {
    "en": "Thank you for reaching out. Your request has been forwarded to a specialist, who will contact you shortly.",
    "de": "Vielen Dank für Ihre Nachricht. Ihre Anfrage wurde an einen Spezialisten weitergeleitet, der sich in Kürze bei Ihnen meldet.",
}
_INTRO = {
    "en": "Thank you for contacting us. Based on similar resolved cases ({ids}), here is what we recommend:",
    "de": "Vielen Dank für Ihre Nachricht. Auf Basis ähnlicher gelöster Fälle ({ids}) empfehlen wir Folgendes:",
}


def holding_reply(target_lang: str) -> str:
    return HOLDING.get(target_lang, HOLDING["en"])


def _fallback(target_lang: str, hits: list[dict], error: str | None = None) -> dict:
    """Extractive: quote the best same-language precedent; never adds new facts."""
    same = [h for h in hits if h["language"] == target_lang and h["answer"]]
    if not same:
        return {"reply": holding_reply(target_lang), "cited_ids": [], "unsupported_requests": [],
                "source": "fallback", "error": error}
    best = same[0]
    snippet = " ".join(best["answer"].split()[:80])
    reply = f"{_INTRO[target_lang].format(ids=best['ticket_id'])}\n\n{snippet}"
    return {"reply": reply, "cited_ids": [best["ticket_id"]], "unsupported_requests": [],
            "source": "fallback", "error": error}


def _llm_draft(text: str, target_lang: str, hits: list[dict], triage: dict) -> dict:
    raise NotImplementedError("teammate 3: Claude call goes here")


def draft(text: str, target_lang: str, hits: list[dict], triage: dict) -> dict:
    try:
        return _llm_draft(text, target_lang, hits, triage)
    except Exception as exc:  # never crash the demo
        return _fallback(target_lang, hits, error=f"{type(exc).__name__}: {exc}")
