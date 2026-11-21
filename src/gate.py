"""Escalation gate. Owner: integrator.

Who decides whether a ticket goes to a supervisor (status ESCALATE):
    ML     Similar resolved cases exist (best precedent >= TAU_SIM): the ML model decides. R1 = very high
           severity (high-priority Incident from the classifier, calibrated HPI score, or critical keyword)
           escalates; otherwise Gemini drafts a reply grounded on the precedents.
    AGENT  No similar resolved case (R3): the Gemini agent decides, with the ML signals (signals()) as
           advisory input. It either escalates or answers on its own (acknowledge / ask for details).
    R3     Agent failed or skipped (R5 injection) on a no-precedent ticket: escalate.

The other checks are flags: they never escalate, but they are shown to the operator next to the draft.
    R4  Request for refund / price / legal / contract / data deletion that the precedents do not cover.
    R5  Possible prompt injection (the LLM is not called; the extractive fallback is used instead).
    R6  Draft quality: missing or foreign citations, numbers not in the evidence, wrong language.
"""
import re

from src import config, lang, triage as triage_model

# Strong outage/safety signals (safety net in case the classifier misses a critical incident)
CRITICAL = re.compile(
    r"\b(outage|down for (all|everyone)|data breach|security breach|ransomware|hacked|hospital|patient|"
    r"emr|telemedicine|production (is )?down|ausfall|ausgefallen|totalausfall|datenleck|sicherheitsvorfall|"
    r"krankenhaus|klinik|patienten)\b"
    # "<system> is down/offline", e.g. "Production API down", "server is offline"
    r"|\b(production|prod|api|server|servers|service|services|system|systems|website|site|platform|network|"
    r"database|db|vpn|portal|app|application|checkout|login|email|e-mail)\s+(is\s+|are\s+|has\s+been\s+|"
    r"have\s+been\s+|went\s+|completely\s+|totally\s+)*(down|offline|unreachable|unavailable|not responding|crashed)\b"
    # HTTP 5xx failures
    r"|\b50[0-4]\b[^\n]{0,20}\berrors?\b|\b(bad gateway|service unavailable|gateway timeout)\b"
    # everyone affected
    r"|\b(nobody|no one)\s+(can|could|is able)\b|\bcustomers cannot\b|\bniemand kann\b"
    # German "<system> ist down/offline/nicht erreichbar/ausgefallen", "Störung"
    r"|\b(server|system|dienst|website|webseite|netzwerk|produktion|plattform|datenbank)\s+(ist\s+|sind\s+)?"
    r"(komplett\s+|völlig\s+)?(down|offline|nicht erreichbar|ausgefallen|abgestürzt)\b|\bstörung\b", re.I)
# Keyword list checked on the KB val split: the added outage patterns match ~0.5% of val tickets.

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


def _severity(text: str, triage: dict) -> str | None:
    """Reason string if the ticket is very high severity, else None."""
    t, p = triage["type"], triage["priority"]
    if p["label"] == "high" and t["label"] == "Incident":
        return "Very high severity: high-priority Incident"
    hpi_th = triage_model.hpi_threshold()  # None when only the uncalibrated baseline is loaded
    hpi = triage_model.hpi_score(triage)
    if hpi_th is not None and hpi >= hpi_th:
        return f"Very high severity: possible high-priority Incident (score {hpi:.2f} >= {hpi_th:.2f})"
    m = CRITICAL.search(text)
    if m:
        return f"Very high severity: critical keyword '{m.group(0)}'"
    return None


def best_precedent(hits: list[dict]) -> dict | None:
    """Most similar retrieved ticket that has a resolution, or None."""
    resolved = [h for h in hits if (h.get("answer") or "").strip()]
    return max(resolved, key=lambda h: h["score"]) if resolved else None


