"""Persist console tickets to Google Cloud Storage.

Disabled unless GCS_BUCKET is set. Auth uses Application Default Credentials
(`gcloud auth application-default login`); the bucket must already exist and the
account needs write access (e.g. roles/storage.objectUser on the bucket).

Layout:  gs://<bucket>/<GCS_PREFIX>/<YYYY-MM-DD>/<ticket_id>.json

Subject and body are PII-masked before upload unless GCS_STORE_RAW=true.
Uploads run as a background task and must never break triage: errors are only logged.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.privacy import mask

log = logging.getLogger("sentineldesk")

_client = None


def bucket_name() -> str | None:
    return os.getenv("GCS_BUCKET") or None


def is_configured() -> bool:
    return bucket_name() is not None


def _prefix() -> str:
    return os.getenv("GCS_PREFIX", "tickets").strip("/")


def _get_client():
    global _client
    if _client is None:
        from google.cloud import storage

        _client = storage.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None)
    return _client


def new_ticket_id() -> str:
    return f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"


def build_record(subject: str | None, body: str, result: dict, client_id: str | None = None) -> tuple[str, str, dict]:
    """Return (object_name, ticket_id, record). Pure function, easy to test."""
    now = datetime.now(timezone.utc)
    ticket_id = f"{now:%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    raw = os.getenv("GCS_STORE_RAW", "").lower() in ("1", "true", "yes")
    if raw:
        subject_out, body_out, pii = subject or "", body, {}
    else:
        subject_out, c1 = mask(subject or "")
        body_out, c2 = mask(body)
        pii = {k: c1.get(k, 0) + c2.get(k, 0) for k in {*c1, *c2}}
    record = {
        "ticket_id": ticket_id,
        "client_id": client_id,
        "received_at": now.isoformat(),
        "subject": subject_out,
        "body": body_out,
        "pii_masked": pii,
        "raw": raw,
        "result": result,
    }
    return f"{_prefix()}/{now:%Y-%m-%d}/{ticket_id}.json", ticket_id, record


def save_ticket(subject: str | None, body: str, result: dict, client_id: str | None = None) -> str | None:
    """Upload one ticket and return its id (None if disabled or failed). Never raises."""
    name = bucket_name()
    if not name:
        return None
    try:
        object_name, ticket_id, record = build_record(subject, body, result, client_id)
        blob = _get_client().bucket(name).blob(object_name)
        blob.upload_from_string(
            json.dumps(record, ensure_ascii=False, indent=2),
            content_type="application/json",
            if_generation_match=0,  # never overwrite an existing object
        )
        log.info("stored ticket %s -> gs://%s/%s", ticket_id, name, object_name)
        return ticket_id
    except Exception:
        log.exception("could not store ticket in gs://%s", name)
        return None


def list_recent(limit: int = 30) -> list[dict]:
    """Most recent stored tickets, newest first.

    Objects live under <prefix>/<YYYY-MM-DD>/, so we list the date folders and walk them
    newest to oldest until we have `limit` objects, instead of listing the whole bucket.
    """
    name = bucket_name()
    if not name:
        return []
    client = _get_client()
    prefix = _prefix() + "/"

    it = client.list_blobs(name, prefix=prefix, delimiter="/")
    list(it)  # exhaust the iterator so it.prefixes is populated

    def load(blob):
        try:
            return json.loads(blob.download_as_text())
        except Exception:
            log.warning("skipping unreadable object %s", blob.name)
            return None

    out: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for day in sorted(it.prefixes, reverse=True):
            blobs = [b for b in client.list_blobs(name, prefix=day) if b.name.endswith(".json")]
            blobs.sort(key=lambda b: b.name.rsplit("/", 1)[-1], reverse=True)  # ids start with a timestamp
            i = 0
            # load in chunks so unreadable objects don't eat into the limit
            while i < len(blobs) and len(out) < limit:
                chunk = blobs[i : i + (limit - len(out))]
                i += len(chunk)
                for r in pool.map(load, chunk):
                    if r and isinstance(r.get("result"), dict):
                        out.append(
                            {
                                "ticket_id": r.get("ticket_id"),
                                "client_id": r.get("client_id"),
                                "received_at": r.get("received_at"),
                                "subject": r.get("subject", ""),
                                "body": r.get("body", ""),
                                "result": r["result"],
                            }
                        )
            if len(out) >= limit:
                break
    return out[:limit]
