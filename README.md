# SentinelDesk

**Multilingual (EN/DE) incident triage, escalation gate and precedent-grounded reply copilot.**

When a raw ticket (optional subject + body) arrives, SentinelDesk:

1. **Classifies** its `type`, `queue` and `priority`, each with a confidence score.
2. **Gates** it: auto-draft a reply, or escalate to a human with explicit reasons.
3. **Retrieves** the top-5 most similar resolved tickets from the historical knowledge base (cross-lingual).
4. **Drafts** a reply in the requester's language, grounded only in those precedents and citing their `ticket_id`s.

## Architecture

```
ticket (subject may be empty + body)
  -> lang.detect        en / de, detected from raw text (the dataset's language column is never used at inference)
  -> pii.mask           emails, phones, IPs, IBANs, card and account numbers masked before any external API call
  -> triage.predict     type / queue / priority + confidence
  -> retrieval.search   top-5 precedents: multilingual MiniLM embeddings + FAISS (cosine), KB fit split only
  -> gate.pre_check     R1-R5 (below)
  -> generate.draft     Claude, grounded in the retrieved answers; extractive template fallback if the API fails
  -> gate.post_check    R6: citations, numbers and language verified against the evidence
  -> AUTO_DRAFT | ESCALATE + reasons + per-stage latency
```

| Component | Implementation |
|---|---|
| Triage | TF-IDF + Logistic Regression, one model per label (`src/triage.py`) |
| Retrieval | `fastembed` `paraphrase-multilingual-MiniLM-L12-v2` (384-d, L2-normalised) + `faiss.IndexFlatIP`; TF-IDF fallback if no embeddings (`src/retrieval.py`) |
| Generation | Claude API (`claude-opus-5-5`) with structured output (`src/generate.py`) |
| Gate | Deterministic rules + thresholds tuned on a validation split (`src/gate.py`) |
| UI | Streamlit (`app.py`) |

## Escalation gate

A ticket is escalated if **any** rule fires; every reason is shown to the operator.

| Rule | Fires when |
|---|---|
| **R1** Critical incident | predicted `priority=high` and `type=Incident`, **or** a critical keyword (outage, data breach, hospital/EMR, Ausfall, Datenleck, ...) as a safety net |
| **R2** Low confidence | type or priority confidence < `TAU_CONF` |
| **R3** No precedent | top-1 retrieval similarity < `TAU_SIM` (0.55); no draft is generated, a safe holding reply is used |
| **R4** Unsupported request | asks for refunds, pricing, legal/SLA guarantees, contract changes or data deletion that no retrieved resolution covers (keywords EN+DE, plus the LLM's own `unsupported_requests`) |
| **R5** Adversarial input | prompt-injection patterns ("ignore previous instructions", ...); no draft is generated |
| **R6** Draft verification failed | the draft cites tickets that were not retrieved, contains numbers/terms absent from the evidence, or is in the wrong language |

### Threshold tuning (validation split only)

`TAU_SIM` was tuned with `python -m scripts.tune_sim` on 400 validation tickets (not in the index):

| Query set | Top-1 cosine similarity |
|---|---|
| Validation tickets | p1 = 0.749, p5 = 0.814, median = 0.938 |
| Out-of-scope / adversarial queries (recipes, weather, poems, injection) | 0.24 – 0.39 |
| Short hand-written in-scope queries | ~0.65 – 0.72 |

`TAU_SIM = 0.55` separates the two groups with margin on both sides. `TAU_CONF` is tuned the same way on the validation split.

## Data and leakage controls

Dataset: [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets), file `aa_dataset-tickets-multi-lang-5-2-50-version.csv` (28,587 tickets, EN/DE; CC-BY-NC-4.0).

The official split is applied exactly as specified: shuffle with `random_state=42`, `TKT-xxxxx` ids, first 80% = knowledge base, last 20% = holdout test.

| Split | Rows | Used for |
|---|---|---|
| KB `fit` | 20,582 | training classifiers, retrieval index |
| KB `val` | 2,287 | threshold tuning only |
| Test | 5,718 | final metrics only |

- The test split's `answer` column is **dropped in `prepare_data.py` and never written to disk**.
- Test inputs (`ticket_id, subject, body`) and labels are stored in separate files; labels are read only when scoring.
- The index contains only KB `fit` tickets (verified: 0 overlap with val and test ids).
- Thresholds are tuned on `val`, never on test.

## Results

Run `python -m scripts.evaluate`; results are written to `reports/metrics.json`.

| Metric | Value |
|---|---|
| Type Macro-F1 | TBD |
| Queue Macro-F1 | TBD |
| Priority Macro-F1 | TBD |
| High-priority Incident recall (classifier) | TBD |
| High-priority Incident recall (gate escalates) | TBD |
| Escalation rate | TBD |
| Latency without LLM (warm, p50) | ~30 ms |
| Latency with LLM (p50 / p95) | TBD |

Gate behaviour on hand-written demo tickets: `python -m scripts.test_gate` (8/8 pass: refund+SLA → R4, injection → R5, out-of-scope EN/DE → R3, hospital VPN outage → R1, empty subject and normal tickets → no false R3/R4/R5).

## Setup

```bash
git clone git@github.com:Zhengyang991002/sentineldesk.git && cd sentineldesk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # optional: without it, replies use the extractive fallback
python -m scripts.prepare_data      # download CSV + official split
python -m src.triage                # train classifiers -> artifacts/
streamlit run app.py                # operator console
```

Prebuilt KB embeddings are committed in `artifacts/`; to rebuild them run `python -m src.retrieval` (resumable, ~10–30 min on a laptop CPU).

| Command | Purpose |
|---|---|
| `python -m src.pipeline` | end-to-end smoke test |
| `python -m src.retrieval --query "..."` | inspect retrieved precedents |
| `python -m scripts.test_gate` | gate rules on demo tickets |
| `python -m scripts.tune_sim` | tune `TAU_SIM` on val |
| `python -m scripts.evaluate` | holdout metrics |

## Repository layout

```
app.py                  Streamlit operator console
src/config.py           paths, thresholds, model id
src/data.py             loading, official split, subject+body joining (handles null subjects)
src/lang.py             en/de detection
src/pii.py              PII masking
src/triage.py           classifiers
src/retrieval.py        embeddings + FAISS search
src/gate.py             escalation rules R1-R6
src/generate.py         grounded reply generation + fallback
src/burst.py            outage burst detection
src/pipeline.py         orchestration, latency, warmup
scripts/                prepare_data, evaluate, tune_sim, test_gate
artifacts/              prebuilt embeddings (KB fit split only)
```

## Team

| Owner | Area |
|---|---|
| Integrator | data split, gate, pipeline, README |
| Teammate 1 | triage, evaluation |
| Teammate 2 (Rory) | retrieval, embeddings |
| Teammate 3 | generation, PII, language detection |
| Teammate 4 | UI, burst detection |
