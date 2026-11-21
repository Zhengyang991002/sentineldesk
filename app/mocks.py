"""Mock pipeline stages, used while PIPELINE_MODE=mock (the default).

Each function stands in for one real stage: triage -> src.triage, retrieve -> src.retrieval,
gate -> src.gate, draft -> src.generate. Output is deterministic and keyword-routed so the four
sample tickets in the console cover every UI state: English/German, escalated/auto-draft,
out-of-scope. Delete this file once nothing needs the mock mode.
"""
from __future__ import annotations

import re

_DE_HINTS = re.compile(
    r"\b(rechnung|konto|bitte|ich|wir|nicht|und|der|die|das|zahlung|abgebucht|doppelt|danke|hallo|sehr geehrte)\b"
    r"|[äöüß]",
    re.IGNORECASE,
)
_OUTAGE = re.compile(r"\b(outage|down|unreachable|500|502|503|crash|production|offline|not responding)\b", re.I)
_BILLING = re.compile(r"\b(rechnung|abgebucht|zahlung|invoice|billing|charged|refund)\b", re.I)
_SUPPORT = re.compile(r"\b(password|reset|export|csv|account|login|how (do|can) i|feature)\b", re.I)


def _case(text: str) -> str:
    t = text or ""
    if _DE_HINTS.search(t) and _BILLING.search(t):
        return "de_billing"
    if _OUTAGE.search(t):
        return "en_outage"
    if _SUPPORT.search(t):
        return "en_request"
    return "out_of_scope"


def _lang(text: str) -> str:
    return "de" if len(_DE_HINTS.findall(text or "")) >= 2 else "en"


_TRIAGE = {
    "en_outage": {
        "type": {"Incident": 0.91, "Problem": 0.06, "Request": 0.02, "Change": 0.01},
        "queue": {"Technical Support": 0.84, "IT Support": 0.11, "Billing and Payments": 0.03, "General Inquiry": 0.02},
        "priority": {"high": 0.93, "medium": 0.06, "low": 0.01},
    },
    "de_billing": {
        "type": {"Request": 0.58, "Incident": 0.27, "Problem": 0.1, "Change": 0.05},
        "queue": {"Billing and Payments": 0.88, "General Inquiry": 0.07, "Technical Support": 0.05},
        "priority": {"medium": 0.71, "low": 0.2, "high": 0.09},
    },
    "en_request": {
        "type": {"Request": 0.86, "Problem": 0.08, "Incident": 0.04, "Change": 0.02},
        "queue": {"Customer Service": 0.69, "General Inquiry": 0.2, "Technical Support": 0.11},
        "priority": {"low": 0.74, "medium": 0.22, "high": 0.04},
    },
    "out_of_scope": {
        "type": {"Request": 0.38, "Problem": 0.31, "Incident": 0.19, "Change": 0.12},
        "queue": {"General Inquiry": 0.34, "Customer Service": 0.33, "Sales and Pre-Sales": 0.33},
        "priority": {"low": 0.41, "medium": 0.38, "high": 0.21},
    },
}

