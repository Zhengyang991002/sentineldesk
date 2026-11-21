"""Live Triage Console. Owner: teammate 4.   Run:  streamlit run app.py
Minimal working version; polish layout, add demo-ticket buttons and the outage banner.
"""
import pandas as pd
import streamlit as st

from src import pipeline
from src.burst import BurstDetector

st.set_page_config(page_title="SentinelDesk", layout="wide")
st.title("SentinelDesk — Incident Triage Console")

if "burst" not in st.session_state:
    st.session_state.burst = BurstDetector()
    st.session_state.n = 0

subject = st.text_input("Subject (optional)")
body = st.text_area("Body", height=180)

if st.button("Triage", type="primary") and body.strip():
    with st.spinner("Triaging..."):
        out = pipeline.run(subject, body)
    st.session_state.n += 1
    burst = st.session_state.burst.add(f"LIVE-{st.session_state.n}", out["masked_text"], out["triage"])
    if burst["outage"]:
        st.error(f"MAJOR INCIDENT: {burst['size']} recent tickets about '{burst['label']}' ({', '.join(burst['members'])})")

    g = out["gate"]
    if g["status"] == "ESCALATE":
        st.error("Escalate to On-Call Engineer — " + " | ".join(g["reasons"]))
    else:
        st.success("Auto-Draft Ready")

    cols = st.columns(5)
    for col, key in zip(cols, ["type", "queue", "priority"]):
        d = out["triage"][key]
        col.metric(key.capitalize(), d["label"], f"conf {d['confidence']:.2f}", delta_color="off")
    cols[3].metric("Language", out["language"])
    cols[4].metric("Latency", f"{out['latency_ms']['total']:.0f} ms")

    st.subheader("Top historical precedents")
    st.dataframe(pd.DataFrame([{"ticket_id": h["ticket_id"], "similarity": round(h["score"], 3), "lang": h["language"],
                                "queue": h["queue"], "answer": h["answer"][:200]} for h in out["hits"]]),
                 use_container_width=True, hide_index=True)

    st.subheader(f"Draft reply ({out['draft']['source']})")
    st.write(out["draft"]["reply"])
    with st.expander("Debug"):
        st.json({"pii_masked": out["pii"], "latency_ms": out["latency_ms"], "draft_error": out["draft"]["error"]})
