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

# --- Heuristics for what the patterns above cannot see: bare long numbers, street addresses, names. ---
# This is not a real NER. Names are only caught after a greeting / title / "my name is" cue, or in a
# sign-off, in English and German. A name in the middle of a sentence still passes.
_CAP = r"[A-ZÄÖÜ][\wÄÖÜäöüß'-]+"

# Standalone digit runs of 7+ (account, customer, contract numbers) that no keyword pattern caught.
_BARE_NUMBER = re.compile(r"(?<![\w.-])\d{7,}(?![\w-])")

_ADDRESS = [
    # 123 Main Street / 5 Park Avenue
    re.compile(rf"\b\d{{1,5}}\s+{_CAP}(?:\s+{_CAP})?\s+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Way|Court|Square)\b\.?"),
    # Main Street 5 / Marktplatz 3
    re.compile(rf"\b{_CAP}(?:\s+{_CAP})?\s+(?:Street|Avenue|Road|Lane|Drive|Boulevard|Platz|Allee|Weg|Gasse)\s*\d{{1,5}}[a-z]?\b"),
    # Hauptstraße 12 / Musterstr. 5a
    re.compile(r"\b[A-ZÄÖÜ][a-zäöüß-]+(?:straße|strasse|str\.|weg|allee|platz|gasse|damm|ring|ufer)\s*\d{1,4}[a-z]?\b", re.I),
    # Calle Mayor 5 / Rue de Rivoli 10
    re.compile(rf"\b(?:Calle|Avenida|Rue|Via|Viale|Carrer)\s+(?:de\s+|la\s+|del\s+)?{_CAP}(?:\s+{_CAP})?\s*,?\s*\d{{1,4}}\b"),
]
# German postcode + city ("10115 Berlin"); common non-places are left alone.
_POSTCODE_CITY = re.compile(rf"\b\d{{5}}\s+({_CAP})\b")
_NOT_A_PLACE = {"Euro", "Eur", "Dollar", "Cent", "Stück", "Tage", "Mal", "Jahre", "Uhr"}

_NAME_STOP = {"Team", "Support", "Sir", "Madam", "All", "There", "Everyone", "Customer", "Service", "Sales",
              "Billing", "Helpdesk", "Desk", "Admin", "Technical", "Hallo", "Hello", "Hi", "Dear", "Thanks",
              "Thank", "Please", "Regards", "Kunde", "Kundendienst", "Zusammen", "Leute"}
_CUES = (r"Hi|Hello|Hey|Dear|Hallo|Liebe[rn]?|Guten\s+(?:Tag|Morgen|Abend)|Mr\.?|Mrs\.?|Ms\.?|Miss|Mx\.?|"
         r"Herr|Frau|Dr\.?|Prof\.?|Sehr\s+geehrte[rn]?(?:\s+(?:Herr|Frau))?|my\s+name\s+is|this\s+is|"
         r"ich\s+hei(?:ß|ss)e|mein\s+Name\s+ist|name:?")
_NAME_AFTER_CUE = re.compile(rf"\b((?i:{_CUES}))(\s+)({_CAP}(?:\s+{_CAP}){{0,2}})")
_SIGNOFF = re.compile(
    r"(?im)^((?:best|kind|warm|many|kindest)?\s*(?:regards|thanks|thank\s+you|cheers|sincerely|"
    r"mit\s+freundlichen\s+gr(?:ü|ue)ßen|viele\s+gr(?:ü|ue)ßen|beste\s+gr(?:ü|ue)ßen|freundliche\s+gr(?:ü|ue)ßen|gr(?:ü|ue)ße)"
    r"\s*,?\s*\n\s*)(" + _CAP + r"(?:[ \t]+" + _CAP + r"){0,2})[ \t]*$"
)


def _mask_names(text: str) -> tuple[str, int]:
    n = 0

    def cue(m):
        nonlocal n
        words = m.group(3).split()
        kept = []
        while words and words[0] in _NAME_STOP:  # "Hi Team" is not a person
            kept.append(words.pop(0))
        if not words:
            return m.group(0)
        n += 1
        return m.group(1) + m.group(2) + " ".join(kept + ["[NAME]"])

    text = _NAME_AFTER_CUE.sub(cue, text)

    def signoff(m):
        nonlocal n
        if m.group(2).split()[0] in _NAME_STOP:
            return m.group(0)
        n += 1
        return m.group(1) + "[NAME]"

    return _SIGNOFF.sub(signoff, text), n


def mask(text: str) -> tuple[str, dict]:
    """Return (masked_text, {kind: count})."""
    counts = {}
    text = text or ""
    for kind, pattern in _PATTERNS:
        text, n = pattern.subn(f"[{kind}]", text)
        if n:
            counts[kind] = n
    text, n = _BARE_NUMBER.subn("[NUMBER]", text)
    if n:
        counts["NUMBER"] = n
    addr = 0
    for pattern in _ADDRESS:
        text, k = pattern.subn("[ADDRESS]", text)
        addr += k
    text, k = _POSTCODE_CITY.subn(lambda m: m.group(0) if m.group(1) in _NOT_A_PLACE else "[ADDRESS]", text)
    addr += k
    if addr:
        counts["ADDRESS"] = addr
    text, n = _mask_names(text)
    if n:
        counts["NAME"] = n
    return text, counts
