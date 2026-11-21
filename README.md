# SentinelDesk

**Multilingual (EN/DE) incident triage, escalation gate and precedent-grounded reply copilot.**

When a raw ticket (optional subject + body) arrives, SentinelDesk:

1. **Classifies** its `type`, `queue` and `priority`, each with a confidence score.
2. **Gates** it: auto-draft a reply, or escalate to a human with explicit reasons.
3. **Retrieves** the top-5 most similar resolved tickets from the historical knowledge base (cross-lingual).
4. **Drafts** a reply in the requester's language, grounded only in those precedents and citing their `ticket_id`s.

## Architecture

```
Browser (React, web/)  ──►  FastAPI (app/main.py)  ──►  app/pipeline.py  ──►  src/pipeline.py
                                                                                 │
ticket (subject may be empty + body)                                             ▼
  -> lang.detect        en / de, detected from raw text (the dataset's language column is never used at inference)
  -> pii.mask           emails, phones, IPs, IBANs, card and account numbers masked before any external API call
  -> triage.predict     type / queue / priority + confidence
  -> retrieval.search   top-5 precedents: multilingual MiniLM embeddings + FAISS (cosine), KB fit split only
  -> gate.pre_check     R1-R5 (below)
  -> generate.draft     Gemini on Vertex AI, grounded in the retrieved answers; extractive template fallback on any error
  -> gate.post_check    R6: citations, numbers and language verified against the evidence
  -> AUTO_DRAFT | ESCALATE + reasons + per-stage latency
```

