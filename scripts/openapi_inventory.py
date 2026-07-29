#!/usr/bin/env python3
"""Summarise sister-service OpenAPI contracts without importing their code."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPOS = ("FastMeet", "FastDocs", "FastSheets", "FastSlides", "FastInsights", "FastDrive", "FastMail")


def inventory() -> dict:
    result = {}
    for name in REPOS:
        repo = ROOT / name
        spec_path = next((repo / filename for filename in ("openapi.json", "swagger.json") if (repo / filename).exists()), None)
        if not spec_path:
            result[name] = {"error": "contract missing"}
            continue
        spec = json.loads(spec_path.read_text())
        paths = {}
        for path, operations in spec.get("paths", {}).items():
            methods = [method.upper() for method in operations if method.lower() in {"get", "post", "put", "patch", "delete"}]
            paths[path] = methods
        result[name] = {"source": str(spec_path), "title": spec.get("info", {}).get("title"), "paths": paths}
    return result


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2))
