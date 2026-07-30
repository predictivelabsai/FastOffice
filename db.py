"""FastOffice persistence and domain operations."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(os.getenv("FASTOFFICE_DB", "data/fastoffice.sqlite"))

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL DEFAULT '',
  google_linked INTEGER NOT NULL DEFAULT 0,
  is_platform_admin INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS password_credentials (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  password_hash TEXT NOT NULL,
  is_verified INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_tokens (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose TEXT NOT NULL CHECK(purpose IN ('verify','reset')),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at INTEGER NOT NULL,
  used_at INTEGER,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_limits (
  subject_hash TEXT NOT NULL,
  action TEXT NOT NULL,
  window_start INTEGER NOT NULL,
  attempts INTEGER NOT NULL,
  PRIMARY KEY(subject_hash,action)
);
CREATE TABLE IF NOT EXISTS organisations (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  logo_url TEXT NOT NULL DEFAULT '',
  accent TEXT NOT NULL DEFAULT '#4f46e5',
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('owner','admin','member','viewer','guest')),
  created_at INTEGER NOT NULL,
  PRIMARY KEY(user_id, organisation_id)
);
CREATE TABLE IF NOT EXISTS invitations (
  id INTEGER PRIMARY KEY,
  organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  role TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  invited_by INTEGER NOT NULL REFERENCES users(id),
  expires_at INTEGER NOT NULL,
  accepted_at INTEGER,
  revoked_at INTEGER,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_settings (
  organisation_id INTEGER PRIMARY KEY REFERENCES organisations(id) ON DELETE CASCADE,
  provider TEXT NOT NULL DEFAULT 'xai',
  model TEXT NOT NULL DEFAULT 'grok-4-1-fast-reasoning',
  encrypted_key TEXT NOT NULL DEFAULT '',
  use_platform_key INTEGER NOT NULL DEFAULT 1,
  updated_by INTEGER REFERENCES users(id),
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY,
  organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT 'New conversation',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
  content TEXT NOT NULL,
  artifact_json TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_actions (
  id INTEGER PRIMARY KEY,
  organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  product TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  resolved_at INTEGER
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY,
  organisation_id INTEGER,
  user_id INTEGER,
  event TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_owner ON conversations(organisation_id,user_id,updated_at);
CREATE INDEX IF NOT EXISTS invitations_lookup ON invitations(organisation_id,email);
CREATE INDEX IF NOT EXISTS auth_tokens_user_purpose ON auth_tokens(user_id,purpose);
"""


def now() -> int:
    return int(time.time())


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_schema() -> None:
    with connect() as con:
        con.executescript(SCHEMA)


def slugify(value: str) -> str:
    value = "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-")
    return "-".join(filter(None, value.split("-")))[:48] or "workspace"


def ensure_user(email: str, name: str = "", google_linked: bool = False) -> dict:
    email = email.strip().lower()
    bootstrap = os.getenv("FASTOFFICE_BOOTSTRAP_ADMIN", "kaljuvee@gmail.com").strip().lower()
    stamp = now()
    with connect() as con:
        con.execute(
            """INSERT INTO users(email,name,google_linked,is_platform_admin,created_at)
               VALUES(?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET
               name=CASE WHEN excluded.name!='' THEN excluded.name ELSE users.name END,
               google_linked=MAX(users.google_linked,excluded.google_linked),
               is_platform_admin=MAX(users.is_platform_admin,excluded.is_platform_admin)""",
            (email, name.strip()[:120], int(google_linked), int(email == bootstrap), stamp),
        )
        user = dict(con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone())
        membership = con.execute("SELECT 1 FROM memberships WHERE user_id=?", (user["id"],)).fetchone()
        if not membership:
            base_name = f"{name.strip() or email.split('@')[0]}'s workspace"
            slug = slugify(base_name)
            suffix = 1
            while con.execute("SELECT 1 FROM organisations WHERE slug=?", (slug,)).fetchone():
                suffix += 1
                slug = f"{slugify(base_name)[:42]}-{suffix}"
            cur = con.execute(
                "INSERT INTO organisations(name,slug,created_at) VALUES(?,?,?)",
                (base_name, slug, stamp),
            )
            con.execute(
                "INSERT INTO memberships(user_id,organisation_id,role,created_at) VALUES(?,?,?,?)",
                (user["id"], cur.lastrowid, "owner", stamp),
            )
        return user


