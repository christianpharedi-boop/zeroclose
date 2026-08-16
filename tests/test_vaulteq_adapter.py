from zeroclose.ledger_client import VaultEqClient


def test_vaulteq_client_persists_audit_events_and_verifies_chain(tmp_path):
    client = VaultEqClient("org_1", db_path=tmp_path / "ledger.db")
    first = client.append("policy_decision", {"id": "tx_1", "allowed": True})
    second = client.append("settlement", {"reference": "tx_1", "amount": "10.00"})
    assert first["event_type"] == "policy_decision"
    assert second["event_type"] == "settlement"
    assert len(client.snapshot()) == 3  # organization creation is audited by VaultEq
    assert client.verify_chain()
    client.close()


def test_vaulteq_client_reopens_durable_database(tmp_path):
    db_path = tmp_path / "ledger.db"
    client = VaultEqClient("org_2", db_path=db_path)
    client.append("settlement", {"reference": "r1"})
    client.close()
    reopened = VaultEqClient("org_2", db_path=db_path)
    assert any(event["event_type"] == "settlement" for event in reopened.snapshot())
    assert reopened.verify_chain()
    reopened.close()