def pre_check(text: str, triage: dict, hits: list[dict]) -> dict:
    rules, reasons, flags, flag_reasons = [], [], [], []

    severity = _severity(text, triage)
    if severity:
        rules.append("R1"); reasons.append(f"{severity}: hand over to a supervisor")

    best = best_precedent(hits)
    if best is None or best["score"] < config.TAU_SIM:
        top = best["score"] if best else 0.0
        rules.append("R3"); reasons.append(
            f"No similar resolved case (best similarity {top:.2f} < {config.TAU_SIM}): hand over to a supervisor")

    evidence = " ".join(h["answer"] for h in hits).lower()
    for topic, pattern in UNSUPPORTED.items():
        if re.search(pattern, text, re.I) and not re.search(pattern, evidence, re.I):
            flags.append("R4"); flag_reasons.append(f"Asks for {topic}, not covered by any retrieved resolution")

    if INJECTION.search(text):
        flags.append("R5"); flag_reasons.append("Possible prompt injection: drafted without the LLM")

    return {"rules": rules, "reasons": reasons, "flags": flags, "flag_reasons": flag_reasons}


def post_check(draft: dict, hits: list[dict], target_lang: str) -> dict:
    """Draft quality checks. Flags only: they never escalate."""
    reasons = []
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
    flags = ["R6"] if reasons else []

    if draft.get("unsupported_requests"):
        flags.append("R4"); reasons.append(f"LLM flagged unsupported requests: {draft['unsupported_requests']}")
    return {"flags": flags, "flag_reasons": reasons}


def signals(text: str, triage: dict, hits: list[dict]) -> str:
    """ML evidence handed to the agent as advisory input (one line per signal)."""
    t, p = triage["type"], triage["priority"]
    hpi, hpi_th = triage_model.hpi_score(triage), triage_model.hpi_threshold()
    best = best_precedent(hits)
    kw = CRITICAL.search(text)
    return "\n".join([
        f"ML signals: type={t['label']} ({t['confidence']:.2f}), priority={p['label']} ({p['confidence']:.2f})",
        f"Severity score P(Incident)*P(high)={hpi:.2f}" + (f" (ML threshold {hpi_th:.2f})" if hpi_th else ""),
        f"Critical keyword: '{kw.group(0)}'" if kw else "Critical keyword: none",
        f"Best precedent similarity: {best['score']:.2f}" if best else "Best precedent similarity: none",
    ])


def decide(pre: dict, post: dict | None, decided_by: str = "ml", agent: dict | None = None,
           agent_error: str | None = None) -> dict:
    """Final decision.
        decided_by="ml"     similar resolved cases exist: ESCALATE iff R1 (very high severity).
        decided_by="agent"  no similar resolved case: the Gemini agent's escalate flag decides;
                            an R1 the agent overruled stays visible as a flag.
        decided_by="rule"   no similar resolved case and the agent failed or was skipped: ESCALATE.
    """
    flags = pre["flags"] + (post["flags"] if post else [])
    flag_reasons = pre["flag_reasons"] + (post["flag_reasons"] if post else [])
    r1_reasons = [r for code, r in zip(pre["rules"], pre["reasons"]) if code == "R1"]
    if decided_by == "agent" and agent is not None:
        escalate = bool(agent["escalate"])
        reason = agent.get("escalation_reason") or (
            "escalate" if escalate else "answered directly, no severe impact")
        rules = ["AGENT"] if escalate else []
        reasons = [f"No similar resolved case; agent decided to escalate: {reason}"] if escalate else []
        if r1_reasons and not escalate:  # ML disagreed: keep it visible to the operator
            flags = flags + ["R1"]
            flag_reasons = flag_reasons + [f"ML severity check disagreed: {r1_reasons[0]}"]
        if not escalate:
            flag_reasons = [f"No similar resolved case; agent answered: {reason}"] + flag_reasons
    elif decided_by == "rule":
        rules, reasons, escalate = list(pre["rules"]), list(pre["reasons"]), True
        if agent_error:
            reasons = reasons + [f"Agent unavailable ({agent_error[:120]})"]
    else:  # "ml"
        rules, reasons = ["R1"] if r1_reasons else [], r1_reasons
        escalate = bool(rules)
    return {"status": "ESCALATE" if escalate else "AUTO_DRAFT", "decided_by": decided_by,
            "rules": sorted(set(rules)), "reasons": reasons,
            "flags": sorted(set(flags)), "flag_reasons": flag_reasons}
