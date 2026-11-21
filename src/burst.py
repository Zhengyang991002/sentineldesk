"""Live outage / burst detection.

Keeps the tickets seen in the last `window_s` seconds (masked text + multilingual embedding) and
raises a major-incident flag when `min_cluster` or more of them describe the same failure:
similar in embedding space (cosine >= sim_threshold to a common center ticket, English and German
tickets match each other) and each one reads like something is broken, not like a question. Repeats of the exact same
text are counted once, so re-analyzing one ticket cannot fake an outage.

CONTRACT:
    BurstDetector(window_s=1800, sim_threshold=0.55, min_cluster=3, embed=None, clock=time.time)
    .add(subject, body) -> status        # records the ticket, then returns status()
    .status() -> {
        "outage": bool, "size": int, "label": str,       # label: the failing system, e.g. "VPN"
        "since": float | None, "window_s": int,          # epoch seconds of the oldest ticket in the cluster
        "members": [{"subject": str, "language": str, "at": float}, ...],   # masked, newest first
    }
Text is masked (src.pii) before it is embedded or kept. State is in memory and per process.
"""
from __future__ import annotations

import hashlib
import threading
import time
from collections import Counter, deque

import numpy as np

from src import pii

# Something is broken / unavailable (en + de). A "how do I export my data" question is not an outage.
import re

_FAILURE = re.compile(
    r"\b(down|outage|offline|unavailable|unreachable|not\s+working|doesn'?t\s+work|isn'?t\s+working|stopped|"
    r"broken|fail(?:s|ed|ing|ure)?|error|errors|cannot|can'?t|unable|timeout|time[ds]?\s+out|5\d\d|"
    r"ausfall|ausgefallen|funktioniert\s+nicht|nicht\s+(?:mehr\s+)?erreichbar|geht\s+nicht|st(?:ö|oe)rung|"
    r"fehler|kann\s+mich\s+nicht|keine\s+verbindung)\b",
    re.I,
)
_SYSTEMS = [
    ("VPN", re.compile(r"\bvpn\b", re.I)),
    ("Login", re.compile(r"\b(log\s?in|sign\s?in|sso|password|anmeld\w*|einlog\w*|passwort)\b", re.I)),
    ("Email", re.compile(r"\be-?mails?\b|\bmail\s?server\b|\boutlook\b", re.I)),
    ("API", re.compile(r"\bapi\b|\b50[0-4]\b", re.I)),
    ("Network", re.compile(r"\b(network|netzwerk|wi-?fi|wlan|internet|dns)\b", re.I)),
    ("Website", re.compile(r"\b(website|webseite|portal|checkout|shop)\b", re.I)),
    ("Server", re.compile(r"\bserver\b|\bdatabase\b|\bdatenbank\b", re.I)),
    ("Payments", re.compile(r"\b(payment|zahlung|payments)\b", re.I)),
]


def _default_embed(texts: list[str]) -> np.ndarray:
    from src import retrieval  # loads the multilingual embedder on first use

    return retrieval.embed(texts)


class BurstDetector:
    def __init__(self, window_s: int = 1800, sim_threshold: float = 0.55, min_cluster: int = 3,
                 max_tickets: int = 100, embed=None, clock=time.time):
        self.window_s = window_s
        self.sim_threshold = sim_threshold
        self.min_cluster = min_cluster
        self._embed = embed or _default_embed
        self._clock = clock
        self._recent: deque = deque(maxlen=max_tickets)  # dicts: key, subject, text, vec, language, at
        self._lock = threading.Lock()

    def add(self, subject: str | None, body: str, language: str = "") -> dict:
        subj, _ = pii.mask((subject or "").strip())
        text, _ = pii.mask(f"{subject or ''}\n{body}".strip())
        key = hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()
        now = self._clock()
        with self._lock:
            self._drop_old(now)
            if not any(t["key"] == key for t in self._recent):
                vec = self._embed([text[:512]])[0]
                self._recent.append({"key": key, "subject": subj or text[:60], "text": text, "vec": vec,
                                     "language": language, "at": now})
            return self._status(now)

    def status(self) -> dict:
        with self._lock:
            now = self._clock()
            self._drop_old(now)
            return self._status(now)

    def _drop_old(self, now: float) -> None:
        while self._recent and now - self._recent[0]["at"] > self.window_s:
            self._recent.popleft()

    def _status(self, now: float) -> dict:
        idle = {"outage": False, "size": 0, "label": "", "since": None, "window_s": self.window_s, "members": []}
        broken = [t for t in self._recent if _FAILURE.search(t["text"])]
        if len(broken) < self.min_cluster:
            return idle
        sims = np.stack([t["vec"] for t in broken])
        sims = sims @ sims.T
        best: list[int] = []
        for i in range(len(broken)):
            group = [j for j in range(len(broken)) if sims[i, j] >= self.sim_threshold]
            if len(group) > len(best):
                best = group
        if len(best) < self.min_cluster:
            return idle
        members = sorted((broken[j] for j in best), key=lambda t: t["at"], reverse=True)
        return {
            "outage": True,
            "size": len(members),
            "label": self._label(members),
            "since": min(t["at"] for t in members),
            "window_s": self.window_s,
            "members": [{"subject": t["subject"], "language": t["language"], "at": t["at"]} for t in members],
        }

    @staticmethod
    def _label(members: list[dict]) -> str:
        counts = Counter(name for t in members for name, rx in _SYSTEMS if rx.search(t["text"]))
        return counts.most_common(1)[0][0] if counts else "system"
