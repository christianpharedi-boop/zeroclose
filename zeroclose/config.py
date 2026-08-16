from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    webhook_secret: str | None = None


class ZeroCloseConfig(BaseModel):
    org_id: str
    policies: str = "strict"
    default_currency: str = "USD"
    amount_tolerance: Decimal = Decimal("0.01")
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    policy_file: str | None = None

    @classmethod
    def from_yaml(cls, path: str | Path, *, org_id: str | None = None) -> "ZeroCloseConfig":
        data: dict[str, Any] = yaml.safe_load(Path(path).read_text()) or {}
        if org_id is not None:
            data["org_id"] = org_id
        return cls.model_validate(data)
