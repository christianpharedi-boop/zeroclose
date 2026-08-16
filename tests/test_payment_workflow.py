from decimal import Decimal

from zeroclose.agent import TreasuryAgent
from zeroclose.connectors.stripe import StripeConnector
from zeroclose.ledger_client import VaultEqClient
from zeroclose.payments import SandboxPaymentWorkflow


def test_policy_rejection_prevents_capture(tmp_path):
    ledger = VaultEqClient("reject_org", db_path=tmp_path / "reject.db")
    workflow = SandboxPaymentWorkflow(TreasuryAgent("reject_org", ledger=ledger), StripeConnector())
    result = workflow.process_capture("pay_reject", Decimal("10.00"), "USD", kyc_verified=False)
    assert result.status == "rejected"
    assert ledger.engine.list_journal_entries("reject_org") == []
    ledger.close()


def test_capture_posts_balanced_vaulteq_journal(tmp_path):
    ledger = VaultEqClient("capture_org", db_path=tmp_path / "capture.db")
    workflow = SandboxPaymentWorkflow(TreasuryAgent("capture_org", ledger=ledger), StripeConnector())
    result = workflow.process_capture("pay_1", Decimal("100.00"), "USD")
    assert result.status == "captured"
    assert result.journal_entry_id
    entry = ledger.engine.get_journal_entry("capture_org", result.journal_entry_id)
    assert sum(line["amount_minor"] for line in entry["lines"] if line["direction"] == "DEBIT") == 10000
    assert sum(line["amount_minor"] for line in entry["lines"] if line["direction"] == "CREDIT") == 10000
    assert ledger.verify_chain()
    replay = workflow.process_capture("pay_1", Decimal("100.00"), "USD")
    assert replay.journal_entry_id == result.journal_entry_id
    assert len(ledger.engine.list_journal_entries("capture_org")) == 1
    ledger.close()