def normalise_email(value: str) -> str:
    value = (value or "").strip().lower()
    return value if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) else ""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$16384$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, cost, salt, expected = encoded.split("$", 3)
        if algorithm != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=base64.urlsafe_b64decode(salt),
            n=int(cost),
            r=8,
            p=1,
        )
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def auth_attempt_allowed(subject: str, action: str, limit: int, window: int) -> bool:
    stamp = now()
    subject_hash = hashlib.sha256((subject or "").encode()).hexdigest()
    with connect() as con:
        row = con.execute(
            "SELECT window_start,attempts FROM auth_limits WHERE subject_hash=? AND action=?",
            (subject_hash, action),
        ).fetchone()
        if not row or row["window_start"] <= stamp - window:
            con.execute(
                """INSERT INTO auth_limits(subject_hash,action,window_start,attempts) VALUES(?,?,?,1)
                   ON CONFLICT(subject_hash,action) DO UPDATE SET
                   window_start=excluded.window_start,attempts=1""",
                (subject_hash, action, stamp),
            )
            return True
        if row["attempts"] >= limit:
            return False
        con.execute(
            "UPDATE auth_limits SET attempts=attempts+1 WHERE subject_hash=? AND action=?",
            (subject_hash, action),
        )
        return True


def issue_auth_token(user_id: int, purpose: str, ttl: int) -> str:
    token = secrets.token_urlsafe(32)
    stamp = now()
    with connect() as con:
        con.execute(
            "UPDATE auth_tokens SET used_at=? WHERE user_id=? AND purpose=? AND used_at IS NULL",
            (stamp, user_id, purpose),
        )
        con.execute(
            """INSERT INTO auth_tokens(user_id,purpose,token_hash,expires_at,created_at)
               VALUES(?,?,?,?,?)""",
            (user_id, purpose, hashlib.sha256(token.encode()).hexdigest(), stamp + ttl, stamp),
        )
    return token


def prepare_registration(email: str, name: str, password: str) -> tuple[dict | None, str]:
    email = normalise_email(email)
    name = (name or "").strip()[:120]
    if not email or not name or len(password or "") < 10:
        return None, "Use your name, a valid email, and a password of at least 10 characters."
    if not auth_attempt_allowed(email, "register", 5, 3600):
        return None, "Too many attempts. Please try again later."
    user = ensure_user(email, name)
    with connect() as con:
        credential = con.execute(
            "SELECT is_verified FROM password_credentials WHERE user_id=?", (user["id"],)
        ).fetchone()
        if credential and credential["is_verified"]:
            return None, "An account already exists. Sign in or reset your password."
        con.execute(
            """INSERT INTO password_credentials(user_id,password_hash,is_verified,updated_at)
               VALUES(?,?,0,?) ON CONFLICT(user_id) DO UPDATE SET
               password_hash=excluded.password_hash,updated_at=excluded.updated_at""",
            (user["id"], hash_password(password), now()),
        )
    return user, ""


def local_login(email: str, password: str) -> dict | None:
    email = normalise_email(email)
    if not auth_attempt_allowed(email, "login", 10, 900):
        return None
    with connect() as con:
        row = con.execute(
            """SELECT u.*,c.password_hash,c.is_verified FROM users u
               JOIN password_credentials c ON c.user_id=u.id WHERE u.email=?""",
            (email,),
        ).fetchone()
    if not row or not row["is_verified"] or not verify_password(password or "", row["password_hash"]):
        return None
    return dict(row)


