import hmac
import hashlib
import time
from app.config import settings
from app.db.client import supabase


def verify_linq_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify Linq webhook HMAC-SHA256 signature.
    Signed payload format: "{timestamp}.{body}"
    Signature is raw hex digest (no prefix).
    Reject if timestamp is older than 5 minutes (replay protection).
    """
    if not timestamp or not signature:
        return False

    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            return False
    except (ValueError, TypeError):
        return False

    # Linq signs: "{timestamp}.{raw_body}"
    message = f"{timestamp}.{request_body.decode('utf-8')}"
    expected = hmac.new(
        settings.linq_webhook_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    # Linq sends raw hex digest, handle optional sha256= prefix too
    clean_signature = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, clean_signature)


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

    V3 API (2026-02-03 schema) format:
    {
      "event_type": "message.received",
      "event_id": "...",
      "data": {
        "chat": {"id": "...", "owner_handle": {"handle": "+1..."}},
        "id": "message-uuid",
        "sender_handle": {"handle": "+1..."},
        "service": "iMessage",
        "parts": [{"type": "text", "value": "Hello"}]
      }
    }

    Also handles legacy flat variants for backwards compatibility.
    """
    event_type = payload.get("event_type", payload.get("type", ""))
    data = payload.get("data", {})

    # --- Chat ID ---
    # V3: data.chat.id
    chat = data.get("chat", {})
    chat_id = (
        chat.get("id")
        or data.get("chat_id")
        or data.get("chatId")
        or payload.get("chatId")
        or ""
    )

    # --- Message ID ---
    # V3: data.id
    message = data.get("message", {})
    message_id = (
        data.get("id")
        or data.get("event_id")
        or payload.get("event_id")
        or message.get("id")
        or data.get("messageId")
        or ""
    )

    # --- Text content ---
    # V3: data.parts[].type=="text" -> .value
    text = ""
    parts = data.get("parts", []) or message.get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            text = part.get("value", "")
            break
    if not text:
        text = data.get("text", "")
    if not text:
        text = message.get("body", data.get("body", payload.get("body", "")))

    # --- Sender phone ---
    # V3: data.sender_handle.handle
    sender_handle = data.get("sender_handle", {})
    from_phone = (
        sender_handle.get("handle")
        or message.get("from")
        or data.get("from")
        or payload.get("from")
        or ""
    )

    # --- Service ---
    service = (
        data.get("service")
        or message.get("service")
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
