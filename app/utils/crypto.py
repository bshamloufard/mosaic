import hmac
import hashlib
import time


def verify_hmac_sha256(secret: str, payload: bytes, signature: str, timestamp: str = None, max_age_seconds: int = 300) -> bool:
    """
    Verify an HMAC-SHA256 webhook signature with optional replay protection.
    Returns False if signature is invalid or timestamp is too old.
    """
    if timestamp:
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > max_age_seconds:
                return False
        except (ValueError, TypeError):
            return False

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    if signature.startswith("sha256="):
        return hmac.compare_digest(f"sha256={expected}", signature)
    return hmac.compare_digest(expected, signature)
