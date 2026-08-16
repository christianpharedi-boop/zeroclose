from decimal import Decimal

from zeroclose.audit.verifier import verify_chain
from zeroclose.fx.registry import FXRegistry
from zeroclose.ledger_client import LedgerClient


def test_fx_lock_and_convert():
    registry = FXRegistry()
    registry.lock("fx1", "USD", "EUR", Decimal("0.92"))
    assert registry.convert(Decimal("100"), "fx1") == Decimal("92.00")


def test_ledger_chain_verifies():
    ledger = LedgerClient()
    ledger.append("test", {"value": 1})
    ledger.append("test", {"value": 2})
    assert verify_chain(ledger.snapshot())
