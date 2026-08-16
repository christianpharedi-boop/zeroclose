from decimal import Decimal

from zeroclose.agent import TreasuryAgent
from zeroclose.connectors.stripe import StripeConnector
from zeroclose.ledger_client import LedgerClient, VaultEqClient
from zeroclose.payments import SandboxPaymentWorkflow


def test_simulation_ledger_is_explicitly_non_durable():
    status = TreasuryAgent("sim").status()
    assert status["ledger_backend"] == "simulation"
    assert status["durable"] is False


def test_provider_capture_with_ledger_failure_requires_reconciliation(tmp_path):
    ledger = VaultEqClient("failure_org", db_path=tmp_path / "failure.db")
    original = ledger.post_capture

    def fail_once(*args, **kwargs):
        raise RuntimeError("simulated ledger outage")

    ledger.post_capture = fail_once
    workflow = SandboxPaymentWorkflow(TreasuryAgent("failure_org", ledger=ledger), StripeConnector())
    result = workflow.process_capture("pay_failure", Decimal("25.00"), "USD")
    assert result.status == "needs_reconciliation"
    assert result.reconciliation_required is True
    assert result.provider_capture_id == "pay_failure"
    assert result.trace[-1]["state"] == "reconciliation_required"
    assert any(event["event_type"] == "external_side_effect_pending" for event in ledger.snapshot())
    ledger.post_capture = original
    ledger.close()
