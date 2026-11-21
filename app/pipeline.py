"""Pipeline entry point for the API: ticket in, UI-shaped result out.

PIPELINE_MODE selects what runs behind POST /triage:

    real  (default)  src.pipeline.run: classifier, retrieval, escalation gate, reply generation.
    mock             app/mocks.py, deterministic and keyword-routed. No model files needed (UI dev only).
    auto             real if it loads (model artifacts and KB present), otherwise mock.

The response shape is the same in every mode (see docs/ARCHITECTURE.md). To change what a real
stage does, edit the module under src/. To change how the output is mapped to the UI schema,
edit `_to_api_result`. Nothing outside this file has to know which mode is active.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

from app import mocks

log = logging.getLogger("sentineldesk")

STAGES = ("triage", "retrieve", "gate", "draft")


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _top(value: Any) -> tuple[str, float]:
    """Reduce a per-class result to (label, probability).

    Accepts {"label": ..., "confidence": ...} (src.triage), {class: probability} (mocks)
    or a (label, probability) pair.
    """
    if isinstance(value, dict):
        if "label" in value and "confidence" in value:
            return str(value["label"]), float(value["confidence"])
        if value:
            label = max(value, key=value.get)
            return str(label), float(value[label])
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return str(value[0]), float(value[1])
    return str(value), 0.0


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
            "reason": "; ".join(gate["reasons"]) or "All escalation checks passed.",
            "rules": list(gate["rules"]),        # e.g. ["R1", "R4"]
            "reasons": list(gate["reasons"]),    # one human-readable reason per rule
        },
        "pii_masked": out.get("pii", {}),
        "retrieved": [
            {"ticket_id": str(h["ticket_id"]), "score": float(h["score"]), "answer": str(h["answer"]),
             "language": str(h.get("language", "")), "subject": str(h.get("subject", ""))}
            for h in out["hits"]
        ],
        # "llm" (Gemini), "fallback" (template after an LLM error) or "holding" (R3/R5: no draft attempted)
        "draft_source": out["draft"].get("source"),
        # An escalated ticket is not shown a draft, even though src.pipeline may have produced one.
        "draft": None
        if escalate
        else {"reply": out["draft"]["reply"], "cited_ids": list(out["draft"]["cited_ids"])},
    }


def _run_real(subject: str | None, body: str) -> dict:
    from src import pipeline as core

    return _to_api_result(core.run(subject, body))


def _warm_real() -> None:
    """Load the classifier and build the retrieval index now, so the first request is not slow."""
    from src import pipeline as core

    log.info("Pipeline warmup: %s ms", core.warmup())


# ---------------------------------------------------------------------------------------------
# Mock pipeline: the four stage functions in app/mocks.py, run in order
# ---------------------------------------------------------------------------------------------

class _StageError(Exception):
    def __init__(self, stage: str):
        self.stage = stage


def _timed(stage: str, stage_ms: dict, fn: Callable, *args, **kwargs):
    started = time.perf_counter()
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        log.exception("stage %s failed", stage)
        raise _StageError(stage) from exc
    finally:
        stage_ms[stage] = _ms(started)


def _run_mock(subject: str | None, body: str) -> dict:
    started = time.perf_counter()
    text = f"{subject or ''} {body}".strip()
    stage_ms = dict.fromkeys(STAGES, 0)
    stage = "triage"  # blamed if a stage returns malformed output
    try:
        tri = _timed("triage", stage_ms, mocks.triage, subject, body)
        type_label, type_conf = _top(tri["type"])
        queue_label, queue_conf = _top(tri["queue"])
        prio_label, prio_conf = _top(tri["priority"])
        language = tri.get("language") if tri.get("language") in ("en", "de") else _detect_language(text)

        stage = "retrieve"
        hits = _timed("retrieve", stage_ms, mocks.retrieve, text, k=5)

        stage = "gate"
        gate = _timed("gate", stage_ms, mocks.gate, tri, hits)
        escalate = bool(gate["escalate"])

        draft = None
        if not escalate:
            stage = "draft"
            d = _timed("draft", stage_ms, mocks.draft, text, language, hits)
            draft = {"reply": str(d["reply"]), "cited_ids": [str(c) for c in d.get("cited_ids", [])]}
    except _StageError as err:
        return _failure(f"Pipeline error: {err.stage}", text, stage_ms, started)
    except Exception:
        log.exception("malformed output from stage %s", stage)
        return _failure(f"Pipeline error: {stage}", text, stage_ms, started)

    return {
        "type": type_label,
        "queue": queue_label,
        "priority": prio_label if prio_label in ("high", "medium", "low") else "medium",
        "confidences": {"type": type_conf, "queue": queue_conf, "priority": prio_conf},
        "language": language,
        "latency_ms": _ms(started),
        "stage_ms": stage_ms,
        "escalation": {"escalate": escalate, "reason": str(gate.get("reason", ""))},
        "retrieved": [
            {"ticket_id": str(h["ticket_id"]), "score": float(h["score"]), "answer": str(h["answer"])}
            for h in hits
        ],
        "draft": draft,
    }


# ---------------------------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------------------------

def _select_mode() -> str:
    requested = os.getenv("PIPELINE_MODE", "real").strip().lower()
    if requested not in ("mock", "real", "auto"):
        log.warning("Unknown PIPELINE_MODE=%r, using mock", requested)
        return "mock"
    if requested == "mock":
        return "mock"
    try:
        _warm_real()
        return "real"
    except Exception as exc:
        if requested == "real":
            raise RuntimeError(f"PIPELINE_MODE=real but the pipeline failed to load: {exc}") from exc
        log.warning("Real pipeline unavailable (%s: %s), falling back to mock", type(exc).__name__, exc)
        return "mock"


MODE = _select_mode()
log.info("Pipeline mode: %s", MODE)


def run_pipeline(subject: str | None, body: str) -> dict:
    """Triage one ticket. Never raises for a failing stage: the ticket is escalated instead."""
    started = time.perf_counter()
    try:
        return _run_real(subject, body) if MODE == "real" else _run_mock(subject, body)
    except Exception:
        log.exception("pipeline failed")
        text = f"{subject or ''} {body}".strip()
        return _failure("Pipeline error", text, dict.fromkeys(STAGES, 0), started)