_PRECEDENTS = {
    "en_outage": [
        ("TKT-01482", 0.87, "We identified a failing load balancer node in the EU region and rerouted traffic. Service was restored within 25 minutes. Please confirm the API is responding normally on your side and share any remaining request IDs that returned 5xx. A full post-incident report, including the timeline and the follow-up actions on health-check configuration, will be sent to your technical contact within two business days."),
        ("TKT-03917", 0.81, "The outage was caused by an expired TLS certificate on the gateway. We rotated the certificate and added expiry monitoring. No data was lost."),
        ("TKT-00255", 0.74, "Thank you for reporting the downtime. Our on-call team found a database connection pool exhaustion after a deploy and rolled it back."),
        ("TKT-02031", 0.66, "Intermittent 502 errors were traced to a misconfigured health check. We adjusted the threshold and are monitoring."),
        ("TKT-04420", 0.61, "We are investigating the degraded performance. Please try clearing your cache and re-authenticating."),
    ],
    "de_billing": [
        ("TKT-02210", 0.89, "Vielen Dank für Ihre Nachricht. Die doppelte Abbuchung war auf einen Fehler bei der Zahlungsabwicklung zurückzuführen. Wir haben den Betrag erstattet; die Gutschrift erscheint innerhalb von 5 bis 7 Werktagen auf Ihrem Konto."),
        ("TKT-00871", 0.82, "Wir haben Ihre Rechnung geprüft und eine korrigierte Version erstellt. Die zu viel berechnete Gebühr wurde storniert."),
        ("TKT-03304", 0.73, "Thank you for contacting us about the duplicate charge. The second payment was reversed and a confirmation email has been sent."),
        ("TKT-01199", 0.65, "Bitte senden Sie uns die Rechnungsnummer, damit wir die Abbuchung nachvollziehen können."),
        ("TKT-04871", 0.58, "Your invoice has been re-issued with the correct VAT rate."),
    ],
    "en_request": [
        ("TKT-00634", 0.83, "You can export your data from Settings > Account > Export. Choose CSV or JSON and we will email you a download link within a few minutes. The link stays valid for 24 hours."),
        ("TKT-02755", 0.77, "Thanks for the feature request. Bulk export is available on the Pro plan; for other plans, a CSV export of the current view can be downloaded from the table menu."),
        ("TKT-01006", 0.69, "To reset your password, use the 'Forgot password' link on the sign-in page. If you no longer have access to your email, contact us with proof of ownership."),
        ("TKT-03618", 0.62, "We have added your request to our product backlog and will notify you once it ships."),
        ("TKT-00912", 0.55, "Please see our documentation on data portability for the full list of supported formats."),
    ],
    "out_of_scope": [
        ("TKT-04012", 0.31, "Thank you for your interest. Unfortunately we do not provide legal advice. Please consult a qualified professional."),
        ("TKT-01733", 0.27, "This request is outside the scope of our support. We recommend contacting the vendor directly."),
        ("TKT-03029", 0.24, "We could not find any related information in our records."),
        ("TKT-00098", 0.22, "Your message has been forwarded to the relevant department."),
        ("TKT-02566", 0.19, "Please provide more details so that we can assist you."),
    ],
}

_DRAFTS = {
    "de_billing": (
        "Guten Tag,\n\nvielen Dank für Ihre Nachricht. Wir haben die doppelte Abbuchung geprüft: Sie ist auf einen Fehler bei der Zahlungsabwicklung zurückzuführen. Den zu viel abgebuchten Betrag erstatten wir Ihnen; die Gutschrift erscheint innerhalb von 5 bis 7 Werktagen auf Ihrem Konto.\n\nBitte senden Sie uns bei Rückfragen Ihre Rechnungsnummer.\n\nMit freundlichen Grüßen\nIhr Support-Team",
        ["TKT-02210", "TKT-00871"],
    ),
    "en_request": (
        "Hello,\n\nthanks for getting in touch. You can export your data under Settings > Account > Export, choosing CSV or JSON. We will email you a download link within a few minutes, valid for 24 hours. Bulk export is available on the Pro plan.\n\nBest regards,\nSupport Team",
        ["TKT-00634", "TKT-02755"],
    ),
    "en_outage": (
        "Hello,\n\nthank you for reporting this. We are investigating the outage and will update you shortly.\n\nBest regards,\nSupport Team",
        ["TKT-01482"],
    ),
    "out_of_scope": (
        "Hello,\n\nthank you for your message. We were unable to match it to our support topics.\n\nBest regards,\nSupport Team",
        [],
    ),
}


def triage(subject: str | None, body: str) -> dict:
    text = f"{subject or ''} {body}".strip()
    out = {k: dict(v) for k, v in _TRIAGE[_case(text)].items()}
    out["language"] = _lang(text)
    return out


def retrieve(text: str, k: int = 5) -> list[dict]:
    rows = _PRECEDENTS[_case(text)][:k]
    return [{"ticket_id": tid, "score": score, "answer": ans} for tid, score, ans in rows]


def gate(triage_out: dict, retrieved: list[dict]) -> dict:
    prio = max(triage_out["priority"], key=triage_out["priority"].get)
    top_score = max((r["score"] for r in retrieved), default=0.0)
    if prio == "high":
        return {"escalate": True, "reason": "High-priority incident: route to on-call engineer for human handling."}
    if top_score < 0.4:
        return {
            "escalate": True,
            "reason": f"Out of scope: best precedent similarity {top_score:.2f} is below the 0.40 threshold.",
        }
    return {"escalate": False, "reason": f"Confident match: top precedent similarity {top_score:.2f}, priority {prio}."}


def draft(text: str, language: str, retrieved: list[dict]) -> dict:
    reply, cited = _DRAFTS[_case(text)]
    present = {r["ticket_id"] for r in retrieved}
    return {"reply": reply, "cited_ids": [c for c in cited if c in present]}
