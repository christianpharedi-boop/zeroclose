from __future__ import annotations

from decimal import Decimal
from typing import Any

from .config import ZeroCloseConfig
from .ledger_client import LedgerBackend, SimulationLedgerClient, VaultEqClient
from .policy.engine import PolicyDecision, PolicyEngine


class TreasuryAgent:
    def __init__(self, org_id: str, policies: str = "strict", *, config: ZeroCloseConfig | None = None, ledger: LedgerBackend | None = None) -> None:
        self.config = config or ZeroCloseConfig(org_id=org_id, policies=policies)
        self.ledger = ledger or SimulationLedgerClient()
        self.policy = PolicyEngine({"kyc": {"required": policies == "strict"}, "fx": {"require_explicit_rate": True}, "amount_thresholds": {"manual_review_at": "10000"}})

    def authorize(self, transaction: dict[str, Any]) -> PolicyDecision:
        decision = self.policy.evaluate(transaction)
        self.ledger.append("policy_decision", {"transaction": transaction, "decision": decision.model_dump()})
        return decision

    def record_settlement(self, reference: str, amount: Decimal, currency: str) -> dict[str, Any]:
        return self.ledger.append("settlement", {"reference": reference, "amount": str(amount), "currency": currency})

    def status(self) -> dict[str, Any]:
        durable = isinstance(self.ledger, VaultEqClient)
        events = self.ledger.snapshot()
        resolved = {event.get("payload", {}).get("payment_id") for event in events if event.get("event_type") == "reconciliation_resolved"}
        pending = sum(1 for event in events if event.get("event_type") == "external_side_effect_pending" and event.get("payload", {}).get("payment_id") not in resolved)
        return {
            "org_id": self.config.org_id,
            # Every workflow reaches either a normal terminal state or a controlled exception state.
            "always_closed": True,
            "financially_closed": pending == 0,
            "controlled_exception_count": pending,
            "ledger_events": len(events),
            "ledger_backend": "vaulteq" if durable else "simulation",
            "durable": durable,
            "closure_definition": "terminal_or_controlled_exception",
        }
