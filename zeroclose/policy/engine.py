from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class PolicyDecision(BaseModel):
    allowed: bool
    reasons: list[str] = []
    required_actions: list[str] = []


class PolicyEngine:
    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self.rules = rules or {}

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PolicyEngine":
        return cls(yaml.safe_load(Path(path).read_text()) or {})

    def evaluate(self, transaction: dict[str, Any]) -> PolicyDecision:
        reasons: list[str] = []
        required: list[str] = []
        amount = Decimal(str(transaction.get("amount", "0")))
        thresholds = self.rules.get("amount_thresholds", {})
        max_amount = thresholds.get("max_amount")
        if max_amount is not None and amount > Decimal(str(max_amount)):
            reasons.append(f"amount exceeds maximum threshold of {max_amount}")
        if self.rules.get("kyc", {}).get("required", True) and not transaction.get("kyc_verified", False):
            reasons.append("KYC verification is required")
        if transaction.get("aml_flag", False):
            reasons.append("transaction is flagged by AML controls")
        if self.rules.get("fx", {}).get("require_explicit_rate", True) and transaction.get("source_currency") != transaction.get("destination_currency") and not transaction.get("fx_rate"):
            reasons.append("explicit FX rate is required for currency conversion")
        if amount >= Decimal(str(thresholds.get("manual_review_at", "10000"))):
            required.append("manual_review")
        return PolicyDecision(allowed=not reasons, reasons=reasons, required_actions=required)
