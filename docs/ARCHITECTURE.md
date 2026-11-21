# Architecture

SentinelDesk triages a support ticket (type, queue, priority, language), retrieves similar resolved
tickets, decides whether a human must handle it, and drafts a cited reply when it does not.
This file says where each piece lives, what is already real and what is still a mock, and where to
plug in the rest.

```
 Browser (React, web/)
   │  fetch /triage /chat /tickets /health        (web/src/api/client.js, proxied by Vite in dev)
   ▼
 FastAPI (app/main.py)
   ├─ POST /triage ─► app/pipeline.py ──► PIPELINE_MODE=mock ─► app/mocks.py
   │                                  └─► PIPELINE_MODE=real ─► src/pipeline.py
   │                                         ├─ src/lang.py       language (en | de)
   │                                         ├─ src/pii.py        mask text before it leaves the machine
   │                                         ├─ src/triage.py     type / queue / priority classifier
   │                                         ├─ src/retrieval.py  top-k similar resolved tickets
   │                                         ├─ src/gate.py       escalation rules R1-R6
   │                                         └─ src/generate.py   grounded reply with citations
   │              └─► app/storage.py  (background task) saves the ticket to Cloud Storage
   ├─ POST /chat ───► app/chat.py     Gemini on Vertex AI, answers from the analyzed ticket
   ├─ GET /tickets ─► app/storage.py  past tickets from Cloud Storage
   └─ GET /health ──► which pipeline mode is active, Gemini and Storage configuration
```

## Repository map

| Path | Role |
|---|---|
| `app/` | HTTP layer. `main.py` routes, `pipeline.py` mode switch and response mapping, `mocks.py`, `chat.py`, `storage.py`, `privacy.py` |
| `src/` | The ML pipeline. Owned per module (see README). Contracts are in each module's docstring |
| `scripts/` | `prepare_data.py` (download and split), `evaluate.py` (scores on the held-out test split) |
| `data/`, `artifacts/`, `reports/` | Parquet splits, trained models, validation reports. Git-ignored except `reports/` |
| `web/` | Operator console (React + Vite). Map below |
| `app.py`, `src/burst.py` | Older Streamlit console. It calls `src.pipeline.run` directly. Not used by the web console |

### Frontend map (`web/src`)

| Path | Role |
|---|---|
| `api/client.js` | The only place that calls the backend. One function per endpoint, plus the `TriageResult` type |
| `config.js` | Constants: pipeline steps, pacing, storage keys, operator profile |
| `hooks/useConsole.js` | All console state and actions (form, analysis, queue, precedent filters, history) |
| `hooks/useHistory.js`, `useStoredState.js` | Browser-local history and persisted UI state |
| `components/` | `Sidebar`, `TicketForm`, `Answers`, `Result`, `Progress`, `HistoryMenu`, `ChatWidget`, `Topbar`, `Icon` |
| `mocks/` | Everything that is fake on the client: sample tickets, on-call avatars, local chat fallback |
| `App.jsx` | Layout only |
| `styles.css` | All styling |

## API contract

`POST /triage` body: `{ "subject": string | null, "body": string }` (`body` must be non-empty, else 422).
Response, identical in every pipeline mode (`TriageResult` in `web/src/api/client.js`):

```json
{
  "type": "Incident",
  "queue": "Technical Support",
  "priority": "high",
  "confidences": { "type": 0.91, "queue": 0.84, "priority": 0.93 },
  "language": "en",
  "latency_ms": 12,
  "stage_ms": { "triage": 8, "retrieve": 3, "gate": 0, "draft": 1 },
  "escalation": { "escalate": true, "reason": "High-priority Incident: page the on-call engineer" },
  "retrieved": [ { "ticket_id": "TKT-01482", "score": 0.87, "answer": "..." } ],
  "draft": { "reply": "...", "cited_ids": ["TKT-01482"] }
}
```

`priority` is `high | medium | low`, `language` is `en | de`, `draft` is `null` when `escalation.escalate`
is true. A stage that raises does not produce an HTTP error: the response is an escalated placeholder
with `reason: "Pipeline error: <stage>"`.

`POST /chat` body: `{ "message", "history": [{ "role": "user" | "bot", "text" }], "ticket": TriageResult | null }`.
Returns `{ "reply", "model" }`. 503 if Gemini is not configured, 502 if the call fails.

`GET /tickets?limit=30` returns `{ "configured": bool, "tickets": [{ ticket_id, received_at, subject, body, result }] }`,
newest first, PII-masked.

