"""PII guardrail: mask before any text leaves the machine (LLM API). Owner: teammate 3."""
import re

_PATTERNS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b")),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("PHONE", re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d\b")),
    ("ACCOUNT", re.compile(r"\b(?:account|acct|konto|kundennummer|customer)\s*(?:no\.?|number|nr\.?|#)?\s*[:#]?\s*\d{5,}\b", re.I)),
]


def mask(text: str) -> tuple[str, dict]:
    """Return (masked_text, {kind: count})."""
    counts = {}
    for kind, pattern in _PATTERNS:
        text, n = pattern.subn(f"[{kind}]", text or "")
        if n:
            counts[kind] = n
    return text, counts
