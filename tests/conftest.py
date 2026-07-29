import importlib

import pytest
from starlette.testclient import TestClient


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTOFFICE_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("FASTOFFICE_DEV_LOGIN", "true")
    monkeypatch.setenv("FASTOFFICE_ENV", "test")
    monkeypatch.setenv("FASTOFFICE_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("FASTOFFICE_BOOTSTRAP_ADMIN", "kaljuvee@gmail.com")
    import db
    import app
    importlib.reload(db)
    importlib.reload(app)
    return app


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app)


@pytest.fixture()
def authed(client):
    response = client.post(
        "/auth/dev",
        data={"email": "kaljuvee@gmail.com", "next_path": "/app"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client