def consume_auth_token(token: str, purpose: str) -> dict | None:
    stamp = now()
    token_hash = hashlib.sha256((token or "").encode()).hexdigest()
    with connect() as con:
        row = con.execute(
            """SELECT t.id,t.user_id,u.email,u.name FROM auth_tokens t
               JOIN users u ON u.id=t.user_id
               WHERE t.token_hash=? AND t.purpose=? AND t.used_at IS NULL AND t.expires_at>?""",
            (token_hash, purpose, stamp),
        ).fetchone()
        if not row:
            return None
        con.execute("UPDATE auth_tokens SET used_at=? WHERE id=?", (stamp, row["id"]))
        if purpose == "verify":
            con.execute(
                "UPDATE password_credentials SET is_verified=1,updated_at=? WHERE user_id=?",
                (stamp, row["user_id"]),
            )
        return dict(row)


def prepare_password_reset(email: str) -> tuple[dict | None, str]:
    email = normalise_email(email)
    if not email or not auth_attempt_allowed(email, "forgot", 5, 3600):
        return None, ""
    with connect() as con:
        row = con.execute(
            """SELECT u.* FROM users u LEFT JOIN password_credentials c ON c.user_id=u.id
               WHERE u.email=? AND (u.google_linked=1 OR c.is_verified=1)""",
            (email,),
        ).fetchone()
    return (dict(row), "") if row else (None, "")


def reset_password(token: str, password: str) -> dict | None:
    if len(password or "") < 10:
        return None
    user = consume_auth_token(token, "reset")
    if not user:
        return None
    with connect() as con:
        con.execute(
            """INSERT INTO password_credentials(user_id,password_hash,is_verified,updated_at)
               VALUES(?,?,1,?) ON CONFLICT(user_id) DO UPDATE SET
               password_hash=excluded.password_hash,is_verified=1,updated_at=excluded.updated_at""",
            (user["user_id"], hash_password(password), now()),
        )
    return user


def verify_password_credential_for_google(user_id: int) -> None:
    with connect() as con:
        con.execute(
            "UPDATE password_credentials SET is_verified=1,updated_at=? WHERE user_id=?",
            (now(), user_id),
        )


def membership(user_id: int, organisation_id: int | None = None) -> dict | None:
    with connect() as con:
        params: tuple = (user_id,)
        extra = ""
        if organisation_id:
            extra = " AND o.id=?"
            params = (user_id, organisation_id)
        row = con.execute(
            """SELECT o.*,m.role FROM organisations o JOIN memberships m
               ON m.organisation_id=o.id WHERE m.user_id=?""" + extra + " ORDER BY o.id LIMIT 1",
            params,
        ).fetchone()
        return dict(row) if row else None


def members(organisation_id: int) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            """SELECT u.id,u.email,u.name,u.is_platform_admin,m.role,m.created_at
               FROM memberships m JOIN users u ON u.id=m.user_id
               WHERE m.organisation_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,u.email""",
            (organisation_id,),
        )]


def set_member_role(actor_id: int, organisation_id: int, member_id: int, role: str) -> bool:
    if role not in {"owner", "admin", "member", "viewer", "guest"}:
        return False
    actor = membership(actor_id, organisation_id)
    if not actor or actor["role"] not in {"owner", "admin"}:
        return False
    with connect() as con:
        target = con.execute(
            "SELECT role FROM memberships WHERE user_id=? AND organisation_id=?",
            (member_id, organisation_id),
        ).fetchone()
        if not target or target["role"] == "owner" or (role == "owner" and actor["role"] != "owner"):
            return False
        con.execute(
            "UPDATE memberships SET role=? WHERE user_id=? AND organisation_id=?",
            (role, member_id, organisation_id),
        )
        audit(con, organisation_id, actor_id, "member.role_changed", {"member_id": member_id, "role": role})
    return True