`GET /health` returns `{ status, pipeline: { mode, mocked }, gemini: { configured, model }, storage: { configured, bucket } }`.

## What is real and what is a mock

| Piece | State | Where | To make it real |
|---|---|---|---|
| Classifier (type, queue, priority) | Real, TF-IDF + logistic regression | `src/triage.py`, `artifacts/triage.joblib` | Retrain with `python -m src.triage` |
| Retrieval | Real but TF-IDF stand-in | `src/retrieval.py` | Implement `build()` with multilingual embeddings + FAISS (see its docstring), then retune `TAU_SIM` in `src/config.py` |
| Escalation gate | Real | `src/gate.py` | Tune thresholds in `src/config.py` on the validation split only |
| Reply generation | Extractive fallback only | `src/generate.py` | Implement `_llm_draft()` (config names `LLM_MODEL`); the fallback already handles errors |
| API in front of the pipeline | Runs the **mock** by default | `app/pipeline.py`, `app/mocks.py` | Set `PIPELINE_MODE=real` (or `auto`). Verified end to end |
| Gemini chat | Real, Vertex AI | `app/chat.py` | Needs credentials, see README |
| Ticket storage and History menu | Real, Cloud Storage | `app/storage.py`, `HistoryMenu.jsx` | Set `GCS_BUCKET` |
| Progress stepper | Mock: advances on a timer | `Progress.jsx`, `config.js` (`STEP_MS`) | Stream stage events from the backend (SSE or polling) and drive the stepper from them; then set `STEP_MS` to 0 |
| Sample tickets and the queue | Mock | `mocks/samples.js`, `useConsole.js` | Fetch tickets from the helpdesk system or an endpoint; `answerAll` already loops over whatever list it gets |
| On-call managers shown on escalation | Mock avatars | `mocks/onCall.js` | Load the actual on-call roster (PagerDuty, Opsgenie) |
| Operator name and role | Mock, hard-coded | `config.js` (`OPERATOR`) | Take it from authentication |
| Local chat fallback | Mock rule-based answers | `mocks/chatFallback.js` | Delete once Gemini is always configured |
| Outage burst detection | Not wired into the API | `src/burst.py` | Call `BurstDetector.add` from the `/triage` handler, add a `burst` field to the response and show a banner in `Result.jsx` |

## Switching the API from mock to real

1. `python -m scripts.prepare_data` and `python -m src.triage` so `data/` and `artifacts/` exist.
2. Put `PIPELINE_MODE=real` in `.env` (or `auto` to fall back to the mock when loading fails).
3. Start the API and open `GET /health`: `pipeline.mode` must be `real`. Startup loads the model and
   builds the retrieval index, so the first request is not slow.
4. If a real stage needs to return something the UI does not show yet, add the field in
   `_to_api_result` (`app/pipeline.py`), the `TriageResult` type in `web/src/api/client.js`, and the
   component that renders it. The mock in `app/mocks.py` does not need to keep up.

The real gate currently escalates more often than the mock (retrieval similarity is low with TF-IDF).
That is a tuning task for `src/config.py`, not a wiring problem.

## Configuration

Read from the environment or `.env` (see `.env.example`).

| Variable | Used by | Meaning |
|---|---|---|
| `PIPELINE_MODE` | `app/pipeline.py` | `mock` (default), `real`, `auto` |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `VERTEX_API_KEY`, `GEMINI_MODEL` | `app/chat.py` | Gemini via Vertex AI |
| `GCS_BUCKET`, `GCS_PREFIX`, `GCS_STORE_RAW` | `app/storage.py` | Ticket storage. Off unless `GCS_BUCKET` is set |

## Rules to keep

- Anything that leaves the machine (Gemini, Cloud Storage) goes through `app/privacy.mask` first.
- The test split's labels are only read by `scripts/evaluate.py`. Models and the index are fit on the KB `fit` part;
  thresholds are tuned on `val`. See "Leakage rules" in the README.
- Keep `src/` module return shapes as documented in their docstrings; `src/pipeline.py`, `app/pipeline.py`
  and the Streamlit app depend on them.
- Backend calls from the frontend go in `web/src/api/client.js`, not in components.

## Known gaps

- The repo root has both `app.py` (Streamlit) and the `app/` package. Python resolves `app` to the package,
  so `streamlit run app.py` works, but renaming the file (for example to `streamlit_app.py`) would remove the ambiguity.
- No automated tests exist for `app/` or `web/`.
- `config.LLM_MODEL` points at a Claude model for draft generation while the chat uses Gemini. Pick one provider
  before implementing `_llm_draft`.
