import json
import re


def csrf(client, path):
    response = client.get(path)
    return re.search(r'name="csrf_token"[^>]+value="([^"]+)"', response.text).group(1)


def test_landing_has_suite_and_sign_in(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Your work. Your data." in response.text
    assert "FastPilot" in response.text
    assert 'data-testid="signin-nav"' in response.text
    assert "FastCal" in response.text
    assert "FastWiki" in response.text


def test_health(client):
    response = client.get("/health")
    assert response.json() == {"status": "ok", "product": "FastOffice", "version": "0.1.0"}


def test_development_login_form_is_environment_gated(client, monkeypatch):
    response = client.get("/login")
    assert 'action="/auth/dev"' in response.text
    monkeypatch.setenv("FASTOFFICE_ENV", "production")
    response = client.get("/login")
    assert 'action="/auth/dev"' not in response.text
    assert "Continue with Google" in response.text


def test_local_registration_verification_and_login(client, app_module, monkeypatch):
    sent = {}

    def capture(email, name, purpose, token):
        sent.update(email=email, name=name, purpose=purpose, token=token)
        return True

    monkeypatch.setattr(app_module, "send_account_link", capture)
    response = client.post(
        "/auth/local/register",
        data={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "correct horse battery",
            "password_confirm": "correct horse battery",
            "next_path": "/app",
            "csrf_token": csrf(client, "/register"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert sent["purpose"] == "verify"
    assert app_module.db.local_login("ada@example.com", "correct horse battery") is None

    response = client.get(f"/auth/local/verify/{sent['token']}", follow_redirects=False)
    assert response.headers["location"] == "/app"
    client.get("/logout")
    response = client.post(
        "/auth/local/login",
        data={
            "email": "ada@example.com",
            "password": "correct horse battery",
            "next_path": "/pilot",
            "csrf_token": csrf(client, "/login"),
        },
        follow_redirects=False,
    )
    assert response.headers["location"] == "/pilot"


def test_password_reset_is_generic_and_single_use(client, app_module, monkeypatch):
    user = app_module.db.ensure_user("google-only@example.com", "Google User", google_linked=True)
    sent = {}
    monkeypatch.setattr(
        app_module,
        "send_account_link",
        lambda email, name, purpose, token: sent.update(token=token, purpose=purpose) or True,
    )
    response = client.post(
        "/auth/local/forgot",
        data={"email": user["email"], "csrf_token": csrf(client, "/forgot-password")},
        follow_redirects=False,
    )
    assert "If+an+account+exists" in response.headers["location"]
    assert sent["purpose"] == "reset"

    response = client.post(
        "/auth/local/reset",
        data={
            "token": sent["token"],
            "password": "a new secure password",
            "password_confirm": "a new secure password",
            "csrf_token": csrf(client, f"/reset-password?token={sent['token']}"),
        },
        follow_redirects=False,
    )
    assert response.headers["location"] == "/app"
    assert app_module.db.local_login(user["email"], "a new secure password")
    assert app_module.db.reset_password(sent["token"], "another secure password") is None

    client.get("/logout")
    response = client.post(
        "/auth/local/forgot",
        data={"email": "missing@example.com", "csrf_token": csrf(client, "/forgot-password")},
        follow_redirects=False,
    )
    assert "If+an+account+exists" in response.headers["location"]


def test_protected_routes_redirect(client):
    for path in ("/app", "/pilot", "/team", "/settings"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_bootstrap_admin_and_suite_home(authed, app_module):
    response = authed.get("/app")
    assert response.status_code == 200
    assert "Good to see you" in response.text
    assert "FastDocs" in response.text
    with app_module.db.connect() as con:
        user = con.execute("SELECT * FROM users WHERE email='kaljuvee@gmail.com'").fetchone()
        assert user["is_platform_admin"] == 1
        membership = con.execute("SELECT * FROM memberships WHERE user_id=?", (user["id"],)).fetchone()
        assert membership["role"] == "owner"


def test_invitation_is_email_bound(authed, app_module):
    with app_module.db.connect() as con:
        owner = con.execute("SELECT * FROM users WHERE email='kaljuvee@gmail.com'").fetchone()
    org = app_module.db.membership(owner["id"])
    token, _ = app_module.db.create_invitation(owner["id"], org["id"], "member@example.com", "member")
    other = app_module.db.ensure_user("other@example.com")
    assert app_module.db.accept_invitation(other["id"], token) is None
    invited = app_module.db.ensure_user("member@example.com")
    assert app_module.db.accept_invitation(invited["id"], token) == org["id"]
    assert app_module.db.membership(invited["id"], org["id"])["role"] == "member"


def test_member_cannot_change_branding(authed, app_module):
    with app_module.db.connect() as con:
        owner = con.execute("SELECT * FROM users WHERE email='kaljuvee@gmail.com'").fetchone()
    org = app_module.db.membership(owner["id"])
    member = app_module.db.ensure_user("member@example.com")
    with app_module.db.connect() as con:
        con.execute(
            "INSERT INTO memberships(user_id,organisation_id,role,created_at) VALUES(?,?,?,?)",
            (member["id"], org["id"], "member", app_module.db.now()),
        )
    assert app_module.db.update_org(member["id"], org["id"], "Hijacked", "#000000", "") is False


def test_provider_key_is_encrypted(authed, app_module):
    with app_module.db.connect() as con:
        owner = dict(con.execute("SELECT * FROM users WHERE email='kaljuvee@gmail.com'").fetchone())
    org = app_module.db.membership(owner["id"])
    encrypted = app_module.encrypt_secret("secret-provider-key")
    assert "secret-provider-key" not in encrypted
    assert app_module.db.save_provider(owner["id"], org["id"], "xai", "grok-test", encrypted, False)
    stored = app_module.db.provider_setting(org["id"])
    assert stored["encrypted_key"] == encrypted
    assert "secret-provider-key" not in json.dumps(stored)


def test_pilot_requires_confirmation(authed, app_module):
    page = authed.get("/pilot")
    assert "What can we move forward?" in page.text
    with app_module.db.connect() as con:
        conversation = con.execute("SELECT id FROM conversations ORDER BY id DESC").fetchone()
    response = authed.post(
        "/pilot/message",
        data={"conversation_id": conversation["id"], "message": "Delete the old FastDocs strategy brief"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = authed.get(response.headers["location"])
    assert "Confirm delete" in page.text
    with app_module.db.connect() as con:
        action = con.execute("SELECT * FROM pending_actions ORDER BY id DESC").fetchone()
        assert action["status"] == "pending"
    authed.post("/pilot/action", data={"action_id": action["id"], "decision": "cancel"})
    with app_module.db.connect() as con:
        action = con.execute("SELECT * FROM pending_actions WHERE id=?", (action["id"],)).fetchone()
        assert action["status"] == "cancelled"


def test_pilot_does_not_fake_unsupported_mutation(authed, app_module):
    authed.get("/pilot")
    with app_module.db.connect() as con:
        conversation = con.execute("SELECT id FROM conversations ORDER BY id DESC").fetchone()
    response = authed.post(
        "/pilot/message",
        data={"conversation_id": conversation["id"], "message": "Delete the old FastDocs strategy brief"},
        follow_redirects=False,
    )
    with app_module.db.connect() as con:
        action = con.execute("SELECT * FROM pending_actions ORDER BY id DESC").fetchone()
    result = authed.post(
        "/pilot/action",
        data={"action_id": action["id"], "decision": "confirm"},
        follow_redirects=True,
    )
    assert "not exposed safely" in result.text
    with app_module.db.connect() as con:
        action = con.execute("SELECT * FROM pending_actions WHERE id=?", (action["id"],)).fetchone()
        assert action["status"] == "blocked"


def test_launch_uses_canonical_subdomain_until_sso_callbacks_ready(authed):
    response = authed.get("/launch/docs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "https://docs.fastsme.com"
