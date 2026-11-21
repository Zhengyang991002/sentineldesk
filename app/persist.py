"""Persist an analyzed ticket: Cloud Storage (masked JSON) and the BigQuery client registry.

Runs as a background task after the response is sent. The raw ticket text is only read in memory
here (to derive a pseudonymous client id); it is never written anywhere unmasked.
"""
from __future__ import annotations

from app import clients, storage
from app.privacy import mask


def save_all(subject: str | None, body: str, result: dict, client_id: str | None = None, id_kind: str | None = None) -> None:
    if not client_id:  # no client picked in the form: detect it from the ticket text
        client_id, id_kind = clients.client_id_for(subject, body)
    ticket_id = storage.save_ticket(subject, body, result, client_id=client_id)
    if client_id:
        _, found = mask(f"{subject or ''} {body}")
        clients.record_ticket(client_id, id_kind, ticket_id or storage.new_ticket_id(), result, pii_kinds=found)
