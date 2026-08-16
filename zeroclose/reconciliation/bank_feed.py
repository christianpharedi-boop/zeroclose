from __future__ import annotations

from typing import Any, Iterable

from .matcher import MatchResult, match_entry


class BankReconciler:
    def __init__(self, tolerance: str = "0.01") -> None:
        from decimal import Decimal
        self.tolerance = Decimal(tolerance)

    def reconcile(self, bank_entries: Iterable[dict[str, Any]], ledger_entries: list[dict[str, Any]]) -> list[MatchResult]:
        return [match_entry(entry, ledger_entries, self.tolerance) for entry in bank_entries]
