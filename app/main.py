import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import chat, storage
from app.pipeline import MODE, run_pipeline

log = logging.getLogger("sentineldesk")

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


@app.post("/triage")
def triage_endpoint(req: TriageRequest, background: BackgroundTasks):
    if not req.body.strip():
        raise HTTPException(status_code=422, detail="Ticket body must not be empty.")
    result = run_pipeline(req.subject, req.body)
    if storage.is_configured():
        # After the response is sent; a failure is logged and never reaches the client.
        background.add_task(storage.save_ticket, req.subject, req.body, result)
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


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pipeline": {"mode": MODE, "mocked": MODE == "mock"},
        "gemini": {"configured": chat.is_configured(), "model": chat.model_name()},
        "storage": {"configured": storage.is_configured(), "bucket": storage.bucket_name()},
    }
