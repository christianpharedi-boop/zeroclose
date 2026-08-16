from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from ..agent import TreasuryAgent
from ..connectors.stripe import StripeConnector
from ..ledger_client import VaultEqClient


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
    """End-to-end sandbox payment orchestration."""

    def __init__(self, agent: TreasuryAgent, stripe: StripeConnector) -> None:
        self.agent = agent
        self.stripe = stripe
        self._completed: dict[str, WorkflowResult] = {}

    def process_capture(self, payment_id: str, amount: Decimal, currency: str, *, kyc_verified: bool = True) -> WorkflowResult:
        if payment_id in self._completed:
            return self._completed[payment_id]

        trace: list[dict[str, Any]] = [{"state": "intent", "payment_id": payment_id, "amount": str(amount), "currency": currency}]

        # 1. Policy evaluation
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

        # 2. Provider capture
        capture_result = self.stripe.capture(payment_id, amount, currency)
        trace.append({"state": "provider_captured", "provider_capture_id": capture_result["id"]})
        fee = Decimal(capture_result["fee"])
        net = Decimal(capture_result["net"])

        # 3. VaultEq journal posting (if using VaultEqClient)
        journal_id = None
        if isinstance(self.agent.ledger, VaultEqClient):
            from vaulteq.ledger import Direction, JournalLineInput, PostRequest
            
            # Ensure accounts exist
            self._ensure_accounts(self.agent.ledger)
            
            # Convert to minor units (cents)
            amount_minor = int(amount * 100)
            fee_minor = int(fee * 100)
            net_minor = int(net * 100)
            
            req = PostRequest(
                organization_id=self.agent.ledger.org_id,
                idempotency_key=f"capture_{payment_id}",
                memo=f"Capture {payment_id}",
                lines=[
                    JournalLineInput("1000", Direction.DEBIT, net_minor, currency, "Stripe Balance"),
                    JournalLineInput("5000", Direction.DEBIT, fee_minor, currency, "Stripe Fees"),
                    JournalLineInput("4000", Direction.CREDIT, amount_minor, currency, "Revenue"),
                ]
            )
            try:
                resp = self.agent.ledger.post_journal(req)
                journal_id = resp.journal_entry_id
            except Exception as exc:
                # Provider side effects and ledger writes are not one atomic transaction.
                # Preserve an explicit open state for reconciliation instead of claiming closure.
                trace.append({"state": "ledger_failed", "error": type(exc).__name__})
                self.agent.ledger.append("external_side_effect_pending", {
                    "payment_id": payment_id,
                    "provider_capture_id": capture_result["id"],
                    "amount": str(amount),
                    "currency": currency,
                    "error_type": type(exc).__name__,
                })
                trace.append({"state": "reconciliation_required", "provider_capture_id": capture_result["id"]})
                return WorkflowResult(
                    "needs_reconciliation", payment_id, amount, currency,
                    ["provider capture succeeded but VaultEq journal posting failed"],
                    provider_capture_id=capture_result["id"],
                    reconciliation_required=True,
                    trace=trace,
                )

        # 4. Record generic settlement audit event
        self.agent.record_settlement(payment_id, amount, currency)
        trace.extend([
            {"state": "ledger_posted", "journal_entry_id": journal_id},
            {"state": "audit_recorded"},
            {"state": "closed", "outcome": "captured"},
        ])

        result = WorkflowResult("captured", payment_id, amount, currency, [], journal_entry_id=journal_id, provider_capture_id=capture_result["id"], trace=trace)
        self._completed[payment_id] = result
        return result

    def _ensure_accounts(self, ledger: VaultEqClient) -> None:
        from vaulteq.ledger import AccountType, Direction
        accounts = {a["code"] for a in ledger.engine.list_accounts(ledger.org_id)}
        if "1000" not in accounts:
            ledger.engine.create_account(ledger.org_id, "1000", "Stripe Balance", AccountType.ASSET, Direction.DEBIT)
        if "4000" not in accounts:
            ledger.engine.create_account(ledger.org_id, "4000", "Revenue", AccountType.REVENUE, Direction.CREDIT)
        if "5000" not in accounts:
            ledger.engine.create_account(ledger.org_id, "5000", "Stripe Fees", AccountType.EXPENSE, Direction.DEBIT)
