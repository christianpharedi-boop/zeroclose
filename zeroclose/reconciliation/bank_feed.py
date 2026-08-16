from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from ..ledger_client import LedgerBackend
from .matcher import MatchResult, match_entry


class BankReconciler:
    def __init__(self, tolerance: str = "0.01", *, ledger: LedgerBackend | None = None) -> None:
        self.tolerance = Decimal(tolerance)
        self.ledger = ledger
        self._processed_ids: set[str] = set()

    def _is_processed(self, entry_id: str) -> bool:
        if entry_id in self._processed_ids:
            return True
        if self.ledger is None:
            return False
        return any(
            event.get("event_type") == "bank_reconciliation_matched"
            and event.get("payload", {}).get("bank_entry_id") == entry_id
            for event in self.ledger.snapshot()
        )

    def reconcile(self, bank_entries: Iterable[dict[str, Any]], ledger_entries: list[dict[str, Any]]) -> list[MatchResult]:
        results: list[MatchResult] = []
        for entry in bank_entries:
            entry_id = str(entry["id"])
            if self._is_processed(entry_id):
                results.append(MatchResult("already_processed", entry_id, reason="bank entry was previously reconciled"))
                continue
            result = match_entry(entry, ledger_entries, self.tolerance)
            if result.status == "matched":
                self._processed_ids.add(entry_id)
                if self.ledger is not None:
                    self.ledger.append("bank_reconciliation_matched", {
                        "bank_entry_id": entry_id,
                        "ledger_entry_id": result.ledger_entry_id,
                        "variance": str(result.variance),
                    })
            results.append(result)
        return results
