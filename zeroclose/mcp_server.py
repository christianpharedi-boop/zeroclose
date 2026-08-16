from __future__ import annotations

from typing import Any

from .agent import TreasuryAgent


class ZeroCloseMCP:
    """Framework-neutral MCP-style tool registry for agent orchestration."""

    def __init__(self, agent: TreasuryAgent) -> None:
        self.agent = agent

    def tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "evaluate_policy", "description": "Evaluate a transaction against treasury policy."},
            {"name": "status", "description": "Return always-closed treasury status."},
            {"name": "verify_audit_chain", "description": "Verify the append-only audit chain."},
        ]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        arguments = arguments or {}
        if name == "evaluate_policy":
            return self.agent.authorize(arguments).model_dump()
        if name == "status":
            return self.agent.status()
        if name == "verify_audit_chain":
            if hasattr(self.agent.ledger, "verify_chain"):
                return {"valid": self.agent.ledger.verify_chain(), "backend": "vaulteq"}
            from .audit.verifier import verify_chain
            return {"valid": verify_chain(self.agent.ledger.snapshot()), "backend": "simulation"}
        raise KeyError(name)
