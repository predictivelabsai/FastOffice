"""FastOffice application entry point."""
from __future__ import annotations

import json
import os
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request as UrlRequest, urlopen

from dotenv import load_dotenv
from fasthtml.common import *
import httpx
from starlette.responses import JSONResponse, RedirectResponse

load_dotenv()

import db
import views
from account_email import send_account_link
from ai import ProviderError, chat
from adapters import aggregate, execute_create
from products import BY_SLUG, proposed_action
from security import encrypt_secret, sign_ticket


app, rt = fast_app(
    static_path=".",
    secret_key=os.getenv("FASTOFFICE_SESSION_SECRET", "fastoffice-dev-secret-change-me"),
)


def current_user(session) -> dict | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db.connect() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def context(session) -> tuple[dict, dict] | None:
    user = current_user(session)
    if not user:
        return None
    org = db.membership(user["id"], session.get("organisation_id"))
    if not org:
        return None
    session["organisation_id"] = org["id"]
    return user, org


def require_context(session):
    ctx = context(session)
    return ctx or RedirectResponse("/login", status_code=303)


def callback_uri(request) -> str:
    configured = os.getenv("GOOGLE_REDIRECT_URI", "")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    return f"{proto}://{host}/auth/google/callback"


def csrf_for(session) -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def valid_csrf(session, token: str) -> bool:
    expected = session.get("csrf_token", "")
    return bool(expected and token and secrets.compare_digest(expected, token))


@rt("/")
def get(session, auth: str = ""):
    if current_user(session):
        return RedirectResponse("/app", status_code=303)
    error = {"not-configured": "Google sign-in is not configured yet.", "failed": "Google sign-in could not be completed."}.get(auth, "")
    return views.landing_page(error)


@rt("/health")
def get():
    return JSONResponse({"status": "ok", "product": "FastOffice", "version": "0.1.0"})


@rt("/login")
def get(session, next: str = "/", error: str = "", message: str = ""):
    if current_user(session):
        return RedirectResponse(next if next.startswith("/") else "/app", status_code=303)
    dev_enabled = (
        os.getenv("FASTOFFICE_DEV_LOGIN", "true").lower() in {"1", "true", "yes"}
        and os.getenv("FASTOFFICE_ENV", "development") != "production"
    )
    return views.login_page(next, error, dev_enabled, message, csrf_for(session))


def start_session(session, user: dict, next_path: str = "/app"):
    session.clear()
    session["user_id"] = user["id"]
    org = db.membership(user["id"])
    session["organisation_id"] = org["id"]
    return RedirectResponse(next_path if next_path.startswith("/") else "/app", status_code=303)


@rt("/register")
def get(session, next: str = "/app", error: str = "", message: str = ""):
    if current_user(session):
        return RedirectResponse("/app", status_code=303)
    return views.register_page(next if next.startswith("/") else "/app", error, message, csrf_for(session))


@rt("/forgot-password")
def get(session, message: str = "", error: str = ""):
    if current_user(session):
        return RedirectResponse("/app", status_code=303)
    return views.forgot_password_page(message, error, csrf_for(session))


@rt("/reset-password")
def get(session, token: str = "", error: str = ""):
    if current_user(session):
        return RedirectResponse("/app", status_code=303)
    if not token:
        return RedirectResponse("/forgot-password?error=The+reset+link+is+invalid+or+expired", status_code=303)
    return views.reset_password_page(token, error, csrf_for(session))


@rt("/auth/local/register")
def post(session, name: str, email: str, password: str, password_confirm: str, next_path: str = "/app", csrf_token: str = ""):
    safe_next = next_path if next_path.startswith("/") else "/app"
    if not valid_csrf(session, csrf_token):
        return RedirectResponse(f"/register?next={quote(safe_next)}&error=Please+try+again", status_code=303)
    if password != password_confirm:
        return RedirectResponse(f"/register?next={quote(safe_next)}&error=Passwords+do+not+match", status_code=303)
    user, error = db.prepare_registration(email, name, password)
    if not user:
        return RedirectResponse(f"/register?next={quote(safe_next)}&error={quote(error)}", status_code=303)
    token = db.issue_auth_token(user["id"], "verify", 24 * 3600)
    if not send_account_link(user["email"], user["name"], "verify", token):
        return RedirectResponse(f"/register?next={quote(safe_next)}&error=Verification+email+could+not+be+sent", status_code=303)
    return RedirectResponse(f"/register?next={quote(safe_next)}&message=Check+your+email+to+verify+your+account", status_code=303)


