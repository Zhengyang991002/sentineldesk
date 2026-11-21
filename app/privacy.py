"""PII helpers shared by everything that sends data off-machine (Gemini, Cloud Storage, BigQuery)."""
from __future__ import annotations

import re

try:  # guardrail owned by the pipeline team
    from src.pii import _PATTERNS, mask
except Exception:  # pragma: no cover - minimal fallback if src is unavailable
    _EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    _PATTERNS = [("EMAIL", _EMAIL)]

    def mask(text: str):
        text, n = _EMAIL.subn("[EMAIL]", text or "")
        return text, ({"EMAIL": n} if n else {})


# Stable, client-specific identifiers, strongest first. IPs, cards and IBANs are never used to identify clients.
_ID_PRIORITY = ("EMAIL", "ACCOUNT", "PHONE")


def extract_identifier(text: str) -> tuple[str, str] | None:
    """Return (kind, normalized_value) of the best client identifier in `text`, or None.

    The value is only ever used in memory to derive a pseudonymous id; it is never stored.
    """
    patterns = dict(_PATTERNS)
    # The phone pattern is permissive and also matches card numbers, IBANs and IPs: blank those out
    # first so a payment card can never end up being treated as a client identifier.
    without_sensitive = text or ""
    for kind in ("IBAN", "CARD", "IP"):
        if kind in patterns:
            without_sensitive = patterns[kind].sub(" ", without_sensitive)
    for kind in _ID_PRIORITY:
        pattern = patterns.get(kind)
        if pattern is None:
            continue
        m = pattern.search(without_sensitive if kind == "PHONE" else (text or ""))
        if not m:
            continue
        raw = m.group(0)
        # The email pattern also swallows sentence punctuation ("...example.com."), which would give the
        # same person a different id depending on where the address sits in the text.
        value = raw.strip().rstrip(".,;:!?-").lstrip(".,;:!?").lower() if kind == "EMAIL" else re.sub(r"\D", "", raw)
        if value:
            return kind.lower(), value
    return None


__all__ = ["mask", "extract_identifier"]
