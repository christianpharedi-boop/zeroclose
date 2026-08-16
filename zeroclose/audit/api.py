from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from ..ledger_client import LedgerClient
from .verifier import verify_chain


def audit_snapshot(ledger: LedgerClient, at_sequence: int | None = None) -> dict[str, Any]:
    events = ledger.snapshot(at_sequence=at_sequence)
    return {"events": events, "event_count": len(events), "chain_valid": verify_chain(events)}


def audit_stream(ledger: LedgerClient, *, after_sequence: int = 0) -> AsyncIterator[str]:
    async def stream() -> AsyncIterator[str]:
        for event in ledger.iter_events(after_sequence=after_sequence):
            yield f"data: {json.dumps(event, default=str)}\n\n"
            await asyncio.sleep(0)
    return stream()