@rt("/auth/local/verify/{token}")
def get(session, token: str):
    verified = db.consume_auth_token(token, "verify")
    if not verified:
        return RedirectResponse("/login?error=The+verification+link+is+invalid+or+expired", status_code=303)
    user = db.ensure_user(verified["email"], verified["name"])
    return start_session(session, user)


@rt("/auth/local/login")
def post(session, email: str, password: str, next_path: str = "/app", csrf_token: str = ""):
    if not valid_csrf(session, csrf_token):
        return RedirectResponse("/login?error=Please+try+again", status_code=303)
    user = db.local_login(email, password)
    if not user:
        return RedirectResponse(
            f"/login?next={quote(next_path if next_path.startswith('/') else '/app')}&error=Invalid+email+or+password",
            status_code=303,
        )
    return start_session(session, user, next_path)


@rt("/auth/local/forgot")
def post(session, email: str, csrf_token: str = ""):
    if not valid_csrf(session, csrf_token):
        return RedirectResponse("/forgot-password?error=Please+try+again", status_code=303)
    user, _ = db.prepare_password_reset(email)
    if user:
        token = db.issue_auth_token(user["id"], "reset", 3600)
        send_account_link(user["email"], user["name"], "reset", token)
    return RedirectResponse(
        "/forgot-password?message=If+an+account+exists,+a+reset+link+is+on+its+way",
        status_code=303,
    )


@rt("/auth/local/reset")
def post(session, token: str, password: str, password_confirm: str, csrf_token: str = ""):
    if not valid_csrf(session, csrf_token):
        return RedirectResponse(f"/reset-password?token={quote(token)}&error=Please+try+again", status_code=303)
    if password != password_confirm or len(password or "") < 10:
        return RedirectResponse(
            f"/reset-password?token={quote(token)}&error=Passwords+must+match+and+contain+at+least+10+characters",
            status_code=303,
        )
    reset_user = db.reset_password(token, password)
    if not reset_user:
        return RedirectResponse("/forgot-password?error=The+reset+link+is+invalid+or+expired", status_code=303)
    user = db.ensure_user(reset_user["email"], reset_user["name"])
    return start_session(session, user)


@rt("/auth/dev")
def post(session, email: str, next_path: str = "/"):
    if os.getenv("FASTOFFICE_DEV_LOGIN", "true").lower() not in {"1", "true", "yes"} or os.getenv("FASTOFFICE_ENV", "development") == "production":
        return RedirectResponse("/login?error=Development+sign-in+is+disabled", status_code=303)
    user = db.ensure_user(email, email.split("@")[0].replace(".", " ").title())
    return start_session(session, user, next_path)


@rt("/auth/google")
def get(session, request, next: str = "/app"):
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        return RedirectResponse("/?auth=not-configured", status_code=303)
    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state
    session["auth_next"] = next if next.startswith("/") else "/app"
    query = urlencode({
        "client_id": client_id,
        "redirect_uri": callback_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=303)


@rt("/auth/google/callback")
def get(session, request, code: str = "", state: str = "", error: str = ""):
    expected = session.pop("google_oauth_state", None)
    if error or not code or not expected or not secrets.compare_digest(state, expected):
        return RedirectResponse("/?auth=failed", status_code=303)
    data = urlencode({
        "code": code,
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": callback_uri(request),
        "grant_type": "authorization_code",
    }).encode()
    try:
        token = json.loads(urlopen(UrlRequest("https://oauth2.googleapis.com/token", data=data), timeout=20).read())
        info_req = UrlRequest("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token['access_token']}"})
        info = json.loads(urlopen(info_req, timeout=20).read())
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError):
        return RedirectResponse("/?auth=failed", status_code=303)
    email = (info.get("email") or "").strip().lower()
    if not email or info.get("email_verified") is False:
        return RedirectResponse("/?auth=failed", status_code=303)
    domains = {x.strip().lower() for x in os.getenv("GOOGLE_ALLOWED_DOMAINS", "").split(",") if x.strip()}
    emails = {x.strip().lower() for x in os.getenv("GOOGLE_ALLOWED_EMAILS", "").split(",") if x.strip()}
    if domains or emails:
        if email not in emails and email.rsplit("@", 1)[-1] not in domains:
            return RedirectResponse("/login?error=This+Google+account+is+not+authorised", status_code=303)
    user = db.ensure_user(email, info.get("name") or email, google_linked=True)
    db.verify_password_credential_for_google(user["id"])
    next_path = session.pop("auth_next", "/app")
    return start_session(session, user, next_path)


