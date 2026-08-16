from __future__ import annotations

import hashlib
import json
from typing import Any


def verify_chain(events: list[dict[str, Any]]) -> bool:
    previous = "GENESIS"
    for event in events:
        if event.get("previous_hash") != previous:
            return False
        content = {k: v for k, v in event.items() if k != "hash"}
        expected = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
        if event.get("hash") != expected:
            return False
        previous = event["hash"]
    return True
