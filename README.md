# ZeroClose

ZeroClose is a Python scaffold for policy-driven treasury orchestration. It provides a typed configuration layer, YAML policy evaluation, explicit FX locking, connector boundaries for Stripe and Wise, bank reconciliation, append-only audit events, a FastAPI surface, an MCP-style tool facade, and a CLI.

## Installation

```bash
cd zeroclose
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.yaml config.local.yaml
```

Provider credentials are intentionally unset in the template. Add them to `config.local.yaml` or inject them through a secret manager before integrating live provider APIs. The current Stripe and Wise connectors are deterministic scaffolding implementations and do not make external payment calls.

### VaultEq integration

ZeroClose includes a native adapter for the open-source [VaultEq repository](https://github.com/christianpharedi-boop/vaulteq). Install the repository alongside ZeroClose while VaultEq is GitHub-only:

```bash
pip install -e /path/to/vaulteq
```

Then use its SQLite-backed ledger and audit chain explicitly:

```python
from zeroclose.ledger_client import VaultEqClient

ledger = VaultEqClient("acme_corp", db_path="acme-ledger.db")
ledger.append("settlement", {"reference": "order_123", "amount": "125.00"})
assert ledger.verify_chain()
```

`VaultEqClient.post_journal()` is available when a caller needs VaultEq’s native integer-minor-unit, double-entry `PostRequest` flow. The adapter does not silently convert generic ZeroClose events into journal entries; callers must choose the native journal path for balanced accounting posts.

## Run the API

```bash
zeroclose serve acme_corp --port 8000
```

The API exposes `/health`, `/status`, `/policy/evaluate`, `/webhooks/{provider}`, `/audit/verify`, and `/audit/stream`. The status response includes `always_closed: true` as the core invariant exposed by this scaffold.

## Programmatic usage

```python
from zeroclose import TreasuryAgent

agent = TreasuryAgent(org_id="acme_corp", policies="strict")
decision = agent.authorize({
    "amount": "250.00",
    "currency": "USD",
    "kyc_verified": True,
})
print(decision.allowed)
```

## Tests

```bash
pytest -q
```

## Production integration notes

Before production use, replace connector stubs with authenticated provider clients, implement webhook signature verification, persist the ledger to a durable append-only store, enforce auditor-token authentication, add idempotency keys for all inbound events, and conduct an independent review of policy and settlement controls. No live funds movement occurs in this scaffold.
