"""FastOffice product registry and adapter contracts."""
from __future__ import annotations

PRODUCTS = [
    {"slug": "docs", "name": "FastDocs", "label": "Documents", "description": "Write, structure and share living documents.", "accent": "#2563eb", "url": "https://docs.fastsme.com", "icon": "D"},
    {"slug": "sheets", "name": "FastSheets", "label": "Spreadsheets", "description": "Model and analyse work with safe formulas.", "accent": "#15803d", "url": "https://sheets.fastsme.com", "icon": "S"},
    {"slug": "slides", "name": "FastSlides", "label": "Presentations", "description": "Turn ideas into clear, compelling decks.", "accent": "#d97706", "url": "https://slides.fastsme.com", "icon": "P"},
    {"slug": "drive", "name": "FastDrive", "label": "Files", "description": "Store, find and govern your team's files.", "accent": "#0f766e", "url": "https://drive.fastsme.com", "icon": "F"},
    {"slug": "meet", "name": "FastMeet", "label": "Meetings", "description": "Plan meetings and carry decisions forward.", "accent": "#7c3aed", "url": "https://meet.fastsme.com", "icon": "M"},
    {"slug": "insights", "name": "FastInsights", "label": "Insights", "description": "Ask governed data and build trusted dashboards.", "accent": "#6d28d9", "url": "https://insights.fastsme.com", "icon": "I"},
    {"slug": "mail", "name": "FastMail", "label": "Mail", "description": "A calmer inbox with AI-assisted drafting.", "accent": "#dc2626", "url": "https://mail.fastsme.com", "icon": "E"},
    {"slug": "calendar", "name": "FastCal", "label": "Calendar", "description": "Coordinate calendars, availability and external bookings.", "accent": "#0891b2", "url": "https://calendar.fastsme.com", "icon": "C"},
    {"slug": "wiki", "name": "FastWiki", "label": "Knowledge", "description": "Turn team knowledge into connected, durable pages.", "accent": "#4f46e5", "url": "https://wiki.fastsme.com", "icon": "W"},
    {"slug": "pilot", "name": "FastPilot", "label": "AI workspace", "description": "Create and act across your entire workspace.", "accent": "#4f46e5", "url": "/pilot", "icon": "✦"},
]

BY_SLUG = {p["slug"]: p for p in PRODUCTS}


def proposed_action(message: str) -> tuple[str, str, dict] | None:
    """Small deterministic CRUD router used before an LLM key is configured."""
    text = message.strip()
    low = text.lower()
    product = next((p["slug"] for p in PRODUCTS if p["slug"] in low or p["name"].lower() in low), "docs")
    if any(word in low for word in ("delete", "remove", "trash")):
        return "delete", product, {"request": text}
    if any(word in low for word in ("send", "invite", "share")):
        return "external_action", product, {"request": text}
    if any(word in low for word in ("create", "draft", "make", "build", "schedule")):
        return "create", product, {"request": text}
    if any(word in low for word in ("update", "edit", "change", "rename")):
        return "update", product, {"request": text}
    return None
