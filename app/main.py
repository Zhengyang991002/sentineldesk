import logging
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import chat, clients, manager_agent, persist, storage
from app.pipeline import MODE, run_pipeline
from src import retrieval as _retrieval, triage as _triage
from src.burst import BurstDetector

log = logging.getLogger("sentineldesk")

burst_detector = BurstDetector()  # in-memory, per process

app = FastAPI(title="SentinelDesk")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriageRequest(BaseModel):
    subject: str | None = None
    body: str
    # Client picked in the form (pseudonymous id from GET /clients). When absent, it is detected from the text.
    client_id: str | None = Field(default=None, pattern=r"^cust_[0-9a-f]{24}$")
    client_kind: Literal["email", "account", "phone"] | None = None


@app.post("/triage")
def triage_endpoint(req: TriageRequest, background: BackgroundTasks):
    if not req.body.strip():
        raise HTTPException(status_code=422, detail="Ticket body must not be empty.")
    result = run_pipeline(req.subject, req.body)
    # Which client wrote this ticket: only the keyed hash, never the email / account / phone behind it.
    if req.client_id:
        client_id, id_kind = req.client_id, req.client_kind
    else:
        client_id, id_kind = clients.client_id_for(req.subject, req.body)
    result["client"] = {"client_id": client_id, "id_kind": id_kind} if client_id else None
    try:  # outage detection must never break triage
        result["burst"] = burst_detector.add(req.subject, req.body, result.get("language", ""))
    except Exception:
        log.exception("burst detection failed")
        result["burst"] = None
    if storage.is_configured() or clients.is_configured():
        # After the response is sent; a failure is logged and never reaches the client.
        background.add_task(persist.save_all, req.subject, req.body, result, client_id, id_kind)
    return result


@app.post("/chat")
def chat_endpoint(req: chat.ChatRequest):
    try:
        return {"reply": chat.answer(req), "model": chat.model_name()}
    except chat.NotConfigured as exc:
        raise HTTPException(status_code=503, detail=f"Gemini is not configured: {exc}")
    except Exception as exc:
        # Missing credentials are a setup problem; anything else is a failed call.
        if type(exc).__name__ == "DefaultCredentialsError":
            raise HTTPException(
                status_code=503,
                detail="Gemini is not configured: no Application Default Credentials "
                "(run `gcloud auth application-default login`).",
            )
        log.exception("Gemini call failed")
        raise HTTPException(status_code=502, detail="Gemini request failed. Check the server logs.")


class AssignRequest(BaseModel):
    ticket: dict


@app.post("/assign-manager")
def assign_manager_endpoint(req: AssignRequest):
    """Gemini agent: which manager should take this escalated ticket (rules fallback, never fails)."""
    return manager_agent.recommend(req.ticket)


@app.get("/burst")
def burst_endpoint():
    """Current outage cluster among recent tickets (masked subjects only), for the console banner."""
    return burst_detector.status()


@app.get("/tickets")
def tickets(limit: int = Query(30, ge=1, le=100)):
    """Past tickets stored in Cloud Storage (PII-masked), newest first."""
    if not storage.is_configured():
        return {"configured": False, "tickets": []}
    try:
        return {"configured": True, "tickets": storage.list_recent(limit)}
    except Exception:
        log.exception("could not list tickets from Cloud Storage")
        raise HTTPException(status_code=502, detail="Could not list tickets from Cloud Storage.")


class ClientIn(BaseModel):
    kind: Literal["email", "account", "phone"]
    value: str = Field(min_length=1, max_length=254)


@app.post("/clients")
def add_client_endpoint(req: ClientIn):
    """Register a client by email / account number / phone. Only the keyed hash is stored."""
    try:
        return clients.add_client(req.kind, req.value)
    except clients.NotConfigured:
        raise HTTPException(status_code=503, detail="Client registry is not configured. Set BQ_DATASET and CLIENT_ID_SALT.")
    except clients.InvalidIdentifier as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        log.exception("could not add client")  # never log the submitted value
        raise HTTPException(status_code=502, detail="Could not add the client in BigQuery.")


@app.get("/clients")
def clients_endpoint(limit: int = Query(50, ge=1, le=200)):
    """Pseudonymous clients (one row each) from the BigQuery `clients` view, most recent first."""
    if not clients.is_configured():
        return {"configured": False, "clients": []}
    try:
        return {"configured": True, "clients": clients.list_clients(limit)}
    except Exception:
        log.exception("could not read clients from BigQuery")
        raise HTTPException(status_code=502, detail="Could not read clients from BigQuery.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pipeline": {"mode": MODE, "retrieval": _retrieval.active_backend(), "classifier": _triage.active_model()},
        "gemini": {"configured": chat.is_configured(), "model": chat.model_name()},
        "storage": {"configured": storage.is_configured(), "bucket": storage.bucket_name()},
        "clients": {"configured": clients.is_configured(), "dataset": clients.dataset_id()},
    }
