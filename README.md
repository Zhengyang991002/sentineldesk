# SentinelDesk

Multilingual (EN/DE) incident triage, escalation gate and precedent-grounded reply copilot.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.prepare_data      # download CSV + official 80/20 split (seed 42)
python -m src.pipeline              # end-to-end smoke test
```
Set `ANTHROPIC_API_KEY` in your environment for LLM drafting (falls back to a template reply without it).

## Team ownership
| Owner | Files |
|---|---|
| Integrator | src/data.py, src/gate.py, src/pipeline.py, README |
| Teammate 1 | src/triage.py, scripts/evaluate.py |
| Teammate 2 | src/retrieval.py |
| Teammate 3 | src/generate.py, src/pii.py, src/lang.py |
| Teammate 4 | app.py, src/burst.py |

Interface contracts are in each module's docstring. Do not change return shapes.

## Leakage rules
Models and index are built on the KB `fit` part only; thresholds are tuned on `val`.
The test split's `answer` column is never written to disk.

## Data

Source: Hugging Face dataset `Tobi-Bueck/customer-support-tickets`, file
`aa_dataset-tickets-multi-lang-5-2-50-version.csv` only (28,587 rows: 22,869 KB, 5,718 test).

Dataset decision: the problem statement names this file as the recommended one, so the
official seed-42 split is applied to it as-is, with no filtering, dedup, or relabeling.
We do not use the quick-start's whole-repo load (61,765 rows): it concatenates several
overlapping CSVs with different label schemes, leaving ~10.6k KB rows without `type` or
`answer` and ~2.6k test texts duplicated in the KB.

Split rule (`scripts/prepare_data.py` via `src.data.official_split`, fixed by hackathon rules,
do not change):

1. Shuffle with `df.sample(frac=1.0, random_state=42).reset_index(drop=True)`.
2. Assign `ticket_id = f"TKT-{i:05d}"` by row position after the shuffle.
3. Split by position: first 80% -> `data/kb.parquet` (10% of it marked `split="val"`),
   last 20% -> `data/test_inputs.parquet` (ticket_id, subject, body) and
   `data/test_labels.parquet` (ticket_id, type, queue, priority, language).
   The test `answer` column is never written.

Leakage rule: `data/test_labels.parquet` is read only by `scripts/evaluate.py`, and only to
score predictions already made from `test_inputs`. No training, indexing, or exploration
code may read test data beyond the `test_inputs` row count and the KB/test duplicate-text
check in `explore.py`. EDA output for the KB lives in `data/EDA.md`.

## Run the demo

Local demo only. The API always runs the real pipeline in `src/pipeline.py`; model artifacts and the KB must exist or the API will not start. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```bash
pip install -r requirements.txt
```

Backend (from the repo root):

```bash
uvicorn app.main:app --port 8000
```

Frontend (in a second terminal):

```bash
cd web && npm install && npm run dev
```

Open http://localhost:5173.

## Gemini chat (Vertex AI)

The floating chat calls `POST /chat`, which calls Gemini through Vertex AI (billed to your Google
Cloud project, so your credits apply). No API key is stored anywhere; auth uses Application
Default Credentials. Ticket data is masked with `src/pii.py` before it is sent.

```bash
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com --project YOUR_PROJECT_ID
cp .env.example .env     # then set GOOGLE_CLOUD_PROJECT (and optionally GOOGLE_CLOUD_LOCATION, GEMINI_MODEL)
uvicorn app.main:app --port 8000
```

Alternatively set `VERTEX_API_KEY` in `.env` (Vertex AI express mode): no login or project needed,
and it takes precedence. API keys cannot list models, so pick one with `GEMINI_MODEL`
(`gemini-3-flash-preview` is the default).

`GET /health` shows `gemini.configured`. Without credentials the chat falls back to a local
rule-based reply and says so. To list the models your project can use:

```bash
python -c "from google import genai; c=genai.Client(vertexai=True,project='YOUR_PROJECT_ID',location='us-central1'); [print(m.name) for m in c.models.list()]"
```

## Storing console tickets in Cloud Storage

Every ticket analyzed in the console (including "Answer all") can be saved as JSON in a bucket.
Off by default; enabled by setting `GCS_BUCKET`. Uploads run after the response is sent, so a
Storage failure is only logged and never affects triage.

- Object path: `gs://<bucket>/tickets/<YYYY-MM-DD>/<ticket_id>.json` (change the prefix with `GCS_PREFIX`).
- Contains subject, body, the full triage result and `pii_masked` counts. Subject and body are
  masked with `src/pii.py` unless `GCS_STORE_RAW=true`.
- Auth is `gcloud auth application-default login`; API keys do not work for Storage. The account
  needs write access, e.g. `roles/storage.objectUser` on the bucket.

```bash
gcloud storage buckets create gs://YOUR_BUCKET --project YOUR_PROJECT_ID --location us-central1   --uniform-bucket-level-access --public-access-prevention
echo "GCS_BUCKET=YOUR_BUCKET" >> .env      # then restart uvicorn
```

`GET /health` shows `storage.configured` and the bucket name.

The console's **History** menu lists past tickets from the bucket (`GET /tickets?limit=30`, newest
first, PII-masked) and re-opens a stored result without re-analyzing it. If Storage is not
configured or unreachable it falls back to this browser's local history.

## Client registry (BigQuery)

Clients are tracked **pseudonymously**. For every analyzed ticket the backend looks for an email,
account number or phone, derives `client_id = "cust_" + HMAC-SHA256(CLIENT_ID_SALT, "<kind>:<value>")`
and appends a row to BigQuery. The raw email/number is used only in memory and is never stored; the
id cannot be reversed without the secret. Cards, IBANs and IPs are never used as identifiers.

- Table `<dataset>.client_tickets`: one row per ticket (client_id, id_kind, ticket_id, received_at,
  language, type, queue, priority, escalated, pii_kinds). Append-only.
- View `<dataset>.clients`: one row per client (first/last seen, ticket and escalation counts,
  languages, queues).
- Dataset, table and view are created on first use. The account behind
  `gcloud auth application-default login` needs *BigQuery Data Editor* and *BigQuery Job User*.
- Enable with `BQ_DATASET` and `CLIENT_ID_SALT` in `.env`. **Keep the salt stable and out of git:**
  changing it changes every client id. `GET /clients` returns the view; `GET /health` shows
  `clients.configured`.
- Tickets without an identifier are stored in Cloud Storage as usual but get no client row.
- Every ticket is linked to its client. `POST /triage` returns an extra `client` field
  (`{"client_id", "id_kind"}`, or `null` when the ticket has no identifier), the stored JSON keeps it, and
  `GET /tickets` returns it. The console shows it as a masked reference ("Client: cust_7db4…b57a"):
  clicking it opens the Clients page filtered to that client, and History and the topbar search show
  and match it. The email / account / phone is never shown or stored.
- Clients can also be added by hand: `POST /clients {"kind": "email" | "account" | "phone", "value": "..."}`
  (the *Add client* button on the Clients page). The value is normalized exactly like a ticket's, hashed
  and **not stored**, so a manually added client and a later ticket from the same person share one
  `client_id`. A manual client has no ticket (`ticket_id` is NULL) and shows 0 tickets until one arrives.
  Adding an existing client is a no-op. Only the hash is kept, so there are no names or display labels.

