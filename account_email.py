"""Transactional email for local-account verification and password recovery."""
from __future__ import annotations

import html
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def public_url() -> str:
    return os.getenv("FASTOFFICE_PUBLIC_URL", "https://office.fastsme.com").rstrip("/")


def send_account_link(email: str, name: str, purpose: str, token: str) -> bool:
    if purpose == "verify":
        subject = "Verify your FastOffice account"
        action = "Verify account"
        link = f"{public_url()}/auth/local/verify/{token}"
    else:
        subject = "Reset your FastOffice password"
        action = "Reset password"
        link = f"{public_url()}/reset-password?token={token}"
    safe_name = html.escape(name or "there")
    safe_link = html.escape(link, quote=True)
    body = (
        f"<p>Hello {safe_name},</p>"
        f"<p><a href=\"{safe_link}\">{action}</a></p>"
        "<p>This one-time link expires automatically. If you did not request it, you can ignore this email.</p>"
    )
    return send_email(email, subject, body)


def send_email(to: str, subject: str, html_body: str) -> bool:
    token = os.getenv("POSTMARK_API_TOKEN", "")
    sender = os.getenv("FROM_EMAIL", "")
    if not token or not sender:
        return False
    payload = json.dumps({
        "From": sender,
        "To": to,
        "Subject": subject,
        "HtmlBody": html_body,
        "TextBody": re.sub(r"<[^>]+>", "", html_body),
        "MessageStream": "outbound",
    }).encode()
    request = Request(
        "https://api.postmarkapp.com/email",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Postmark-Server-Token": token,
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return response.status == 200
    except (HTTPError, URLError, TimeoutError):
        return False
