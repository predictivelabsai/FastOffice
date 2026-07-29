import time

from security import sign_ticket, verify_ticket


def test_ticket_is_audience_bound(monkeypatch):
    monkeypatch.setenv("FASTOFFICE_SESSION_SECRET", "ticket-test-secret")
    token = sign_ticket({"sub": "1", "aud": "docs"}, ttl=60)
    assert verify_ticket(token, "docs")["sub"] == "1"
    assert verify_ticket(token, "sheets") is None


def test_tampered_ticket_is_rejected(monkeypatch):
    monkeypatch.setenv("FASTOFFICE_SESSION_SECRET", "ticket-test-secret")
    token = sign_ticket({"sub": "1", "aud": "docs"}, ttl=60)
    assert verify_ticket(token + "x", "docs") is None
