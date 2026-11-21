"""Confidence & risk escalation gate. Owner: integrator.

pre_check runs BEFORE generation (R1, R2, R3, R4-keyword, R5); post_check runs AFTER (R4-llm, R6).
Every reason is a human-readable string shown in the UI.
"""
import re

from src import config, lang

# Strong outage/safety signals (safety net in case the classifier misses a critical incident)
CRITICAL = re.compile(
    r"\b(outage|down for (all|everyone)|data breach|security breach|ransomware|hacked|hospital|patient|"
    r"emr|telemedicine|production (is )?down|ausfall|ausgefallen|totalausfall|datenleck|sicherheitsvorfall|"
    r"krankenhaus|klinik|patienten)\b", re.I)

# Requests the agent may only answer if a precedent's answer covers the same topic
UNSUPPORTED = {
    "refund/compensation": r"refund|reimburs|compensat|money back|chargeback|credit note|erstattung|rückerstattung|entschädigung|gutschrift|geld zurück",
    "pricing/discount": r"\bprice|pricing|quote|discount|cost of|preis|angebot|rabatt|kosten",
    "legal/guarantee/SLA": r"legal|lawsuit|lawyer|liabilit|guarantee|warranty|\bsla\b|anwalt|rechtlich|haftung|garantie|gewährleistung",
    "contract change": r"cancel (my|the|our) (contract|subscription)|terminate|kündig|vertrag",
    "data deletion": r"delete (all )?(my|our) data|gdpr|right to be forgotten|dsgvo|daten löschen",
}

INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior|above|the) (instructions|rules)|system prompt|you are now|"
    r"disregard (all|previous|your)|developer mode|jailbreak|ignoriere (alle |die )?(vorherigen |obigen )?anweisungen",
    re.I)

NUMBER_CLAIM = re.compile(r"\d+(?:[.,]\d+)?\s?(?:%|€|\$|eur\b|usd\b|days?\b|tage?n?\b|hours?\b|stunden?\b)", re.I)


def pre_check(text: str, triage: dict, hits: list[dict]) -> dict:
    reasons, rules = [], []
    t, p = triage["type"], triage["priority"]

    if p["label"] == "high" and t["label"] == "Incident":
        rules.append("R1"); reasons.append("High-priority Incident: page the on-call engineer")
    elif CRITICAL.search(text):
        rules.append("R1"); reasons.append(f"Critical keyword detected: '{CRITICAL.search(text).group(0)}'")

    low = [f"{name}={d['confidence']:.2f}" for name, d in (("type", t), ("priority", p))
           if d["confidence"] < config.TAU_CONF]
    if low:
        rules.append("R2"); reasons.append(f"Low classifier confidence ({', '.join(low)} < {config.TAU_CONF})")

    top = hits[0]["score"] if hits else 0.0
    if top < config.TAU_SIM:
        rules.append("R3"); reasons.append(f"No close precedent (top similarity {top:.2f} < {config.TAU_SIM})")

    evidence = " ".join(h["answer"] for h in hits).lower()
    for topic, pattern in UNSUPPORTED.items():
        if re.search(pattern, text, re.I) and not re.search(pattern, evidence, re.I):
            rules.append("R4"); reasons.append(f"Asks for {topic}, not covered by any retrieved resolution")

    if INJECTION.search(text):
        rules.append("R5"); reasons.append("Possible prompt injection / adversarial instruction")

    return {"rules": rules, "reasons": reasons}


def post_check(draft: dict, hits: list[dict], target_lang: str) -> dict:
    reasons, rules = [], []
    hit_ids = {h["ticket_id"] for h in hits}
    cited = set(draft.get("cited_ids") or [])
    if not cited:
        reasons.append("Draft cites no precedent")
    elif not cited <= hit_ids:
        reasons.append(f"Draft cites tickets that were not retrieved: {sorted(cited - hit_ids)}")

    evidence = " ".join(h["answer"] for h in hits).lower()
    invented = [m for m in NUMBER_CLAIM.findall(draft.get("reply", "")) if m.lower() not in evidence]
    if invented:
        reasons.append(f"Numbers/terms not found in evidence: {invented[:3]}")

    if draft.get("reply") and lang.detect(draft["reply"]) != target_lang:
        reasons.append(f"Draft is not in the requester's language ({target_lang})")
    if reasons:
        rules.append("R6")

    if draft.get("unsupported_requests"):
        rules.append("R4"); reasons.append(f"LLM flagged unsupported requests: {draft['unsupported_requests']}")
    return {"rules": rules, "reasons": reasons}


def decide(pre: dict, post: dict | None) -> dict:
    rules = pre["rules"] + (post["rules"] if post else [])
    reasons = pre["reasons"] + (post["reasons"] if post else [])
    status = "ESCALATE" if rules else "AUTO_DRAFT"
    return {"status": status, "rules": sorted(set(rules)), "reasons": reasons}
