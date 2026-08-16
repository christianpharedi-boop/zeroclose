from zeroclose.policy import PolicyEngine


def test_strict_policy_requires_kyc():
    decision = PolicyEngine({"kyc": {"required": True}}).evaluate({"amount": "10", "kyc_verified": False})
    assert not decision.allowed
    assert "KYC verification is required" in decision.reasons


def test_fx_requires_explicit_rate():
    decision = PolicyEngine({"fx": {"require_explicit_rate": True}}).evaluate({"amount": "10", "source_currency": "USD", "destination_currency": "EUR", "kyc_verified": True})
    assert not decision.allowed
