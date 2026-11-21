"""Language detection restricted to en/de. Owner: teammate 3."""
import re

from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 0
_DE_HINTS = re.compile(r"\b(und|nicht|ich|wir|bitte|der|die|das|ist|mit|für|unser|können)\b|[äöüß]", re.I)


def detect(text: str) -> str:
    """Return "en" or "de". Falls back to a German-hint heuristic on short/odd text."""
    text = (text or "").strip()
    if not text:
        return "en"
    try:
        for cand in detect_langs(text):
            if cand.lang in ("en", "de"):
                return cand.lang
    except Exception:
        pass
    return "de" if len(_DE_HINTS.findall(text)) >= 2 else "en"