@rt("/logout")
def get(session):
    session.clear()
    return RedirectResponse("/", status_code=303)


@rt("/app")
def get(session):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    recent, failures = aggregate(user, org, limit_per_service=3)
    return views.suite_home(user, org, recent[:9], failures)


@rt("/search")
def get(session, q: str = ""):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    items, failures = aggregate(user, org, q.strip(), limit_per_service=20) if q.strip() else ([], [])
    return views.search_page(user, org, q.strip(), items, failures)


@rt("/launch/{slug}")
def get(session, slug: str):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    product = BY_SLUG.get(slug)
    if not product or product.get("coming_soon"):
        return RedirectResponse("/app", status_code=303)
    ticket = sign_ticket({
        "sub": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "org_id": str(org["id"]),
        "org_name": org["name"],
        "role": org["role"],
        "aud": slug,
    })
    # Product callback support is rolled out service by service. Until then,
    # canonical product URLs remain usable with their standalone login.
    if os.getenv("FASTOFFICE_SUITE_SSO_READY", "").lower() in {"1", "true", "yes"}:
        return RedirectResponse(f"{product['url']}/auth/suite/callback?ticket={quote(ticket)}", status_code=303)
    return RedirectResponse(product["url"], status_code=303)


@rt("/pilot")
def get(session, conversation: int = 0, new: int = 0):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    current, messages = db.conversation(user["id"], org["id"], None if new else conversation or None)
    rows = db.conversations(user["id"], org["id"])
    return views.pilot_page(user, org, rows, current, messages)


@rt("/pilot/message")
def post(session, conversation_id: int, message: str):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    current, previous = db.conversation(user["id"], org["id"], conversation_id)
    db.add_message(current["id"], "user", message.strip())
    proposal = proposed_action(message)
    if proposal:
        action, product_slug, payload = proposal
        pending = db.create_pending_action(user["id"], org["id"], current["id"], action, product_slug, payload)
        product = BY_SLUG.get(product_slug, BY_SLUG["docs"])
        destructive = action in {"delete", "external_action"}
        artifact = {
            "kind": "action_confirmation",
            "action": pending["id"],
            "product": product["name"],
            "title": f"Confirm {action.replace('_', ' ')}",
            "summary": message.strip()[:140],
            "detail": "This is a permission-scoped FastPilot proposal. The external product adapter will execute it only after confirmation.",
            "effect": f"{action.title()} an item in {product['name']}" + (" and notify external recipients." if destructive else "."),
        }
        response = f"I prepared a {product['name']} action. Review the details in the canvas before I apply it."
        db.add_message(current["id"], "assistant", response, artifact)
    else:
        try:
            answer, disclosure = chat(
                db.provider_setting(org["id"]),
                [*previous, {"role": "user", "content": message.strip()}],
            )
            artifact = {
                "kind": "ai_response",
                "product": "FastPilot",
                "title": "AI response",
                "summary": f"Processed by {disclosure['provider'].upper()}",
                "detail": f"Model: {disclosure['model']}. No external workspace mutation was performed.",
            }
            db.add_message(current["id"], "assistant", answer, artifact)
        except ProviderError as exc:
            artifact = {
                "kind": "provider_error",
                "product": "FastPilot",
                "title": "Provider connection needed",
                "summary": str(exc),
                "detail": "An administrator can select the hosted xAI connection or save a bring-your-own key in Settings.",
            }
            db.add_message(current["id"], "assistant", str(exc), artifact)
    return RedirectResponse(f"/pilot?conversation={current['id']}", status_code=303)


