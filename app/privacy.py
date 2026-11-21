"""PII masking shared by everything that sends data off-machine (Gemini, Cloud Storage)."""
from __future__ import annotations

import re

try:  # guardrail owned by the pipeline team
    from src.pii import mask
except Exception:  # pragma: no cover - minimal fallback if src is unavailable
    _EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

    def mask(text: str):
        text, n = _EMAIL.subn("[EMAIL]", text or "")
        return text, ({"EMAIL": n} if n else {})

__all__ = ["mask"]
