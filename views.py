"""FastOffice HTML views."""
from __future__ import annotations

import json
from urllib.parse import quote

from fasthtml.common import *

from products import PRODUCTS


FAVICON = "data:image/svg+xml," + quote(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="18" fill="#4f46e5"/><path d="M18 16h30v10H29v8h16v10H29v12H18z" fill="white"/><circle cx="49" cy="49" r="9" fill="#a5b4fc"/><path d="m49 44 1.6 3.4L54 49l-3.4 1.6L49 54l-1.6-3.4L44 49l3.4-1.6z" fill="#312e81"/></svg>""",
    safe="",
)


def head(title: str, description: str = "Your work. Your data. Your freedom.") -> Head:
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1, viewport-fit=cover"),
        Meta(name="theme-color", content="#4f46e5"),
        Meta(name="description", content=description),
        Title(f"{title} · FastOffice"),
        Link(rel="icon", href=FAVICON, type="image/svg+xml"),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap"),
        Link(rel="stylesheet", href="/static/site.css"),
    )


def logo(href: str = "/", compact: bool = False):
    return A(
        Span("F", cls="brand-mark"),
        None if compact else Span("FastOffice", cls="brand-name"),
        href=href,
        cls="brand",
        aria_label="FastOffice home",
    )


def public_nav():
    return Nav(
        Div(
            logo(),
            Div(
                A("Products", href="#products", cls="nav-link"),
                A("FastPilot", href="#pilot", cls="nav-link"),
                A("Open source", href="#freedom", cls="nav-link"),
                A("Sign In", href="/login", cls="btn btn-quiet", data_testid="signin-nav"),
                cls="nav-actions",
            ),
            cls="nav-inner",
        ),
        cls="public-nav",
    )


def landing_page(auth_error: str = ""):
    cards = [
        Article(
            Div(Span(p["icon"], cls="product-icon", style=f"--product:{p['accent']}"), Span("Coming soon", cls="soon") if p.get("coming_soon") else None, cls="product-card-top"),
            H3(p["name"]),
            P(p["description"]),
            A("Explore " + p["label"], href=p["url"], cls="product-link", target="_blank" if p["url"].startswith("http") else None, rel="noopener" if p["url"].startswith("http") else None),
            cls="product-card",
            style=f"--product:{p['accent']}",
        )
        for p in PRODUCTS
    ]
    return Html(
        head("Open-source workspace"),
        Body(
            public_nav(),
            Main(
                Section(
                    Div(
                        Span("One open workspace", cls="eyebrow"),
                        H1("Your work. Your data.", Br(), Span("Your freedom.", cls="hero-accent")),
                        P("Discover the freedom of an open-source workspace—documents, spreadsheets, presentations, files, meetings, mail, calendars, insights and AI in one connected suite.", cls="hero-copy"),
                        Div(
                            A("Sign In", href="/login", cls="btn btn-primary", data_testid="signin-hero"),
                            A("Explore the suite", href="#products", cls="btn btn-secondary"),
                            cls="hero-actions",
                        ),
                        P(auth_error, cls="notice error") if auth_error else None,
                        Div(
                            Span("Open source"),
                            Span("Self-hostable"),
                            Span("AI-native"),
                            Span("No per-seat lock-in"),
                            cls="trust-row",
                        ),
                        cls="hero-content",
                    ),
                    Div(
                        Div(
                            Div(Span("F", cls="mini-logo"), Span("FastOffice"), Span("9 apps", cls="demo-muted"), cls="demo-bar"),
                            Div(
                                Div(
                                    Span("Good morning", cls="demo-kicker"),
                                    H2("Where will your ideas go today?"),
                                    Div(Span("Ask FastPilot anything…"), Span("↑", cls="send-dot"), cls="demo-prompt"),
                                    Div(*[Span(x, cls="demo-chip") for x in ("Draft a brief", "Analyse sales", "Plan a meeting")], cls="demo-chips"),
                                    cls="demo-main",
                                ),
                                Div(
                                    Span("Recent"),
                                    *[
                                        Div(Span(p["icon"], cls="recent-icon", style=f"--product:{p['accent']}"), Div(Strong(title), Small(label)), cls="recent-row")
                                        for p, title, label in (
                                            (PRODUCTS[0], "Q3 strategy brief", "FastDocs · 12 min ago"),
                                            (PRODUCTS[1], "Operating plan", "FastSheets · Yesterday"),
                                            (PRODUCTS[2], "Board update", "FastSlides · Monday"),
                                        )
                                    ],
                                    cls="demo-recent",
                                ),
                                cls="demo-grid",
                            ),
                            cls="hero-window",
                        ),
                        Div("✦", cls="floating-spark spark-one"),
                        Div("●", cls="floating-spark spark-two"),
                        cls="hero-visual",
                    ),
                    cls="hero",
                ),
                Section(
                    Div(
                        Span("Everything your team needs", cls="eyebrow"),
                        H2("A complete workspace,", Br(), "without the closed ecosystem."),
                        P("Use one focused product or bring the whole suite together with shared identity, permissions and FastPilot.", cls="section-copy"),
                        cls="section-heading",
                    ),
                    Div(*cards, cls="product-grid"),
                    id="products",
                    cls="section products",
                ),
                Section(
                    Div(
                        Span("FastPilot", cls="eyebrow light"),
                        H2("Ask. Create. Act."),
                        P("FastPilot works across your suite—grounded in the files and permissions you already have. Every material action stays visible and under your control."),
                        Div(
                            Div(Span("01"), H3("Understand"), P("Find and connect knowledge across mail, files, meetings and data.")),
                            Div(Span("02"), H3("Create"), P("Draft documents, workbooks, decks, events and messages from a conversation.")),
                            Div(Span("03"), H3("Act safely"), P("Preview, confirm and audit changes before they reach your workspace.")),
                            cls="pilot-features",
                        ),
                        A("Meet FastPilot", href="/login?next=/pilot", cls="btn btn-light"),
                        cls="pilot-copy",
                    ),
                    Div(
                        Div(logo(compact=True), Button("+ New chat", cls="pilot-new"), P("HISTORY", cls="pilot-label"), P("Quarterly planning"), P("Customer research"), P("TEAM WORKFLOWS", cls="pilot-label"), P("Executive brief"), cls="pilot-left"),
                        Div(
                            Div(Strong("FastPilot"), Span("Workspace agent"), cls="pilot-chat-head"),
                            Div(Span("✦", cls="pilot-orb"), H3("What can we move forward?"), P("I can create, analyse and update work across FastOffice."), cls="pilot-welcome"),
                            Div(Span("Create an executive brief from our Q3 results"), Span("↑", cls="send-dot"), cls="pilot-input"),
                            cls="pilot-centre",
                        ),
                        Div(Span("DYNAMIC CANVAS", cls="pilot-label"), H3("Executive brief"), Div(cls="canvas-line wide"), Div(cls="canvas-line"), Div(cls="canvas-chart"), Div(Button("Cancel", cls="canvas-cancel"), Button("Create document", cls="canvas-confirm"), cls="canvas-actions"), cls="pilot-right"),
                        cls="pilot-preview",
                    ),
                    id="pilot",
                    cls="pilot-section",
                ),
                Section(
                    Div(Span("Built for ownership", cls="eyebrow"), H2("Freedom is a feature."), P("Run FastOffice in our cloud or on your infrastructure. Bring your identity, your AI provider and your brand."), cls="freedom-heading"),
                    Div(
                        Article(Span("⌂"), H3("Host it your way"), P("Use the managed FastSME cloud or deploy the same open-source stack yourself.")),
                        Article(Span("◇"), H3("Make it yours"), P("Add your logo, colours, domain and the products your organisation needs.")),
                        Article(Span("◉"), H3("Keep control"), P("Open APIs, exportable data and transparent permissions prevent platform lock-in.")),
                        cls="freedom-grid",
                    ),
                    id="freedom",
                    cls="section freedom",
                ),
                Section(
                    H2("A workspace should expand your possibilities,", Br(), "not your licence bill."),
                    A("Sign In to FastOffice", href="/login", cls="btn btn-primary"),
                    cls="closing",
                ),
            ),
            Footer(
                Div(logo(), P("Open-source tools for ambitious teams.")),
                Div(A("GitHub", href="https://github.com/predictivelabsai/FastOffice"), A("FastSME", href="https://fastsme.com"), A("Privacy", href="#")),
                P("© 2026 Predictive Labs Ltd"),
                cls="footer",
            ),
        ),
    )


def login_page(next_path: str = "/", error: str = "", dev_enabled: bool = False):
    return Html(
        head("Sign in"),
        Body(
            Div(
                A("← Back", href="/", cls="back-link"),
                Div(
                    logo(),
                    Span("ONE CONNECTED WORKSPACE", cls="eyebrow"),
                    H1("Welcome to your work."),
                    P("Sign in once to open every FastOffice product."),
                    Div(
                        Div(Span("D", style="--product:#2563eb"), Span("S", style="--product:#15803d"), Span("P", style="--product:#d97706"), Span("✦", style="--product:#4f46e5"), cls="login-icons"),
                        cls="login-art",
                    ),
                    cls="login-story",
                ),
                Div(
                    Div(
                        H2("Sign in to FastOffice"),
                        P("Continue with your organisation account."),
                        A(
                            NotStr('<svg width="18" height="18" viewBox="0 0 18 18"><path d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.69-3.88 2.69-6.62z" fill="#4285F4"/><path d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.34 0-4.33-1.58-5.04-3.71H.96v2.33A9 9 0 0 0 9 18z" fill="#34A853"/><path d="M3.96 10.71A5.4 5.4 0 0 1 3.68 9c0-.59.1-1.17.28-1.71V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.04l3-2.33z" fill="#FBBC05"/><path d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58A8.64 8.64 0 0 0 9 0 9 9 0 0 0 .96 4.96l3 2.33C4.67 5.16 6.66 3.58 9 3.58z" fill="#EA4335"/></svg>'),
                            "Continue with Google",
                            href=f"/auth/google?next={quote(next_path)}",
                            cls="google-button",
                        ),
                        Div(Span(), Small("or, for local development"), Span(), cls="divider") if dev_enabled else None,
                        Form(
                            Label("Email", Input(name="email", type="email", value="kaljuvee@gmail.com", autocomplete="email", required=True)),
                            Input(name="next_path", type="hidden", value=next_path),
                            Button("Continue", type="submit", cls="btn btn-primary full"),
                            method="post",
                            action="/auth/dev",
                            cls="login-form",
                        ) if dev_enabled else None,
                        P(error, cls="notice error") if error else None,
                        Small("By continuing, you agree to the deployment's terms and privacy policy.", cls="login-terms"),
                        cls="login-card",
                    ),
                    cls="login-panel",
                ),
                cls="login-layout",
            ),
            cls="login-body",
        ),
    )


def app_header(user: dict, org: dict, active: str = "home"):
    return Header(
        Div(
            logo("/app"),
            Nav(
                A("Home", href="/app", cls="active" if active == "home" else ""),
                A("FastPilot", href="/pilot", cls="active" if active == "pilot" else ""),
                A("Team", href="/team", cls="active" if active == "team" else ""),
                A("Settings", href="/settings", cls="active" if active == "settings" else ""),
                cls="app-nav",
            ),
            Div(
                Span(org["name"], cls="org-pill"),
                Span((user["name"] or user["email"])[0].upper(), cls="avatar"),
                A("Sign out", href="/logout", cls="signout"),
                cls="account",
            ),
            cls="app-header-inner",
        ),
        cls="app-header",
    )


def suite_home(user: dict, org: dict):
    products = [
        A(
            Div(Span(p["icon"], cls="app-icon", style=f"--product:{p['accent']}"), Span("Soon", cls="soon") if p.get("coming_soon") else Span("↗", cls="open-arrow")),
            H3(p["name"]),
            P(p["description"]),
            href="/pilot" if p["slug"] == "pilot" else f"/launch/{p['slug']}",
            cls="app-card",
            style=f"--product:{p['accent']}",
            data_testid=f"app-{p['slug']}",
        )
        for p in PRODUCTS
    ]
    return Html(
        head("Home"),
        Body(
            app_header(user, org),
            Main(
                Section(
                    Div(Span("WORKSPACE", cls="eyebrow"), H1(f"Good to see you, {(user['name'] or user['email'].split('@')[0]).split()[0]}."), P("What would you like to move forward today?")),
                    A(Span("✦", cls="ask-icon"), Div(Strong("Ask FastPilot"), Small("Create, analyse or update work across your suite")), Span("→"), href="/pilot", cls="ask-pilot"),
                    cls="dashboard-hero",
                ),
                Section(H2("Your apps"), Div(*products, cls="app-grid"), cls="dashboard-section"),
                Section(
                    Div(H2("Recent work"), Button("View all", cls="text-button")),
                    Div(
                        Div(Span("D", cls="file-type blue"), Div(Strong("Q3 strategy brief"), Small("FastDocs · Edited 12 minutes ago")), Span("⋯")),
                        Div(Span("S", cls="file-type green"), Div(Strong("Operating plan"), Small("FastSheets · Edited yesterday")), Span("⋯")),
                        Div(Span("P", cls="file-type amber"), Div(Strong("Board update"), Small("FastSlides · Edited Monday")), Span("⋯")),
                        cls="recent-list",
                    ),
                    cls="dashboard-section recent-section",
                ),
                cls="dashboard",
            ),
        ),
    )


def pilot_page(user: dict, org: dict, conversations: list[dict], current: dict, messages: list[dict]):
    history = [A(c["title"], href=f"/pilot?conversation={c['id']}", cls="history-item active" if c["id"] == current["id"] else "history-item") for c in conversations]
    rendered_messages = []
    last_artifact = None
    for message in messages:
        artifact = json.loads(message["artifact_json"]) if message.get("artifact_json") else None
        if artifact:
            last_artifact = artifact
        rendered_messages.append(
            Div(
                Span("You" if message["role"] == "user" else "✦", cls="message-avatar"),
                Div(P(message["content"]), cls="message-bubble"),
                cls=f"message {message['role']}",
            )
        )
    if not rendered_messages:
        rendered_messages.append(
            Div(
                Span("✦", cls="pilot-big-orb"),
                H1("What can we move forward?"),
                P("Create, analyse and update work across your FastOffice suite."),
                Div(
                    *[
                        Button(title, Small(body), onclick=f"pilotSuggest({json.dumps(prompt)})", cls="suggestion-card")
                        for title, body, prompt in (
                            ("Draft a brief", "Turn notes into a structured FastDocs document.", "Create a FastDocs executive brief from my latest notes"),
                            ("Analyse a workbook", "Find patterns and explain the numbers.", "Analyse my FastSheets operating plan"),
                            ("Plan a meeting", "Create an agenda and coordinate the team.", "Schedule a FastMeet planning meeting and invite my team"),
                            ("Build a deck", "Create a presentation from existing work.", "Build a FastSlides deck from my Q3 strategy brief"),
                        )
                    ],
                    cls="suggestion-grid",
                ),
                cls="pilot-empty",
            )
        )
    return Html(
        head("FastPilot"),
        Body(
            Div(
                Aside(
                    Div(logo("/app"), Button("×", cls="mobile-close", onclick="togglePilotMenu()"), cls="pilot-brand-row"),
                    A("+ New conversation", href="/pilot?new=1", cls="pilot-new-button"),
                    P("HISTORY", cls="pilot-section-label"),
                    Div(*history, cls="pilot-history"),
                    P("WORKSPACE", cls="pilot-section-label"),
                    *[A(Span(p["icon"], style=f"--product:{p['accent']}"), p["name"], href="/pilot" if p["slug"] == "pilot" else f"/launch/{p['slug']}", cls="pilot-app-link") for p in PRODUCTS[:-1]],
                    Div(Span((user["name"] or user["email"])[0].upper(), cls="avatar"), Div(Strong(user["name"] or user["email"]), Small(org["name"])), cls="pilot-user"),
                    id="pilot-left",
                    cls="pilot-app-left",
                ),
                Main(
                    Header(Button("☰", cls="mobile-menu", onclick="togglePilotMenu()"), Div(Strong("FastPilot"), Small("Workspace agent")), Div(A("Home", href="/app"), Button("Canvas", onclick="toggleCanvas()")), cls="pilot-app-header"),
                    Div(*rendered_messages, id="pilot-messages", cls="pilot-messages"),
                    Form(
                        Textarea(name="message", placeholder="Ask FastPilot to create, find, analyse or update…", rows="1", required=True, id="pilot-input"),
                        Input(name="conversation_id", type="hidden", value=current["id"]),
                        Div(Span("FastOffice workspace"), Button("↑", type="submit", cls="pilot-send"), cls="pilot-compose-foot"),
                        method="post",
                        action="/pilot/message",
                        cls="pilot-compose",
                        id="pilot-form",
                    ),
                    cls="pilot-app-centre",
                ),
                Aside(canvas_content(last_artifact), id="pilot-canvas", cls="pilot-app-canvas open" if last_artifact else "pilot-app-canvas"),
                Div(id="pilot-overlay", cls="pilot-overlay", onclick="closePilotPanels()"),
                cls="pilot-app",
            ),
            Script(src="/static/app.js"),
        ),
    )


def canvas_content(artifact: dict | None):
    if not artifact:
        return (
            Div(Button("×", onclick="toggleCanvas()", cls="canvas-close"), cls="canvas-head"),
            Div(Span("◇", cls="empty-canvas-icon"), H3("Your canvas is ready"), P("FastPilot will show documents, tables, charts and proposed actions here."), cls="empty-canvas"),
        )
    action = artifact.get("action")
    return (
        Div(Div(Span("PROPOSED ACTION", cls="pilot-section-label"), H3(artifact.get("title", "Review action"))), Button("×", onclick="toggleCanvas()", cls="canvas-close"), cls="canvas-head"),
        Div(
            Span(artifact.get("product", "FastOffice"), cls="artifact-product"),
            H2(artifact.get("summary", "Review this action")),
            P(artifact.get("detail", "")),
            Div(Strong("FastPilot will"), P(artifact.get("effect", "Apply the requested change using your current permissions.")), cls="effect-card"),
            Div(
                Form(Input(name="action_id", type="hidden", value=action), Button("Cancel", name="decision", value="cancel", cls="btn btn-secondary"), Button("Confirm action", name="decision", value="confirm", cls="btn btn-primary"), method="post", action="/pilot/action", cls="confirm-form"),
                cls="canvas-bottom",
            ),
            cls="artifact-body",
        ),
    )


def team_page(user: dict, org: dict, member_rows: list[dict], message: str = ""):
    can_admin = org["role"] in {"owner", "admin"}
    rows = [
        Tr(
            Td(Div(Span((m["name"] or m["email"])[0].upper(), cls="avatar small"), Div(Strong(m["name"] or m["email"]), Small(m["email"])), cls="member-cell")),
            Td(Span(m["role"].title(), cls=f"role role-{m['role']}")),
            Td(
                Form(
                    Input(name="member_id", type="hidden", value=m["id"]),
                    Select(*[Option(r.title(), value=r, selected=r == m["role"]) for r in ("admin", "member", "viewer", "guest")], name="role", disabled=(m["role"] == "owner" or not can_admin), onchange="this.form.submit()"),
                    method="post",
                    action="/team/role",
                ) if m["role"] != "owner" else Span("Workspace owner", cls="muted")
            ),
        )
        for m in member_rows
    ]
    return Html(
        head("Team"),
        Body(
            app_header(user, org, "team"),
            Main(
                Div(Div(Span("ORGANISATION", cls="eyebrow"), H1("Team and access"), P("Invite people and control what they can do across FastOffice.")), cls="page-heading"),
                P(message, cls="notice ok") if message else None,
                Section(
                    Div(H2("Members"), Span(f"{len(member_rows)} people", cls="count-pill"), cls="section-title-row"),
                    Table(Thead(Tr(Th("Person"), Th("Role"), Th("Access"))), Tbody(*rows), cls="members-table"),
                    cls="settings-card",
                ),
                Section(
                    H2("Invite a team member"),
                    P("Invitations expire after seven days and are bound to the recipient's email."),
                    Form(
                        Label("Email address", Input(name="email", type="email", placeholder="name@company.com", required=True)),
                        Label("Role", Select(*[Option(r.title(), value=r) for r in ("member", "admin", "viewer", "guest")], name="role")),
                        Button("Send invitation", type="submit", cls="btn btn-primary", disabled=not can_admin),
                        method="post",
                        action="/team/invite",
                        cls="invite-form",
                    ),
                    cls="settings-card",
                ),
                cls="settings-page",
            ),
        ),
    )


def settings_page(user: dict, org: dict, provider: dict, message: str = ""):
    can_admin = org["role"] in {"owner", "admin"}
    return Html(
        head("Settings"),
        Body(
            app_header(user, org, "settings"),
            Main(
                Div(Span("WORKSPACE", cls="eyebrow"), H1("Settings"), P("Brand the suite and choose how FastPilot processes your data."), cls="page-heading"),
                P(message, cls="notice ok") if message else None,
                Section(
                    H2("Branding"),
                    Form(
                        Label("Workspace name", Input(name="name", value=org["name"], required=True, autocomplete="organization")),
                        Label("Logo URL", Input(name="logo_url", value=org["logo_url"], placeholder="https://…", autocomplete="url")),
                        Label("Accent colour", Input(name="accent", type="color", value=org["accent"], autocomplete="off")),
                        Button("Save branding", type="submit", cls="btn btn-primary", disabled=not can_admin),
                        method="post",
                        action="/settings/branding",
                        cls="settings-form",
                    ),
                    cls="settings-card",
                ),
                Section(
                    H2("FastPilot provider"),
                    P("Use the FastOffice hosted xAI connection or bring an organisation key. Keys are encrypted and never displayed again."),
                    Form(
                        Label("Provider", Select(*[Option(x.upper(), value=x, selected=provider["provider"] == x) for x in ("xai", "openai", "anthropic", "google")], name="provider")),
                        Label("Model", Input(name="model", value=provider["model"], required=True, autocomplete="off")),
                        Label("API key", Input(name="api_key", type="password", placeholder="Leave blank to keep the current key", autocomplete="new-password")),
                        Label(Input(name="use_platform", type="checkbox", value="yes", checked=bool(provider["use_platform_key"])), Span("Use the hosted FastOffice key"), cls="check-label"),
                        Div(Span("Configured", cls="status-dot") if provider.get("encrypted_key") else Span("No organisation key", cls="muted")),
                        Button("Save AI settings", type="submit", cls="btn btn-primary", disabled=not can_admin),
                        method="post",
                        action="/settings/provider",
                        cls="settings-form",
                    ),
                    cls="settings-card",
                ),
                cls="settings-page",
            ),
        ),
    )
