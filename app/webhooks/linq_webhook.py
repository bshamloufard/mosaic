import hmac
import hashlib
import time
from app.config import settings
from app.db.client import supabase


def verify_linq_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify Linq webhook HMAC-SHA256 signature.
    Reject if timestamp is older than 5 minutes (replay protection).
    """
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            return False
    except (ValueError, TypeError):
        return False

    expected = hmac.new(
        settings.linq_webhook_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


async def is_duplicate_webhook(message_id: str) -> bool:
    """Check if we've already processed this webhook (idempotency)."""
    result = supabase.table("processed_webhooks")\
        .select("message_id")\
        .eq("message_id", message_id)\
        .execute()
    return len(result.data) > 0


async def mark_webhook_processed(message_id: str) -> None:
    """Mark a webhook as processed."""
    supabase.table("processed_webhooks").insert(
        {"message_id": message_id}
    ).execute()


def parse_linq_webhook(payload: dict) -> dict:
    """
    Parse a Linq webhook payload into a normalized message object.

    DEFENSIVE PARSING: Linq's payload structure can vary between sandbox
    and production, and across API versions. This parser handles known variants:

    Variant A (CareSupport/production docs):
    {"event_type": "message.created", "data": {"chat_id": "...", "message": {"id": "...", "parts": [{"type": "text", "value": "..."}], "from": "+1..."}}}

    Variant B (sandbox/webhook style):
    {"event_type": "message.received", "data": {"chatId": "...", "messageId": "...", "text": "...", "from": "+1...", "service": "iMessage"}}

    Variant C (flat body style seen in some integrations):
    {"type": "message", "chatId": "...", "body": "...", "from": "+1..."}
    """
    event_type = payload.get("event_type", payload.get("type", ""))
    data = payload.get("data", {})
    message = data.get("message", {})

    chat_id = (
        data.get("chat_id")
        or data.get("chatId")
        or payload.get("chatId")
        or ""
    )

    message_id = (
        message.get("id")
        or data.get("messageId")
        or data.get("message_id")
        or payload.get("messageId")
        or ""
    )

    text = ""
    parts = message.get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            text = part.get("value", "")
            break
    if not text:
        text = data.get("text", "")
    if not text:
        text = message.get("body", data.get("body", payload.get("body", "")))

    from_phone = (
        message.get("from")
        or data.get("from")
        or payload.get("from")
        or ""
    )

    service = (
        message.get("service")
        or data.get("service")
        or payload.get("service")
        or "unknown"
    )

    return {
        "event_type": event_type,
        "chat_id": chat_id,
        "message_id": message_id,
        "from_phone": from_phone,
        "text": text,
        "service": service,
    }
