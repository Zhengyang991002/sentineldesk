"""Pseudonymous client registry in BigQuery.

Table  <dataset>.client_tickets  : append-only, one row per analyzed ticket that carries an identifier.
View   <dataset>.clients         : one row per client (first/last seen, ticket and escalation counts).

A client is identified by  client_id = "cust_" + HMAC-SHA256(CLIENT_ID_SALT, "<kind>:<value>")[:24]
where <value> is the email / account number / phone found in the ticket. The raw value is only used
in memory: it is never stored, and the id cannot be reversed without the secret. Keep CLIENT_ID_SALT
stable (changing it changes every client id) and out of git.

Enabled when BQ_DATASET and CLIENT_ID_SALT are set. Auth: Application Default Credentials; the account
needs BigQuery Data Editor + BigQuery Job User on the project. Dataset, table and view are created on
first use (BQ_LOCATION, default US). Writes run in the background and never break triage.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time
from datetime import datetime, timezone

from app.privacy import extract_identifier

log = logging.getLogger("sentineldesk")

TABLE = "client_tickets"
VIEW = "clients"

_client = None
_ready = False


def dataset_id() -> str | None:
    return os.getenv("BQ_DATASET") or None


def is_configured() -> bool:
    return bool(dataset_id() and os.getenv("CLIENT_ID_SALT"))


class NotConfigured(Exception):
    """BQ_DATASET / CLIENT_ID_SALT are not set."""


class InvalidIdentifier(ValueError):
    """The email / account number / phone typed in is not valid."""


_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def derive_client_id(kind: str, value: str) -> str | None:
    """Keyed hash of a normalized identifier; None when there is no salt."""
    salt = os.getenv("CLIENT_ID_SALT")
    if not salt:
        return None
    digest = hmac.new(salt.encode(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()[:24]
    return f"cust_{digest}"


def client_id_for(subject: str | None, body: str) -> tuple[str | None, str | None]:
    """Return (client_id, id_kind) or (None, None) when there is no salt or no identifier."""
    found = extract_identifier(f"{subject or ''} {body}")
    if not found:
        return None, None
    kind, value = found
    client_id = derive_client_id(kind, value)
    return (client_id, kind) if client_id else (None, None)


def normalize_identifier(kind: str, value: str) -> str:
    """Same normalization the ticket path uses, so a manual client and a ticket match."""
    v = (value or "").strip()
    if kind == "email":
        if len(v) > 254 or not _EMAIL_RE.fullmatch(v):
            raise InvalidIdentifier("Enter a valid email address.")
        return v.lower()
    digits = re.sub(r"\D", "", v)
    if kind == "account":
        if not 5 <= len(digits) <= 20:
            raise InvalidIdentifier("An account number has 5 to 20 digits.")
        return digits
    if kind == "phone":
        if not 8 <= len(digits) <= 15:
            raise InvalidIdentifier("A phone number has 8 to 15 digits.")
        return digits
    raise InvalidIdentifier("Unknown identifier type.")


def _get_client():
    global _client
    if _client is None:
        from google.cloud import bigquery

        _client = bigquery.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None)
    return _client


def _fqn(client, name: str) -> str:
    return f"{client.project}.{dataset_id()}.{name}"


def _ensure():
    """Create dataset, table and view if missing (idempotent, once per process)."""
    global _ready
    if _ready:
        return
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery

    c = _get_client()
    ds = bigquery.Dataset(f"{c.project}.{dataset_id()}")
    ds.location = os.getenv("BQ_LOCATION", "US")
    c.create_dataset(ds, exists_ok=True)

    schema = [
        bigquery.SchemaField("client_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("id_kind", "STRING"),
        bigquery.SchemaField("ticket_id", "STRING"),
        bigquery.SchemaField("received_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("language", "STRING"),
        bigquery.SchemaField("type", "STRING"),
        bigquery.SchemaField("queue", "STRING"),
        bigquery.SchemaField("priority", "STRING"),
        bigquery.SchemaField("escalated", "BOOLEAN"),
        bigquery.SchemaField("pii_kinds", "STRING", mode="REPEATED"),
    ]
    table = bigquery.Table(_fqn(c, TABLE), schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(field="received_at")
    table.clustering_fields = ["client_id"]
    c.create_table(table, exists_ok=True)

    view_sql = f"""
        SELECT
          client_id,
          ANY_VALUE(id_kind) AS id_kind,
          MIN(received_at) AS first_seen,
          MAX(received_at) AS last_seen,
          COUNTIF(ticket_id IS NOT NULL) AS ticket_count,
          COUNTIF(escalated) AS escalated_count,
          ARRAY_AGG(DISTINCT language IGNORE NULLS) AS languages,
          ARRAY_AGG(DISTINCT queue IGNORE NULLS) AS queues
        FROM `{_fqn(c, TABLE)}`
        GROUP BY client_id
    """
    try:
        view = c.get_table(_fqn(c, VIEW))
        if (view.view_query or "").split() != view_sql.split():  # an older definition: bring it up to date
            view.view_query = view_sql
            c.update_table(view, ["view_query"])
    except NotFound:
        view = bigquery.Table(_fqn(c, VIEW))
        view.view_query = view_sql
        c.create_table(view, exists_ok=True)
    _ready = True


def record_ticket(client_id, id_kind, ticket_id, result: dict, pii_kinds=()) -> None:
    """Append one row. Never raises."""
    if not is_configured() or not client_id:
        return
    try:
        _ensure()
        c = _get_client()
        row = {
            "client_id": client_id,
            "id_kind": id_kind,
            "ticket_id": ticket_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "language": result.get("language"),
            "type": result.get("type"),
            "queue": result.get("queue"),
            "priority": result.get("priority"),
            "escalated": bool((result.get("escalation") or {}).get("escalate")),
            "pii_kinds": sorted(pii_kinds),
        }
        errors = None
        for _ in range(3):  # a freshly created table can take a moment to accept streaming inserts
            errors = c.insert_rows_json(_fqn(c, TABLE), [row])
            if not errors:
                break
            time.sleep(2)
        if errors:
            log.error("BigQuery rejected the client row: %s", errors)
        else:
            log.info("recorded %s (%s) ticket %s", client_id, id_kind, ticket_id)
    except Exception:
        log.exception("could not record client in BigQuery")


def list_clients(limit: int = 50) -> list[dict]:
    """One row per client, most recently seen first."""
    from google.cloud import bigquery

    _ensure()
    c = _get_client()
    job = c.query(
        f"SELECT * FROM `{_fqn(c, VIEW)}` ORDER BY last_seen DESC LIMIT @limit",
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)]
        ),
    )
    out = []
    for row in job.result():
        d = dict(row.items())
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        out.append(d)
    return out


def add_client(kind: str, value: str) -> dict:
    """Register a client without a ticket. The raw value is hashed and never stored.

    Returns {"client_id", "id_kind", "created"}; `created` is False if that client already exists.
    """
    if not is_configured():
        raise NotConfigured("Set BQ_DATASET and CLIENT_ID_SALT.")
    from google.cloud import bigquery

    client_id = derive_client_id(kind, normalize_identifier(kind, value))
    _ensure()
    c = _get_client()
    table = _fqn(c, TABLE)
    existing = list(
        c.query(
            f"SELECT 1 FROM `{table}` WHERE client_id = @id LIMIT 1",
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("id", "STRING", client_id)]
            ),
        ).result()
    )
    if not existing:
        row = {
            "client_id": client_id,
            "id_kind": kind,
            "ticket_id": None,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "pii_kinds": [],
        }
        errors = None
        for _ in range(3):
            errors = c.insert_rows_json(table, [row])
            if not errors:
                break
            time.sleep(2)
        if errors:
            raise RuntimeError(f"BigQuery rejected the client row: {errors}")
        log.info("added client %s (%s)", client_id, kind)
    return {"client_id": client_id, "id_kind": kind, "created": not existing}