@rt("/pilot/action")
def post(session, action_id: int, decision: str):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    pending = db.pending_action(user["id"], org["id"], action_id)
    if not pending:
        return RedirectResponse("/pilot", status_code=303)
    if decision != "confirm":
        result = db.resolve_action(user["id"], org["id"], action_id, "cancelled")
    elif pending["action"] != "create":
        result = db.resolve_action(user["id"], org["id"], action_id, "blocked")
    else:
        try:
            payload = json.loads(pending["payload_json"])
            external = execute_create(pending["product"], payload, pending["idempotency_key"], user, org)
            result = db.resolve_action(user["id"], org["id"], action_id, "completed", external)
        except (ValueError, httpx.HTTPError, HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            result = db.resolve_action(user["id"], org["id"], action_id, "failed", {"error": str(exc)})
    if not result:
        return RedirectResponse("/pilot", status_code=303)
    message = {
        "completed": "Action completed through the product API and recorded.",
        "cancelled": "Action cancelled. Nothing was changed.",
        "blocked": "This action is not exposed safely by the product API yet, so nothing was changed.",
        "failed": "The product API could not complete this action. Nothing was marked as completed.",
    }[result["status"]]
    db.add_message(result["conversation_id"], "assistant", message)
    return RedirectResponse(f"/pilot?conversation={result['conversation_id']}", status_code=303)


@rt("/team")
def get(session, message: str = ""):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    return views.team_page(user, org, db.members(org["id"]), message)


@rt("/team/invite")
def post(session, email: str, role: str):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    result = db.create_invitation(user["id"], org["id"], email, role)
    if not result:
        return RedirectResponse("/team?message=Invitation+could+not+be+created", status_code=303)
    token, invite = result
    public_url = os.getenv("FASTOFFICE_PUBLIC_URL", "http://localhost:5020").rstrip("/")
    invite_url = f"{public_url}/invite/{token}"
    sent = send_invitation(email, org["name"], invite_url, role)
    message = "Invitation sent" if sent else f"Invitation created. Development link: {invite_url}"
    return RedirectResponse(f"/team?message={quote(message)}", status_code=303)


def send_invitation(email: str, org_name: str, invite_url: str, role: str) -> bool:
    token = os.getenv("POSTMARK_API_TOKEN", "")
    if not token:
        return False
    payload = json.dumps({
        "From": os.getenv("FROM_EMAIL", "info@fastsme.com"),
        "To": email,
        "Subject": f"Join {org_name} on FastOffice",
        "TextBody": f"You were invited as {role}. Accept your invitation: {invite_url}",
        "HtmlBody": f"<p>You were invited to <strong>{org_name}</strong> as {role}.</p><p><a href=\"{invite_url}\">Accept invitation</a></p>",
        "MessageStream": "outbound",
    }).encode()
    try:
        request = UrlRequest("https://api.postmarkapp.com/email", data=payload, headers={"X-Postmark-Server-Token": token, "Content-Type": "application/json"})
        with urlopen(request, timeout=15) as response:
            return response.status < 300
    except (HTTPError, URLError, TimeoutError):
        return False


@rt("/invite/{token}")
def get(session, token: str):
    user = current_user(session)
    if not user:
        session["invite_token"] = token
        return RedirectResponse(f"/login?next=/invite/{quote(token)}", status_code=303)
    organisation_id = db.accept_invitation(user["id"], token)
    if organisation_id:
        session["organisation_id"] = organisation_id
        return RedirectResponse("/app", status_code=303)
    return RedirectResponse("/team?message=Invitation+is+invalid,+expired,+or+belongs+to+another+email", status_code=303)


@rt("/team/role")
def post(session, member_id: int, role: str):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    db.set_member_role(user["id"], org["id"], member_id, role)
    return RedirectResponse("/team", status_code=303)


@rt("/settings")
def get(session, message: str = ""):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    return views.settings_page(user, org, db.provider_setting(org["id"]), message)


@rt("/settings/branding")
def post(session, name: str, accent: str = "#4f46e5", logo_url: str = ""):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    ok = db.update_org(user["id"], org["id"], name, accent, logo_url)
    return RedirectResponse("/settings?message=" + ("Branding+saved" if ok else "Not+authorised"), status_code=303)


@rt("/settings/provider")
def post(session, provider: str, model: str, api_key: str = "", use_platform: str = ""):
    ctx = require_context(session)
    if isinstance(ctx, RedirectResponse):
        return ctx
    user, org = ctx
    encrypted = encrypt_secret(api_key.strip()) if api_key.strip() else ""
    ok = db.save_provider(user["id"], org["id"], provider, model, encrypted, use_platform == "yes")
    return RedirectResponse("/settings?message=" + ("AI+settings+saved" if ok else "Not+authorised"), status_code=303)


if __name__ == "__main__":
    serve(port=int(os.getenv("FASTOFFICE_PORT", "5020")))
