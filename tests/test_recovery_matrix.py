from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from zeroclose.agent import TreasuryAgent
from zeroclose.api.app import create_app
from zeroclose.audit.verifier import verify_chain
from zeroclose.connectors.stripe import StripeConnector
from zeroclose.ledger_client import SimulationLedgerClient, VaultEqClient
from zeroclose.mcp_server import ZeroCloseMCP
from zeroclose.payments import SandboxPaymentWorkflow


def test_simulation_audit_tampering_is_detected():
    ledger = SimulationLedgerClient()
    ledger.append("event", {"value": 1})
    ledger.snapshot()[0]["payload"]["value"] = 99
    assert verify_chain(ledger.snapshot()) is False


def test_pending_capture_survives_restart_and_resolves(tmp_path):
    db_path = tmp_path / "recover.db"
    ledger = VaultEqClient("recover_org", db_path=db_path)
    workflow = SandboxPaymentWorkflow(TreasuryAgent("recover_org", ledger=ledger), StripeConnector())
    workflow._post_capture_journal = lambda *args: (_ for _ in ()).throw(RuntimeError("outage"))
    pending = workflow.process_capture("pay_restart", Decimal("20.00"), "USD")
    assert pending.status == "needs_reconciliation"
    ledger.close()

    reopened = VaultEqClient("recover_org", db_path=db_path)
    recovered = SandboxPaymentWorkflow(TreasuryAgent("recover_org", ledger=reopened), StripeConnector())
    resolved = recovered.resolve_reconciliation("pay_restart")
    assert resolved.status == "captured"
    assert reopened.verify_chain()
    assert recovered.agent.status()["financially_closed"] is True
    reopened.close()


def test_conflicting_retry_is_rejected_after_restart(tmp_path):
    db_path = tmp_path / "conflict.db"
    ledger = VaultEqClient("conflict_org", db_path=db_path)
    workflow = SandboxPaymentWorkflow(TreasuryAgent("conflict_org", ledger=ledger), StripeConnector())
    workflow.process_capture("pay_conflict", Decimal("20.00"), "USD")
    ledger.close()
    reopened = VaultEqClient("conflict_org", db_path=db_path)
    restarted = SandboxPaymentWorkflow(TreasuryAgent("conflict_org", ledger=reopened), StripeConnector())
    with pytest.raises(ValueError, match="conflicting retry"):
        restarted.process_capture("pay_conflict", Decimal("21.00"), "USD")
    reopened.close()


def test_api_and_mcp_use_vaulteq_native_verification(tmp_path):
    ledger = VaultEqClient("verify_org", db_path=tmp_path / "verify.db")
    agent = TreasuryAgent("verify_org", ledger=ledger)
    agent.record_settlement("r1", Decimal("1.00"), "USD")
    client = TestClient(create_app(agent))
    assert client.get("/audit/verify").json()["backend"] == "vaulteq"
    assert client.get("/audit/verify").json()["valid"] is True
    assert ZeroCloseMCP(agent).call("verify_audit_chain")["backend"] == "vaulteq"
    ledger.close()
