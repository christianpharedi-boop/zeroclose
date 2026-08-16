from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
from typing import Any, Protocol


class LedgerBackend(Protocol):
    """Minimal ledger contract required by ZeroClose orchestration."""

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def snapshot(self, *, at_sequence: int | None = None) -> list[dict[str, Any]]: ...
    def iter_events(self, *, after_sequence: int = 0): ...


class SimulationLedgerClient:
    """Non-durable simulation ledger for tests and local development only."""

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint
        self._events: list[dict[str, Any]] = []

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self._events[-1]["hash"] if self._events else "GENESIS"
        event = {
            "sequence": len(self._events) + 1,
            "event_type": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous,
        }
        event["hash"] = hashlib.sha256(json.dumps(event, sort_keys=True, default=str).encode()).hexdigest()
        self._events.append(event)
        return event

    def get_event(self, sequence: int) -> dict[str, Any] | None:
        if sequence < 1 or sequence > len(self._events):
            return None
        return self._events[sequence - 1]

    def snapshot(self, *, at_sequence: int | None = None) -> list[dict[str, Any]]:
        if at_sequence is None:
            return list(self._events)
        if at_sequence < 0:
            raise ValueError("at_sequence must be non-negative")
        return list(self._events[:at_sequence])

    def iter_events(self, *, after_sequence: int = 0):
        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        yield from self._events[after_sequence:]


# Backward-compatible name for callers that explicitly want the simulation backend.
LedgerClient = SimulationLedgerClient


class VaultEqClient:
    """Adapter for the open-source VaultEq ``LedgerEngine``.

    VaultEq is an optional dependency. Install it from the repository with
    ``pip install -e /path/to/vaulteq`` or from a published package when one is
    available. This adapter uses VaultEq's SQLite-backed hash-chained audit
    events for generic ZeroClose events and exposes native journal posting for
    balanced accounting entries.
    """

    def __init__(self, org_id: str, *, db_path: str | Path = ":memory:", organization_name: str | None = None) -> None:
        try:
            from vaulteq.ledger import LedgerEngine
        except ImportError as exc:
            raise RuntimeError("VaultEq is required for VaultEqClient; install it from the vaulteq repository") from exc
        self.endpoint = f"sqlite://{db_path}"
        self.org_id = org_id
        self.db_path = str(db_path)
        self.engine = LedgerEngine(self.db_path)
        self.organization_name = organization_name or org_id
        self._ensure_organization()

    def _ensure_organization(self) -> None:
        # VaultEq intentionally exposes creation rather than a read-only org lookup.
        # Reopening a durable database is therefore handled by checking its accounts
        # and by translating the known duplicate constraint into a no-op.
        try:
            if not self.engine.list_accounts(self.org_id):
                self.engine.create_organization(self.organization_name, org_id=self.org_id)
        except sqlite3.IntegrityError as exc:
            # VaultEq currently surfaces duplicate organization IDs from SQLite.
            # Keep this narrow: do not hide unrelated database failures.
            if "UNIQUE" not in str(exc).upper():
                raise

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        entity_id = str(payload.get("id") or payload.get("reference") or event_type)
        event_id = self.engine.append_audit_event(self.org_id, "zeroclose", entity_id, event_type, payload)
        events = self.engine.get_audit_trail(self.org_id, limit=1)
        event = events[0] if events else {"id": event_id, "action": event_type, "payload": payload}
        return self._normalize_event(event)

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = event.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"raw": payload}
        return {
            "sequence": event.get("id"),
            "event_type": event.get("action"),
            "payload": payload,
            "timestamp": event.get("created_at"),
            "previous_hash": event.get("prev_event_hash"),
            "hash": event.get("payload_sha256"),
            "id": event.get("id"),
        }

    def snapshot(self, *, at_sequence: int | None = None) -> list[dict[str, Any]]:
        limit = at_sequence if at_sequence is not None else 100000
        if limit < 0:
            raise ValueError("at_sequence must be non-negative")
        events = self.engine.get_audit_trail(self.org_id, limit=limit)
        return [self._normalize_event(event) for event in reversed(events)]

    def iter_events(self, *, after_sequence: int = 0):
        events = self.snapshot()
        yield from events[after_sequence:]

    def verify_chain(self) -> bool:
        return self.engine.verify_audit_chain(self.org_id)

    def post_journal(self, request: Any) -> Any:
        """Post a native VaultEq ``PostRequest`` atomically and idempotently."""
        return self.engine.post(request)

    def health(self) -> dict[str, Any]:
        return {"ok": True, "backend": "vaulteq", "durable": True, "org_id": self.org_id, "chain_valid": self.verify_chain()}

    def close(self) -> None:
        self.engine.close()
