"""Pipeline entry point for the API: ticket in, UI-shaped result out.

POST /triage always runs src.pipeline.run: classifier, retrieval, escalation gate, reply
generation. Model artifacts and the KB must be present; the app refuses to start otherwise.

The response shape is documented in docs/ARCHITECTURE.md. To change what a real
stage does, edit the module under src/. To change how the output is mapped to the UI schema,
edit `_to_api_result`.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger("sentineldesk")

STAGES = ("triage", "retrieve", "gate", "draft")


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _detect_language(text: str) -> str:
    try:
        from src.lang import detect

        return detect(text)
    except Exception:
        return "en"


def _failure(reason: str, text: str, stage_ms: dict, started: float) -> dict:
    """Escalated placeholder result returned when a stage raises."""
    return {
        "type": "unknown",
        "queue": "unknown",
        "priority": "high",  # a failed run is treated as urgent
        "confidences": {"type": 0.0, "queue": 0.0, "priority": 0.0},
        "language": _detect_language(text),
        "latency_ms": _ms(started),
        "stage_ms": stage_ms,
        "escalation": {"escalate": True, "reason": reason},
        "retrieved": [],
        "draft": None,
    }


# ---------------------------------------------------------------------------------------------
# Real pipeline: src.pipeline.run
# ---------------------------------------------------------------------------------------------

def _to_api_result(out: dict) -> dict:
    """Map src.pipeline.run's output to the API schema."""
    triage, gate, latency = out["triage"], out["gate"], out["latency_ms"]
    escalate = gate["status"] == "ESCALATE"
    return {
        "type": triage["type"]["label"],
        "queue": triage["queue"]["label"],
        "priority": triage["priority"]["label"],
        "confidences": {k: triage[k]["confidence"] for k in ("type", "queue", "priority")},
        "language": out["language"],
        "latency_ms": round(latency["total"]),
        # src.pipeline does not time the gate on its own; it is included in retrieval/generate.
        "stage_ms": {
            "triage": round(latency["triage"]),
            "retrieve": round(latency["retrieval"]),
            "gate": 0,
            "draft": round(latency["generate"]),
        },
        "escalation": {
            "escalate": escalate,
            "reason": "; ".join(gate["reasons"])
            or (gate["flag_reasons"][0] if gate.get("decided_by") == "agent" and gate["flag_reasons"]
                else "Similar resolved case found and severity is not very high: auto-draft."),
            "decided_by": gate.get("decided_by", "ml"),  # "ml" (similar cases), "agent" (Gemini, no similar case), "rule" (agent failed)
            "rules": list(gate["rules"]),            # R1 (ML), AGENT (Gemini) or R3 (no similar case, agent failed)
            "reasons": list(gate["reasons"]),
            "flags": list(gate["flags"]),            # R4/R5/R6: shown to the operator, never escalate
            "flag_reasons": list(gate["flag_reasons"]),
        },
        "pii_masked": out.get("pii", {}),
        "retrieved": [
            {"ticket_id": str(h["ticket_id"]), "score": float(h["score"]), "answer": str(h["answer"]),
             "language": str(h.get("language", "")), "subject": str(h.get("subject", ""))}
            for h in out["hits"]
        ],
        # An escalated ticket is not shown a draft, even though src.pipeline may have produced one.
        "draft": None
        if escalate
        else {"reply": out["draft"]["reply"], "cited_ids": list(out["draft"]["cited_ids"]),
              "source": out["draft"].get("source", "fallback")},  # "llm" = Gemini, else extractive
    }


def _run_real(subject: str | None, body: str) -> dict:
    from src import pipeline as core

    return _to_api_result(core.run(subject, body))


def _warm_real() -> None:
    """Load the classifier, embedding model and FAISS index now, so the first request is not slow."""
    from src import pipeline as core
    from src import retrieval, triage

    ms = core.warmup()
    log.info("Pipeline warmup: %s ms (%s retrieval, %s classifier)",
             ms, retrieval.active_backend(), triage.active_model())


# ---------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------

def _load() -> str:
    """Load the real pipeline at import time. Fails loudly if model artifacts or the KB are missing."""
    try:
        _warm_real()
    except Exception as exc:
        raise RuntimeError(f"The pipeline failed to load: {exc}") from exc
    return "real"


MODE = _load()
log.info("Pipeline mode: %s", MODE)


def run_pipeline(subject: str | None, body: str) -> dict:
    """Triage one ticket. Never raises for a failing stage: the ticket is escalated instead."""
    started = time.perf_counter()
    try:
        return _run_real(subject, body)
    except Exception:
        log.exception("pipeline failed")
        text = f"{subject or ''} {body}".strip()
        return _failure("Pipeline error", text, dict.fromkeys(STAGES, 0), started)
