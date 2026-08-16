from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class PaymentConnector(ABC):
    @abstractmethod
    def capture(self, payment_id: str, amount: Decimal, currency: str) -> dict[str, Any]: ...

    @abstractmethod
    def refund(self, payment_id: str, amount: Decimal | None = None) -> dict[str, Any]: ...


class PayoutConnector(ABC):
    @abstractmethod
    def create_payout(self, recipient_id: str, amount: Decimal, currency: str) -> dict[str, Any]: ...
