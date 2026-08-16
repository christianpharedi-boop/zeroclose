from __future__ import annotations

from decimal import Decimal
from typing import Any

from .base import PayoutConnector


class WiseConnector(PayoutConnector):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._pending: dict[str, dict[str, Any]] = {}

    def create_payout(self, recipient_id: str, amount: Decimal, currency: str) -> dict[str, Any]:
        transfer_id = f"wise_{len(self._pending) + 1}"
        result = {"id": transfer_id, "recipient_id": recipient_id, "amount": str(amount), "currency": currency, "status": "quoted"}
        self._pending[transfer_id] = result
        return result

    def fund(self, transfer_id: str) -> dict[str, Any]:
        if transfer_id not in self._pending:
            raise KeyError(transfer_id)
        self._pending[transfer_id]["status"] = "funded"
        return self._pending[transfer_id]

    def complete(self, transfer_id: str) -> dict[str, Any]:
        if transfer_id not in self._pending:
            raise KeyError(transfer_id)
        if self._pending[transfer_id]["status"] != "funded":
            raise ValueError("transfer must be funded before completion")
        self._pending[transfer_id]["status"] = "completed"
        return self._pending[transfer_id]
