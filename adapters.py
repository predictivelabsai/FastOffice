"""Tenant-aware HTTP adapter foundation for independently deployed suite apps."""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from products import BY_SLUG


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


def execute_create(slug: str, payload: dict, idempotency_key: str) -> dict:
    contract = CONTRACTS.get(slug)
    if not contract or "POST" not in contract.methods:
        raise ValueError(f"{BY_SLUG.get(slug, {'name': slug})['name']} does not expose create through its current API contract.")
    result = request(slug, "POST", contract.collection, json=payload, idempotency_key=idempotency_key)
    return result if isinstance(result, dict) else {"result": result}
