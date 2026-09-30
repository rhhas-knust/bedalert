"""Outbound SMS.

Messages are written to `sms_outbox` inside the same transaction as the
change that caused them, and only sent after that transaction commits
(`flush_outbox`). So a rolled-back hold never texts anyone, and a failing
SMS provider never rolls back a hold.
"""

import logging

import httpx
from psycopg import Connection

from .config import settings
from .db import connection

log = logging.getLogger("bedalert.sms")


def queue_sms(conn: Connection, to_phone: str, body: str, purpose: str) -> None:
    conn.execute(
        "insert into sms_outbox (to_phone, body, purpose) values (%s, %s, %s)",
        (to_phone, body[:459], purpose),  # 3 SMS segments max
    )


def _send(to_phone: str, body: str) -> str:
    if settings.sms_provider == "console":
        log.warning("SMS (console, not really sent) to %s: %s", to_phone, body)
        return "console"
    if settings.sms_provider == "africastalking":
        host = "api.sandbox.africastalking.com" if settings.at_username == "sandbox" else "api.africastalking.com"
        data = {"username": settings.at_username, "to": to_phone, "message": body}
        if settings.at_sender_id:
            data["from"] = settings.at_sender_id
        resp = httpx.post(
            f"https://{host}/version1/messaging",
            data=data,
            headers={"apiKey": settings.at_api_key, "Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        recipients = resp.json().get("SMSMessageData", {}).get("Recipients", [])
        if not recipients or recipients[0].get("status") != "Success":
            raise RuntimeError(f"Africa's Talking rejected message: {resp.text[:300]}")
        return recipients[0].get("messageId", "")
    raise RuntimeError(f"Unknown SMS_PROVIDER '{settings.sms_provider}'")


def flush_outbox(limit: int = 50) -> int:
    """Send queued messages. Safe to call concurrently (SKIP LOCKED)."""
    sent = 0
    with connection() as conn:
        rows = conn.execute(
            """select id, to_phone, body from sms_outbox
               where status = 'queued' order by created_at limit %s
               for update skip locked""",
            (limit,),
        ).fetchall()
        for row in rows:
            try:
                ref = _send(row["to_phone"], row["body"])
                conn.execute(
                    "update sms_outbox set status = 'sent', provider_ref = %s, sent_at = now() where id = %s",
                    (ref, row["id"]),
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001 — record and carry on
                log.exception("SMS to %s failed", row["to_phone"])
                conn.execute(
                    "update sms_outbox set status = 'failed', error = %s where id = %s",
                    (str(exc)[:500], row["id"]),
                )
    return sent


def run_outbox_worker(stop_event, interval: float = 2.0) -> None:
    """Background thread: sends queued SMS a moment after the transaction
    that queued them commits."""
    while not stop_event.is_set():
        try:
            flush_outbox()
        except Exception:  # noqa: BLE001 — never let the worker die
            log.exception("Outbox flush failed")
        stop_event.wait(interval)
