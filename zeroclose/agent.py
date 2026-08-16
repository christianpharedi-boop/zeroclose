from __future__ import annotations

from decimal import Decimal
from typing import Any

from .config import ZeroCloseConfig
from .ledger_client import LedgerClient, SimulationLedgerClient, VaultEqClient
from .policy.engine import PolicyDecision, PolicyEngine


class TreasuryAgent:
    def __init__(self, org_id: str, policies: str = "strict", *, config: ZeroCloseConfig | None = None, ledger: LedgerClient | None = None) -> None:
        self.config = config or ZeroCloseConfig(org_id=org_id, policies=policies)
        self.ledger = ledger or LedgerClient()
        self.policy = PolicyEngine({"kyc": {"required": policies == "strict"}, "fx": {"require_explicit_rate": True}, "amount_thresholds": {"manual_review_at": "10000"}})

    def authorize(self, transaction: dict[str, Any]) -> PolicyDecision:
        decision = self.policy.evaluate(transaction)
        self.ledger.append("policy_decision", {"transaction": transaction, "decision": decision.model_dump()})
        return decision

    def record_settlement(self, reference: str, amount: Decimal, currency: str) -> dict[str, Any]:
        return self.ledger.append("settlement", {"reference": reference, "amount": str(amount), "currency": currency})

    def status(self) -> dict[str, Any]:
        durable = isinstance(self.ledger, VaultEqClient)
        return {
            "org_id": self.config.org_id,
            "always_closed": True,
            "ledger_events": len(self.ledger.snapshot()),
            "ledger_backend": "vaulteq" if durable else "simulation",
            "durable": durable,
        }
