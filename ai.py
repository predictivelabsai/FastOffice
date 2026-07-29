"""FastPilot model-provider client with safe, deterministic fallbacks."""
from __future__ import annotations

import os

import httpx

from security import decrypt_secret


PROVIDERS = {
    "xai": ("https://api.x.ai/v1/chat/completions", "XAI_API_KEY"),
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
}

SYSTEM_PROMPT = """You are FastPilot, the concise workspace assistant for FastOffice.
Help the user plan, find, analyse and draft work across FastDocs, FastSheets,
FastSlides, FastDrive, FastMeet, FastInsights, FastMail and FastCalendar.
Never claim an external action was performed. Mutations are proposed and
confirmed separately by trusted application code. Keep responses under 180 words."""


class ProviderError(RuntimeError):
    """A user-safe provider failure."""


def effective_provider(setting: dict) -> tuple[str, str, str]:
    provider = (setting.get("provider") or "xai").lower()
    model = setting.get("model") or "grok-4-1-fast-reasoning"
    key = ""
    if not setting.get("use_platform_key") and setting.get("encrypted_key"):
        key = decrypt_secret(setting["encrypted_key"])
    if not key:
        env_name = PROVIDERS.get(provider, ("", ""))[1]
        key = os.getenv(env_name, "") if env_name else ""
    return provider, model, key


def chat(setting: dict, messages: list[dict]) -> tuple[str, dict]:
    provider, model, key = effective_provider(setting)
    endpoint = PROVIDERS.get(provider, ("", ""))[0]
    if not endpoint:
        raise ProviderError(f"{provider.title()} is saved for future support but is not connected yet.")
    if not key:
        raise ProviderError(f"No {provider.upper()} API key is configured.")
    history = [
        {"role": item["role"], "content": item["content"]}
        for item in messages[-16:]
        if item.get("role") in {"user", "assistant"} and item.get("content")
    ]
    try:
        response = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *history],
                "temperature": 0.3,
            },
            timeout=35,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"].strip()
        if not content:
            raise ValueError("empty model response")
        return content, {"provider": provider, "model": model}
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError(f"FastPilot could not reach {provider.upper()} right now.") from exc
