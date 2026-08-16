from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any


def verify_signature(payload: bytes, signature: str, secret: str, *, tolerance_seconds: int = 300, now: int | None = None) -> bool:
    """Verify a Stripe-style ``t=timestamp,v1=digest`` signature."""
    try:
        fields = dict(item.split("=", 1) for item in signature.split(","))
        timestamp = int(fields["t"])
        digest = fields["v1"]
    except (KeyError, ValueError):
        return False
    import time
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > tolerance_seconds:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def map_event(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, bytes):
        payload = payload.decode()
    event = json.loads(payload) if isinstance(payload, str) else payload
    data = event.get("data", {}).get("object", {})
    return {
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "provider_id": data.get("id"),
        "amount": Decimal(data["amount"]) / Decimal("100") if data.get("amount") is not None else None,
        "currency": (data.get("currency") or "").upper() or None,
        "raw": event,
    }
