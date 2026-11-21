"""Live outage / burst detection (bonus). Owner: teammate 4.

CONTRACT:
    BurstDetector(window=20, sim_threshold=0.6, min_cluster=3)
    .add(ticket_id, text, triage) -> {"outage": bool, "size": int, "members": [ticket_id, ...], "label": str}

TODO(teammate 4): replace the keyword STUB with embedding similarity (reuse retrieval's embedder):
keep the last `window` tickets; if >= min_cluster are mutually similar (>= sim_threshold) -> outage banner.
"""
import re
from collections import deque

_SIGNAL = re.compile(r"\b(vpn|login|log in|sign in|outage|down|ausfall|anmeld\w*|e-?mail|server|network|netzwerk)\b", re.I)


class BurstDetector:
    def __init__(self, window: int = 20, sim_threshold: float = 0.6, min_cluster: int = 3):
        self.recent = deque(maxlen=window)
        self.sim_threshold = sim_threshold
        self.min_cluster = min_cluster

    def add(self, ticket_id: str, text: str, triage: dict) -> dict:
        keys = {m.lower() for m in _SIGNAL.findall(text)}
        self.recent.append((ticket_id, keys))
        best_key, members = "", []
        for key in keys:
            group = [tid for tid, ks in self.recent if key in ks]
            if len(group) > len(members):
                best_key, members = key, group
        return {"outage": len(members) >= self.min_cluster, "size": len(members),
                "members": members, "label": best_key}
