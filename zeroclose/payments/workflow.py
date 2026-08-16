from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..agent import TreasuryAgent
from ..connectors.stripe import StripeConnector
from ..ledger_client import LedgerBackend


@dataclass
class WorkflowResult:
    status: str
    payment_id: str
    amount: Decimal
    currency: str
    reasons: list[str]
    journal_entry_id: str | None = None
    provider_capture_id: str | None = None
    reconciliation_required: bool = False
    trace: list[dict[str, Any]] | None = None


class SandboxPaymentWorkflow:
    """End-to-end sandbox payment orchestration with durable recovery states."""

    def __init__(self, agent: TreasuryAgent, stripe: StripeConnector) -> None:
        self.agent = agent
        self.stripe = stripe
        self._completed: dict[str, WorkflowResult] = {}

    def process_capture(self, payment_id: str, amount: Decimal, currency: str, *, kyc_verified: bool = True) -> WorkflowResult:
        currency = currency.upper()
        cached = self._completed.get(payment_id) or self._recover_existing(payment_id, amount, currency)
        if cached is not None:
            return cached

        trace: list[dict[str, Any]] = [{"state": "intent", "payment_id": payment_id, "amount": str(amount), "currency": currency}]
        decision = self.agent.authorize({
            "payment_id": payment_id,
            "amount": str(amount),
            "currency": currency,
            "kyc_verified": kyc_verified,
        })
        trace.append({"state": "policy", "allowed": decision.allowed, "reasons": decision.reasons})
        if not decision.allowed:
            trace.append({"state": "closed", "outcome": "rejected"})
            return WorkflowResult("rejected", payment_id, amount, currency, decision.reasons, trace=trace)

        capture_result = self.stripe.capture(payment_id, amount, currency)
        trace.append({"state": "provider_captured", "provider_capture_id": capture_result["id"]})
        fee = Decimal(capture_result["fee"])
        net = Decimal(capture_result["net"])
        journal_id = None

        if hasattr(self.agent.ledger, "post_capture"):
            try:
                journal_id = self._post_capture_journal(payment_id, amount, fee, net, currency)
            except Exception as exc:
                self.agent.ledger.append("external_side_effect_pending", {
                    "payment_id": payment_id,
                    "provider_capture_id": capture_result["id"],
                    "amount": str(amount),
                    "fee": str(fee),
                    "net": str(net),
                    "currency": currency,
                    "error_type": type(exc).__name__,
                })
                trace.extend([
                    {"state": "ledger_failed", "error": type(exc).__name__},
                    {"state": "reconciliation_required", "provider_capture_id": capture_result["id"]},
                ])
                return WorkflowResult(
                    "needs_reconciliation", payment_id, amount, currency,
                    ["provider capture succeeded but VaultEq journal posting failed"],
                    provider_capture_id=capture_result["id"],
                    reconciliation_required=True,
                    trace=trace,
                )

        self.agent.record_settlement(payment_id, amount, currency)
        trace.extend([
            {"state": "ledger_posted", "journal_entry_id": journal_id},
            {"state": "audit_recorded"},
            {"state": "closed", "outcome": "captured"},
        ])
        result = WorkflowResult("captured", payment_id, amount, currency, [], journal_entry_id=journal_id, provider_capture_id=capture_result["id"], trace=trace)
        self._completed[payment_id] = result
        return result

    def resolve_reconciliation(self, payment_id: str) -> WorkflowResult:
        """Retry accounting from durable pending evidence without recapturing the provider payment."""
        pending = self._pending_for(payment_id)
        if pending is None:
            existing = self._recover_existing(payment_id, Decimal("0"), "")
            if existing is not None and existing.status == "captured":
                return existing
            raise KeyError(f"no pending reconciliation for {payment_id}")
        if not hasattr(self.agent.ledger, "post_capture"):
            raise RuntimeError("durable reconciliation resolution requires an accounting-capable ledger backend")

        amount = Decimal(str(pending["amount"]))
        fee = Decimal(str(pending["fee"]))
        net = Decimal(str(pending["net"]))
        currency = str(pending["currency"]).upper()
        journal_id = self._post_capture_journal(payment_id, amount, fee, net, currency)
        self.agent.ledger.append("reconciliation_resolved", {
            "payment_id": payment_id,
            "provider_capture_id": pending.get("provider_capture_id"),
            "journal_entry_id": journal_id,
            "resolution": "accounted",
        })
        self.agent.record_settlement(payment_id, amount, currency)
        trace = [
            {"state": "reconciliation_queue"},
            {"state": "ledger_posted", "journal_entry_id": journal_id},
            {"state": "resolved", "outcome": "accounted"},
            {"state": "closed", "outcome": "captured"},
        ]
        result = WorkflowResult("captured", payment_id, amount, currency, [], journal_entry_id=journal_id, provider_capture_id=pending.get("provider_capture_id"), trace=trace)
        self._completed[payment_id] = result
        return result

    def _post_capture_journal(self, payment_id: str, amount: Decimal, fee: Decimal, net: Decimal, currency: str) -> str:
        if not hasattr(self.agent.ledger, "post_capture"):
            raise RuntimeError("accounting-capable ledger backend is required")
        return self.agent.ledger.post_capture(payment_id, amount, fee, net, currency)

    def _pending_for(self, payment_id: str) -> dict[str, Any] | None:
        resolved = any(event.get("event_type") == "reconciliation_resolved" and event.get("payload", {}).get("payment_id") == payment_id for event in self.agent.ledger.snapshot())
        if resolved:
            return None
        for event in reversed(self.agent.ledger.snapshot()):
            if event.get("event_type") == "external_side_effect_pending" and event.get("payload", {}).get("payment_id") == payment_id:
                return event.get("payload", {})
        return None

    def _recover_existing(self, payment_id: str, amount: Decimal, currency: str) -> WorkflowResult | None:
        for event in reversed(self.agent.ledger.snapshot()):
            payload = event.get("payload", {})
            if payload.get("payment_id") != payment_id and payload.get("reference") != payment_id:
                continue
            event_amount = payload.get("amount")
            event_currency = str(payload.get("currency", "")).upper()
            if amount != Decimal("0") and (Decimal(str(event_amount)) != amount or event_currency != currency):
                raise ValueError(f"conflicting retry for payment {payment_id}")
            if event.get("event_type") == "reconciliation_resolved" or event.get("event_type") == "settlement":
                result = WorkflowResult("captured", payment_id, Decimal(str(event_amount)), event_currency, [], provider_capture_id=payment_id, trace=[{"state": "recovered"}, {"state": "closed", "outcome": "captured"}])
                self._completed[payment_id] = result
                return result
            if event.get("event_type") == "external_side_effect_pending":
                return WorkflowResult("needs_reconciliation", payment_id, Decimal(str(event_amount)), event_currency, ["provider capture is awaiting reconciliation"], provider_capture_id=payload.get("provider_capture_id"), reconciliation_required=True, trace=[{"state": "recovered_pending"}])
        return None

