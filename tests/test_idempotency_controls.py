import json

from fastapi.testclient import TestClient

from zeroclose.agent import TreasuryAgent
from zeroclose.api.app import create_app
from zeroclose.reconciliation.bank_feed import BankReconciler


def test_duplicate_webhook_has_no_second_ledger_event():
    client = TestClient(create_app(TreasuryAgent("webhook_org")))
    payload = {"id": "evt_1", "type": "test.event", "data": {"object": {}}}
    first = client.post("/webhooks/stripe", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    second = client.post("/webhooks/stripe", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert client.get("/status").json()["ledger_events"] == 1


def test_reconciliation_marks_duplicate_bank_entry_processed():
    reconciler = BankReconciler()
    bank = [{"id": "bank_1", "reference": "ref_1", "currency": "USD", "amount": "10.00"}]
    ledger = [{"id": "ledger_1", "reference": "ref_1", "currency": "USD", "amount": "10.00"}]
    assert reconciler.reconcile(bank, ledger)[0].status == "matched"
    assert reconciler.reconcile(bank, ledger)[0].status == "already_processed"
