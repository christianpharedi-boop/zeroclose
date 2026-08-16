from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class MatchResult:
    status: str
    bank_entry_id: str
    ledger_entry_id: str | None = None
    variance: Decimal = Decimal("0")
    reason: str | None = None


def match_entry(bank: dict[str, Any], ledger_entries: list[dict[str, Any]], tolerance: Decimal = Decimal("0.01")) -> MatchResult:
    candidates = [e for e in ledger_entries if e.get("reference") == bank.get("reference") and e.get("currency") == bank.get("currency")]
    if not candidates:
        return MatchResult("suspense", str(bank["id"]), reason="no reference and currency match")
    target = candidates[0]
    variance = abs(Decimal(str(bank["amount"])) - Decimal(str(target["amount"])))
    if variance <= tolerance:
        return MatchResult("matched", str(bank["id"]), str(target["id"]), variance)
    return MatchResult("exception", str(bank["id"]), str(target["id"]), variance, "amount exceeds tolerance")
