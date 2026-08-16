from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class FXRate:
    rate_id: str
    source_currency: str
    destination_currency: str
    rate: Decimal
    locked_at: str


class FXRegistry:
    def __init__(self) -> None:
        self._rates: dict[str, FXRate] = {}

    def lock(self, rate_id: str, source_currency: str, destination_currency: str, rate: Decimal) -> FXRate:
        if rate <= 0:
            raise ValueError("FX rate must be positive")
        locked = FXRate(rate_id, source_currency, destination_currency, rate, datetime.now(timezone.utc).isoformat())
        self._rates[rate_id] = locked
        return locked

    def get(self, rate_id: str) -> FXRate:
        return self._rates[rate_id]

    def convert(self, amount: Decimal, rate_id: str) -> Decimal:
        return amount * self.get(rate_id).rate
