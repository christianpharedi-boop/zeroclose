import hashlib
import hmac
import json
import time
from decimal import Decimal

from fastapi.testclient import TestClient

from zeroclose.agent import TreasuryAgent
from zeroclose.api.app import create_app
from zeroclose.audit.auth import AuditorTokenAuth
from zeroclose.connectors.stripe_mapper import map_event, verify_signature


def test_stripe_signature_and_mapping():
    payload = json.dumps({"id": "evt_1", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_1", "amount": 1250, "currency": "usd"}}}).encode()
    timestamp = int(time.time())
    signature = hmac.new(b"secret", f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    assert verify_signature(payload, f"t={timestamp},v1={signature}", "secret")
    mapped = map_event(payload)
    assert mapped["provider_id"] == "pi_1"
    assert mapped["amount"] == Decimal("12.5")


def test_audit_endpoint_requires_token_when_tokens_configured():
    auth = AuditorTokenAuth()
    token = auth.issue()
    agent = TreasuryAgent("acme")
    agent.record_settlement("r1", Decimal("10"), "USD")
    client = TestClient(create_app(agent, auditor_auth=auth))
    assert client.get("/audit/verify").status_code == 401
    response = client.get("/audit/verify", headers={"X-Auditor-Token": token})
    assert response.status_code == 200
    assert response.json()["valid"] is True
