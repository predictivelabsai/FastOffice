"""Tenant-aware HTTP adapter foundation for independently deployed suite apps."""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from products import BY_SLUG
from security import sign_ticket


@dataclass(frozen=True)
class ResourceContract:
    collection: str
    methods: frozenset[str]


CONTRACTS = {
    "docs": ResourceContract("/v1/documents", frozenset({"GET"})),
    "sheets": ResourceContract("/v1/workbooks", frozenset({"GET", "POST"})),
    "slides": ResourceContract("/v1/presentations", frozenset({"GET", "POST"})),
    "drive": ResourceContract("/v1/files", frozenset({"GET", "POST"})),
    "meet": ResourceContract("/v1/meetings", frozenset({"GET", "POST"})),
    "insights": ResourceContract("/v1/dashboards", frozenset({"GET", "POST"})),
    "mail": ResourceContract("/v1/messages", frozenset({"GET"})),
}


def service_url(slug: str) -> str:
    configured = os.getenv(f"FASTOFFICE_{slug.upper()}_API_URL", "")
    return (configured or BY_SLUG[slug]["url"]).rstrip("/")


def suite_token(slug: str, user: dict, org: dict) -> str:
    return sign_ticket({
        "sub": str(user["id"]), "email": user["email"], "name": user["name"],
        "org_id": str(org["id"]), "org_name": org["name"], "role": org["role"], "aud": slug,
    }, ttl=90)


def request(slug: str, method: str, path: str, *, access_token: str = "", json: dict | None = None,
            idempotency_key: str = "") -> dict | list:
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    service_token = os.getenv(f"FASTOFFICE_{slug.upper()}_API_TOKEN", "")
    if service_token and not access_token:
        headers["X-API-Key"] = service_token
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    response = httpx.request(method, service_url(slug) + path, headers=headers, json=json, timeout=12)
    response.raise_for_status()
    return response.json()


def execute_create(slug: str, payload: dict, idempotency_key: str, user: dict | None = None,
                   org: dict | None = None) -> dict:
    contract = CONTRACTS.get(slug)
    if not contract or "POST" not in contract.methods:
        raise ValueError(f"{BY_SLUG.get(slug, {'name': slug})['name']} does not expose create through its current API contract.")
    token = suite_token(slug, user, org) if user and org else ""
    result = request(slug, "POST", contract.collection, access_token=token, json=payload, idempotency_key=idempotency_key)
    return result if isinstance(result, dict) else {"result": result}


def aggregate(user: dict, org: dict, query: str = "", limit_per_service: int = 8) -> tuple[list[dict], list[dict]]:
    """Return tenant-scoped resources and per-service failure states."""
    items, failures = [], []
    for slug, contract in CONTRACTS.items():
        try:
            params = httpx.QueryParams({"limit": limit_per_service, **({"q": query} if query else {})})
            body = request(slug, "GET", f"{contract.collection}?{params}", access_token=suite_token(slug, user, org))
            rows = body.get("data", []) if isinstance(body, dict) else []
            product = BY_SLUG[slug]
            for row in rows:
                title = next((str(row.get(k)) for k in ("title", "name", "subject", "filename") if row.get(k)), f"{product['name']} item")
                item_id = next((row.get(k) for k in ("id", "uuid", "name") if row.get(k) is not None), "")
                items.append({
                    "product": product["name"], "slug": slug, "title": title,
                    "url": f"{product['url']}/{item_id}" if item_id else product["url"],
                    "updated": row.get("updated_at") or row.get("modified") or row.get("created_at") or "",
                })
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            failures.append({"slug": slug, "message": type(exc).__name__})
    items.sort(key=lambda item: item["updated"], reverse=True)
    return items, failures
