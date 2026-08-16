from zeroclose.ledger_client import VaultEqClient
from zeroclose.reconciliation.bank_feed import BankReconciler


def test_bank_replay_protection_survives_restart(tmp_path):
    db_path = tmp_path / "bank.db"
    ledger = VaultEqClient("bank_org", db_path=db_path)
    bank = [{"id": "bank_1", "reference": "ref_1", "currency": "USD", "amount": "10.00"}]
    entries = [{"id": "ledger_1", "reference": "ref_1", "currency": "USD", "amount": "10.00"}]
    assert BankReconciler(ledger=ledger).reconcile(bank, entries)[0].status == "matched"
    ledger.close()

    reopened = VaultEqClient("bank_org", db_path=db_path)
    assert BankReconciler(ledger=reopened).reconcile(bank, entries)[0].status == "already_processed"
    reopened.close()
