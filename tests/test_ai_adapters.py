import pytest

import adapters
import ai


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Here is a concise workspace answer."}}]}


def test_fastpilot_uses_platform_xai_key(monkeypatch):
    observed = {}

    def fake_post(url, **kwargs):
        observed["url"] = url
        observed["authorization"] = kwargs["headers"]["Authorization"]
        observed["model"] = kwargs["json"]["model"]
        return FakeResponse()

    monkeypatch.setenv("XAI_API_KEY", "platform-test-key")
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    text, disclosure = ai.chat(
        {"provider": "xai", "model": "grok-test", "use_platform_key": 1, "encrypted_key": ""},
        [{"role": "user", "content": "Summarise this"}],
    )
    assert text.startswith("Here is")
    assert observed == {
        "url": "https://api.x.ai/v1/chat/completions",
        "authorization": "Bearer platform-test-key",
        "model": "grok-test",
    }
    assert disclosure == {"provider": "xai", "model": "grok-test"}


def test_unconnected_provider_fails_without_leaking_key():
    with pytest.raises(ai.ProviderError, match="future support"):
        ai.chat(
            {"provider": "anthropic", "model": "claude", "use_platform_key": 1, "encrypted_key": ""},
            [{"role": "user", "content": "Hello"}],
        )


def test_adapter_refuses_unsupported_create():
    with pytest.raises(ValueError, match="does not expose create"):
        adapters.execute_create("docs", {"request": "create a document"}, "key")


def test_aggregation_uses_tenant_bearer_grants(monkeypatch):
    observed = []

    def fake_request(slug, method, path, **kwargs):
        observed.append((slug, kwargs.get("access_token", "")))
        return {"data": [{"id": 1, "title": f"{slug} result", "updated_at": "2026-07-30"}]}

    monkeypatch.setattr(adapters, "request", fake_request)
    user = {"id": 7, "email": "member@example.com", "name": "Member"}
    org = {"id": 42, "name": "Tenant", "role": "member"}
    items, failures = adapters.aggregate(user, org, "result")
    assert len(items) == len(adapters.CONTRACTS)
    assert not failures
    assert all(token and token.count(".") == 1 for _, token in observed)
