from __future__ import annotations

from decimal import Decimal
from typing import Any

from .base import PaymentConnector


class StripeConnector(PaymentConnector):
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def capture(self, payment_id: str, amount: Decimal, currency: str) -> dict[str, Any]:
        fee = (amount * Decimal("0.029") + Decimal("0.30")).quantize(Decimal("0.01"))
        return {"id": payment_id, "status": "captured", "gross": str(amount), "fee": str(fee), "net": str(amount - fee), "currency": currency}

    def refund(self, payment_id: str, amount: Decimal | None = None) -> dict[str, Any]:
        return {"id": payment_id, "status": "refund_requested", "amount": str(amount) if amount is not None else None}

    def handle_chargeback(self, payment_id: str, reason: str) -> dict[str, Any]:
        return {"id": payment_id, "status": "chargeback_recorded", "reason": reason}

    def handle_payout(self, payout_id: str, amount: Decimal, currency: str) -> dict[str, Any]:
        return {"id": payout_id, "status": "payout_recorded", "amount": str(amount), "currency": currency}