More detail (API contract, frontend map): [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

| Component | Implementation |
|---|---|
| Triage | Shared TF-IDF (word 1-2gram + char 3-5gram) + Logistic Regression per label, `C` picked on val (`src/triage.py`) |
| Retrieval | `fastembed` `paraphrase-multilingual-MiniLM-L12-v2` (384-d, L2-normalised) + `faiss.IndexFlatIP`; TF-IDF fallback if no embeddings (`src/retrieval.py`) |
| Generation | Gemini (Vertex AI, `google-genai`) with JSON output (`src/generate.py`) |
| Gate | Deterministic rules + thresholds tuned on a validation split (`src/gate.py`) |
| API | FastAPI: `/triage`, `/chat`, `/tickets`, `/health` (`app/`) |
| UI | React + Vite operator console (`web/`), Gemini chat assistant |
| Storage | Optional: analysed tickets (PII-masked) saved to Google Cloud Storage |

## Escalation gate

A ticket is escalated if **any** rule fires; every reason is shown to the operator.

| Rule | Fires when |
|---|---|
| **R1** Critical incident | predicted `priority=high` and `type=Incident`, **or** a critical keyword (outage, data breach, hospital/EMR, Ausfall, Datenleck, ...) as a safety net |
| **R2** Low confidence | type or priority confidence < `TAU_CONF` (0.55) |
| **R3** No precedent | top-1 retrieval similarity < `TAU_SIM` (0.50); no draft is generated, a safe holding reply is used |
| **R4** Unsupported request | asks for refunds, pricing, legal/SLA guarantees, contract changes or data deletion that no retrieved resolution covers (keywords EN+DE, plus the LLM's own `unsupported_requests`) |
| **R5** Adversarial input | prompt-injection patterns ("ignore previous instructions", ...); no draft is generated |
| **R6** Draft verification failed | the draft cites tickets that were not retrieved, contains numbers/terms absent from the evidence, or is in the wrong language |

### Threshold tuning (validation split only)

`TAU_SIM` was tuned with `python -m scripts.tune_sim` on 400 validation tickets (not in the index):

| Query set | Top-1 cosine similarity |
|---|---|
| Validation tickets | p1 = 0.749, p5 = 0.814, median = 0.938 |
| Out-of-scope / adversarial queries (recipes, weather, poems, injection) | 0.24 – 0.39 |
| Short hand-written in-scope queries | ~0.58 – 0.72 |

`TAU_SIM = 0.50` separates the groups and leaves margin for the short one-line tickets judges type live. `TAU_CONF` is tuned the same way on the validation split.

## Data and leakage controls

Dataset: [Tobi-Bueck/customer-support-tickets](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets), file `aa_dataset-tickets-multi-lang-5-2-50-version.csv` only (28,587 tickets, EN/DE; CC-BY-NC-4.0).

Dataset decision: the problem statement names this file as the recommended one, so the official seed-42 split is applied to it as-is, with no filtering, dedup or relabelling. We do not use the quick-start's whole-repo load (61,765 rows): it concatenates several overlapping CSVs with different label schemes, leaving ~10.6k KB rows without `type` or `answer` and ~2.6k test texts duplicated in the KB.

The official split is applied exactly as specified: shuffle with `random_state=42`, `TKT-xxxxx` ids by position, first 80% = knowledge base, last 20% = holdout test.

| Split | Rows | Used for |
|---|---|---|
| KB `fit` | 20,582 | training classifiers, retrieval index |
| KB `val` | 2,287 | model selection and threshold tuning only |
| Test | 5,718 | final metrics only |

- The test split's `answer` column is **dropped in `prepare_data.py` and never written to disk**.
- Test inputs (`ticket_id, subject, body`) and labels are stored in separate files; `test_labels.parquet` is read only by `scripts/evaluate.py`, to score predictions already made from `test_inputs`.
- The index contains only KB `fit` tickets (verified: 0 overlap with val and test ids).
- Thresholds and classifier `C` are chosen on `val`, never on test.

## Results

Validation (KB `val`, 2,287 tickets), from `python -m src.triage` → `reports/triage_val.md`:

| Label | Val Macro-F1 | Val accuracy |
|---|---|---|
| type | 0.877 | 0.867 |
| queue | 0.611 | 0.617 |
| priority | 0.622 | 0.635 |

Holdout test (5,718 unseen tickets, `python -m scripts.evaluate` → `reports/metrics.json`):

| Metric | Value |
|---|---|
| Type Macro-F1 / accuracy | **0.883** / 0.873 |
| Queue Macro-F1 / accuracy | **0.607** / 0.608 |
| Priority Macro-F1 / accuracy | **0.640** / 0.653 |
| High-priority Incident recall, classifier alone (n = 995) | 0.687 |
| High-priority Incident recall, **gate escalates** (1,000-ticket sample) | **0.790** |
| Escalation rate (pre-generation rules R1–R5, same sample) | 46.3% |
| Triage latency | 3.8 ms / ticket |
| Retrieval + gate latency (p50 / p95) | 49.5 / 76.2 ms |
| Latency with LLM (p50 / p95) | TBD |

Reading the numbers: queue and priority labels are noisy in this dataset (e.g. marketing complaints labelled "IT Support / Incident / high"), which caps those scores. The gate is tuned for safety rather than coverage: it raises recall on true high-priority incidents from 0.69 (classifier) to 0.79, at the cost of escalating about half of all tickets, since every predicted high-priority Incident is paged (R1).

### `TAU_CONF` tuning (validation split, `python -m scripts.tune_conf`)

R2 fires when type **or** priority confidence is below `TAU_CONF`. "Accuracy" = type and priority both correct.

| `TAU_CONF` | Escalated by R2 | Accuracy kept | Accuracy escalated | HP-Incident caught |
|---|---|---|---|---|
| 0.45 | 3.2% | 0.580 | 0.329 | 0.713 |
| 0.50 | 7.5% | 0.594 | 0.302 | 0.728 |
| **0.55** | **16.9%** | **0.624** | **0.318** | **0.783** |
| 0.60 | 25.9% | 0.642 | 0.372 | 0.828 |
| 0.70 | 43.3% | 0.695 | 0.410 | 0.890 |

At 0.55, the tickets R2 sends to a human are about half as accurate as the ones it keeps (0.32 vs 0.62), and high-priority-incident coverage rises from 0.70 to 0.78 while escalating 17%.

Gate behaviour on hand-written demo tickets: `python -m scripts.test_gate` (8/8 pass: refund+SLA → R4, injection → R5, out-of-scope EN/DE → R3, hospital VPN outage → R1, empty subject and normal tickets → no false R3/R4/R5).

## Setup

```bash
git clone git@github.com:Zhengyang991002/sentineldesk.git && cd sentineldesk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.prepare_data      # download CSV + official split
python -m src.triage                # train classifiers -> artifacts/triage.joblib
cp .env.example .env                # set GOOGLE_CLOUD_PROJECT (or VERTEX_API_KEY), PIPELINE_MODE=real
```

Prebuilt KB embeddings are committed in `artifacts/`; to rebuild them run `python -m src.retrieval` (resumable, ~10–30 min on a laptop CPU).

## Run the demo

Backend (repo root):

```bash
uvicorn app.main:app --port 8000
```

Frontend (second terminal):

```bash
cd web && npm install && npm run dev
```

Open http://localhost:5173. `GET http://localhost:8000/health` shows the active pipeline mode and whether Gemini and Storage are configured.

`PIPELINE_MODE` selects what runs behind `POST /triage`: `real` (the `src/` pipeline above, used for the demo), `auto` (real, falls back to the mock if models are missing), or `mock` (`app/mocks.py`, for UI development only).

| Command | Purpose |
|---|---|
| `python -m src.pipeline` | end-to-end smoke test in the terminal |
| `python -m src.retrieval --query "..."` | inspect retrieved precedents |
| `python -m scripts.test_gate` | gate rules on demo tickets |
| `python -m scripts.tune_sim` | tune `TAU_SIM` on val |
| `python -m scripts.evaluate` | holdout metrics |

## Gemini on Vertex AI

Both reply drafting (`src/generate.py`) and the floating chat (`POST /chat`, `app/chat.py`) call Gemini through Vertex AI, billed to your Google Cloud project. Ticket text is masked with `src/pii.py` before it is sent. No key is stored in code.

```bash
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com --project YOUR_PROJECT_ID
# .env: GOOGLE_CLOUD_PROJECT=..., GOOGLE_CLOUD_LOCATION=us-central1, GEMINI_MODEL=gemini-3-flash-preview
```

Alternatively set `VERTEX_API_KEY` in `.env` (Vertex AI express mode); it takes precedence. Without credentials, drafting falls back to the extractive template and the chat to a local rule-based reply, so the demo never crashes.

## Storing console tickets in Cloud Storage

Optional, enabled by setting `GCS_BUCKET`. Every analysed ticket is saved as JSON after the response is sent, so a Storage failure is only logged and never affects triage.

- Object path: `gs://<bucket>/tickets/<YYYY-MM-DD>/<ticket_id>.json` (prefix via `GCS_PREFIX`).
- Subject and body are masked with `src/pii.py` unless `GCS_STORE_RAW=true`.
- Auth: `gcloud auth application-default login` (API keys do not work for Storage); the account needs e.g. `roles/storage.objectUser` on the bucket.

```bash
gcloud storage buckets create gs://YOUR_BUCKET --project YOUR_PROJECT_ID --location us-central1 --uniform-bucket-level-access --public-access-prevention
echo "GCS_BUCKET=YOUR_BUCKET" >> .env      # then restart uvicorn
```

The console's **History** menu lists past tickets from the bucket (`GET /tickets?limit=30`, newest first, PII-masked). Without Storage it uses the browser's local history.

## Repository layout

```
web/                    React + Vite operator console
app/                    FastAPI: main (routes), pipeline (mode switch + response mapping), chat, storage, mocks, privacy
src/config.py           paths, thresholds, model ids
src/data.py             loading, official split, subject+body joining (handles null subjects)
src/lang.py             en/de detection
src/pii.py              PII masking
src/triage.py           classifiers
src/retrieval.py        embeddings + FAISS search
src/gate.py             escalation rules R1-R6
src/generate.py         grounded reply generation (Gemini) + fallback
src/burst.py            outage burst detection
src/pipeline.py         orchestration, latency, warmup
scripts/                prepare_data, evaluate, tune_sim, test_gate
artifacts/              prebuilt embeddings (KB fit split only)
docs/ARCHITECTURE.md    detailed architecture and API contract
app.py                  legacy Streamlit console (not used in the demo)
```

## Team

| Owner | Area |
|---|---|
| Zhengyang (integrator) | data split, gate, pipeline, integration, README |
| Leo | triage classifier, FastAPI backend, React console, Gemini, Cloud Storage |
| Rory | retrieval, embeddings |
| Teammate 3 | generation, PII, language detection |
| Teammate 4 | evaluation, burst detection |
