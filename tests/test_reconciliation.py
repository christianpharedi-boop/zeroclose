from zeroclose.reconciliation.bank_feed import BankReconciler


def test_reconciles_within_tolerance():
    results = BankReconciler("0.01").reconcile(
        [{"id": "b1", "reference": "r1", "currency": "USD", "amount": "100.00"}],
        [{"id": "l1", "reference": "r1", "currency": "USD", "amount": "100.005"}],
    )
    assert results[0].status == "matched"


def test_unmatched_entry_goes_to_suspense():
    result = BankReconciler().reconcile([{"id": "b1", "reference": "x", "currency": "USD", "amount": "1"}], [])[0]
    assert result.status == "suspense"