def create_invitation(actor_id: int, organisation_id: int, email: str, role: str) -> tuple[str, dict] | None:
    actor = membership(actor_id, organisation_id)
    email = email.strip().lower()
    if not actor or actor["role"] not in {"owner", "admin"} or role not in {"admin", "member", "viewer", "guest"} or "@" not in email:
        return None
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stamp = now()
    with connect() as con:
        con.execute(
            "UPDATE invitations SET revoked_at=? WHERE organisation_id=? AND email=? AND accepted_at IS NULL AND revoked_at IS NULL",
            (stamp, organisation_id, email),
        )
        cur = con.execute(
            """INSERT INTO invitations(organisation_id,email,role,token_hash,invited_by,expires_at,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (organisation_id, email, role, token_hash, actor_id, stamp + 7 * 86400, stamp),
        )
        audit(con, organisation_id, actor_id, "invitation.created", {"email": email, "role": role})
        invite = dict(con.execute("SELECT * FROM invitations WHERE id=?", (cur.lastrowid,)).fetchone())
    return token, invite


def accept_invitation(user_id: int, token: str) -> int | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stamp = now()
    with connect() as con:
        user = con.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
        invite = con.execute(
            """SELECT * FROM invitations WHERE token_hash=? AND accepted_at IS NULL
               AND revoked_at IS NULL AND expires_at>?""",
            (token_hash, stamp),
        ).fetchone()
        if not user or not invite or user["email"] != invite["email"]:
            return None
        con.execute(
            """INSERT INTO memberships(user_id,organisation_id,role,created_at) VALUES(?,?,?,?)
               ON CONFLICT(user_id,organisation_id) DO UPDATE SET role=excluded.role""",
            (user_id, invite["organisation_id"], invite["role"], stamp),
        )
        con.execute("UPDATE invitations SET accepted_at=? WHERE id=?", (stamp, invite["id"]))
        audit(con, invite["organisation_id"], user_id, "invitation.accepted", {"invitation_id": invite["id"]})
    return int(invite["organisation_id"])


def update_org(actor_id: int, organisation_id: int, name: str, accent: str, logo_url: str) -> bool:
    member = membership(actor_id, organisation_id)
    if not member or member["role"] not in {"owner", "admin"}:
        return False
    if not (len(accent) == 7 and accent.startswith("#")):
        accent = "#4f46e5"
    with connect() as con:
        con.execute(
            "UPDATE organisations SET name=?,accent=?,logo_url=? WHERE id=?",
            (name.strip()[:100] or member["name"], accent, logo_url.strip()[:500], organisation_id),
        )
        audit(con, organisation_id, actor_id, "organisation.branding_updated", {})
    return True


def save_provider(actor_id: int, organisation_id: int, provider: str, model: str, encrypted_key: str, platform: bool) -> bool:
    member = membership(actor_id, organisation_id)
    if not member or member["role"] not in {"owner", "admin"}:
        return False
    stamp = now()
    with connect() as con:
        existing = con.execute("SELECT encrypted_key FROM provider_settings WHERE organisation_id=?", (organisation_id,)).fetchone()
        key = encrypted_key if encrypted_key else (existing["encrypted_key"] if existing else "")
        con.execute(
            """INSERT INTO provider_settings(organisation_id,provider,model,encrypted_key,use_platform_key,updated_by,updated_at)
               VALUES(?,?,?,?,?,?,?) ON CONFLICT(organisation_id) DO UPDATE SET
               provider=excluded.provider,model=excluded.model,encrypted_key=excluded.encrypted_key,
               use_platform_key=excluded.use_platform_key,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
            (organisation_id, provider[:30], model[:100], key, int(platform), actor_id, stamp),
        )
        audit(con, organisation_id, actor_id, "ai.settings_updated", {"provider": provider, "platform": platform})
    return True


def provider_setting(organisation_id: int) -> dict:
    with connect() as con:
        row = con.execute("SELECT * FROM provider_settings WHERE organisation_id=?", (organisation_id,)).fetchone()
        return dict(row) if row else {"provider": "xai", "model": "grok-4-1-fast-reasoning", "encrypted_key": "", "use_platform_key": 1}


