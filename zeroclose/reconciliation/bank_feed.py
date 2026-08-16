from __future__ import annotations

from typing import Any, Iterable
from decimal import Decimal

from .matcher import MatchResult, match_entry


class BankReconciler:
    def __init__(self, tolerance: str = "0.01") -> None:
        self.tolerance = Decimal(tolerance)
        self._processed_ids: set[str] = set()

    def reconcile(self, bank_entries: Iterable[dict[str, Any]], ledger_entries: list[dict[str, Any]]) -> list[MatchResult]:
        results: list[MatchResult] = []
        for entry in bank_entries:
            entry_id = str(entry["id"])
            if entry_id in self._processed_ids:
                results.append(MatchResult("already_processed", entry_id, reason="bank entry was previously reconciled"))
                continue
            result = match_entry(entry, ledger_entries, self.tolerance)
            if result.status == "matched":
                self._processed_ids.add(entry_id)
            results.append(result)
        return results