def conversations(user_id: int, organisation_id: int) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM conversations WHERE user_id=? AND organisation_id=? ORDER BY updated_at DESC LIMIT 30",
            (user_id, organisation_id),
        )]


def conversation(user_id: int, organisation_id: int, conversation_id: int | None = None) -> tuple[dict, list[dict]]:
    stamp = now()
    with connect() as con:
        row = None
        if conversation_id:
            row = con.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=? AND organisation_id=?",
                (conversation_id, user_id, organisation_id),
            ).fetchone()
        if not row:
            cur = con.execute(
                "INSERT INTO conversations(organisation_id,user_id,created_at,updated_at) VALUES(?,?,?,?)",
                (organisation_id, user_id, stamp, stamp),
            )
            row = con.execute("SELECT * FROM conversations WHERE id=?", (cur.lastrowid,)).fetchone()
        messages = [dict(r) for r in con.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (row["id"],)
        )]
        return dict(row), messages


def add_message(conversation_id: int, role: str, content: str, artifact: dict | None = None) -> int:
    stamp = now()
    with connect() as con:
        cur = con.execute(
            "INSERT INTO messages(conversation_id,role,content,artifact_json,created_at) VALUES(?,?,?,?,?)",
            (conversation_id, role, content, json.dumps(artifact) if artifact else None, stamp),
        )
        if role == "user":
            title = content.strip().replace("\n", " ")[:54] or "New conversation"
            con.execute(
                "UPDATE conversations SET title=CASE WHEN title='New conversation' THEN ? ELSE title END,updated_at=? WHERE id=?",
                (title, stamp, conversation_id),
            )
        else:
            con.execute("UPDATE conversations SET updated_at=? WHERE id=?", (stamp, conversation_id))
        return cur.lastrowid


def create_pending_action(user_id: int, organisation_id: int, conversation_id: int, action: str, product: str, payload: dict) -> dict:
    stamp = now()
    key = secrets.token_urlsafe(24)
    with connect() as con:
        cur = con.execute(
            """INSERT INTO pending_actions(organisation_id,user_id,conversation_id,action,product,payload_json,idempotency_key,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (organisation_id, user_id, conversation_id, action, product, json.dumps(payload), key, stamp),
        )
        row = dict(con.execute("SELECT * FROM pending_actions WHERE id=?", (cur.lastrowid,)).fetchone())
        audit(con, organisation_id, user_id, "pilot.action_proposed", {"action": action, "product": product})
        return row


def pending_action(user_id: int, organisation_id: int, action_id: int) -> dict | None:
    with connect() as con:
        row = con.execute(
            "SELECT * FROM pending_actions WHERE id=? AND user_id=? AND organisation_id=? AND status='pending'",
            (action_id, user_id, organisation_id),
        ).fetchone()
        return dict(row) if row else None


def resolve_action(user_id: int, organisation_id: int, action_id: int, status: str, result: dict | None = None) -> dict | None:
    if status not in {"completed", "cancelled", "blocked", "failed"}:
        return None
    stamp = now()
    with connect() as con:
        row = con.execute(
            "SELECT * FROM pending_actions WHERE id=? AND user_id=? AND organisation_id=? AND status='pending'",
            (action_id, user_id, organisation_id),
        ).fetchone()
        if not row:
            return None
        con.execute("UPDATE pending_actions SET status=?,resolved_at=? WHERE id=?", (status, stamp, action_id))
        audit(con, organisation_id, user_id, f"pilot.action_{status}", {"action_id": action_id, "result": result or {}})
        result = dict(row)
        result["status"] = status
        return result


def audit(con: sqlite3.Connection, organisation_id: int | None, user_id: int | None, event: str, detail: dict) -> None:
    con.execute(
        "INSERT INTO audit_events(organisation_id,user_id,event,detail_json,created_at) VALUES(?,?,?,?,?)",
        (organisation_id, user_id, event, json.dumps(detail), now()),
    )


init_schema()
