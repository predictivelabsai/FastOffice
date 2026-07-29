# FastOffice architecture and delivery plan

Status: accepted direction, implementation pending

## Product goal

FastOffice is a multi-user productivity suite that provides one coherent
experience across:

| Product | Role | Public hostname |
|---|---|---|
| FastOffice | Suite home, identity, administration, search | `office.fastsme.com` |
| FastPilot | Cross-suite AI agent and generative UI | `office.fastsme.com/pilot` |
| FastDocs | Documents | `docs.fastsme.com` |
| FastSheets | Spreadsheets | `sheets.fastsme.com` |
| FastSlides | Presentations | `slides.fastsme.com` |
| FastDrive | Files | `drive.fastsme.com` |
| FastMeet | Meetings | `meet.fastsme.com` |
| FastInsights | Business intelligence | `insights.fastsme.com` |
| FastMail | Email client | `mail.fastsme.com` |
| FastCalendar | Calendars and scheduling | `calendar.fastsme.com` |

FastCalendar is a new service. FastMail exists, but currently demonstrates a
webmail client over synthetic data rather than a production mail server.

## Architecture decision

Use independently deployable microservices on product subdomains. FastOffice is
the identity, organisation, administration, discovery, and AI orchestration
control plane. It integrates with product services through versioned APIs.

Do not copy the sister repositories into FastOffice. Extract common,
versioned packages only after a shared implementation has proved stable in at
least two services.

The production edge routes each hostname to its service. FastOffice does not
proxy complete product HTML under paths such as `/docs`, because the current
applications use root-relative routes, cookies, OAuth callbacks, and static
assets. Path proxying would tightly couple their deployments and require
rewriting each application.

The experience remains seamless through:

- one FastOffice login;
- silent, one-time session handoff between trusted subdomains;
- shared suite navigation and account controls;
- stable cross-product deep links;
- consistent organisation, branding, and permissions;
- no repeated Google account chooser or local login;
- FastOffice aggregation APIs for search, recents, favourites, and FastPilot.

Each product may still be deployed and used independently. A standalone product
keeps its own Google and local sign-in entry points.

## Identity and session design

FastOffice is the identity authority for suite deployments.

1. A user signs in at `/auth/google` or with a verified local account.
2. FastOffice creates or resolves the user and active organisation.
3. Selecting a product creates a single-use login ticket with a short expiry,
   intended audience, user ID, organisation ID, role and return path.
4. The browser reaches the product's `/auth/suite/callback`.
5. The product redeems the ticket server-to-server and creates a host-only,
   secure session cookie.
6. Returning visits use the existing product session. If it has expired, a
   hidden or top-level FastOffice authorization request performs silent
   handoff without invoking Google again.

Do not share a broad `.fastsme.com` session cookie. Host-only cookies limit the
impact of a compromised product and make standalone/self-hosted deployments
possible.

Required controls:

- OpenID Connect state and nonce validation;
- `openid email profile` scopes only for Google authentication;
- verified-email enforcement;
- authorization-code and login-ticket replay protection;
- short ticket and access-token lifetimes;
- audience-bound signed tokens and key rotation;
- secure, HTTP-only, SameSite cookies;
- explicit logout from the current product and optional suite-wide logout;
- audit events for login, invitation, role and key changes.

The bootstrap hosted-cloud super-admin is `kaljuvee@gmail.com`. It must be
configured through an environment variable or migration, not embedded as an
unconditional application bypass. On first boot, the configured address gains
the platform-admin role and an owner membership in the initial organisation.

## Organisations, tenancy and RBAC

Core records:

- users;
- organisations;
- memberships;
- roles and permissions;
- invitations;
- product entitlements;
- sessions and service grants;
- audit events;
- organisation branding;
- AI provider configurations.

Initial organisation roles:

| Role | Capabilities |
|---|---|
| Owner | Organisation deletion/transfer, billing, all admin capabilities |
| Admin | Members, invitations, branding, product and AI settings |
| Member | Create and collaborate within granted products |
| Viewer | Read shared resources without mutation |
| Guest | Explicitly shared resources only |

Products must authorize both the user and organisation on every data operation.
Adding `org_id` only at the FastOffice gateway is insufficient; tenant
enforcement belongs inside each product service and database query.

Invitations are single-use, expiring, email-bound tokens. FastOffice sends them
through Postmark and records inviter, organisation, role, expiry, acceptance,
and revocation. Only `POSTMARK_API_TOKEN` belongs in runtime secret storage.

## API and service integration

The existing sister APIs provide a useful schema baseline, but public reads and
one deployment-wide `FASTSME_API_TOKEN` are not suitable for a multi-tenant
suite.

Adopt:

- `/api/v1` versioning;
- short-lived user access tokens for user actions;
- client-credential tokens for service jobs;
- scopes such as `docs:read`, `docs:write`, and `meetings:create`;
- consistent `org_id`, owner, created/updated timestamps and resource URLs;
- cursor pagination for changing collections;
- idempotency keys on create and side-effecting AI actions;
- standard error envelopes and request/correlation IDs;
- optimistic concurrency through version numbers or ETags;
- outbox/webhook events for cross-service indexing;
- OpenAPI contract tests and generated clients.

FastOffice owns an integration adapter per product. FastPilot calls these
adapters rather than product databases or arbitrary HTTP endpoints.

Cross-suite search uses a FastOffice index populated by product events and
periodic reconciliation. Search results retain source product, organisation,
permissions, resource type, title, snippet, updated time, and canonical deep
link. Permission checks are repeated at retrieval time.

## FastPilot

FastPilot is a first-class FastOffice service at `/pilot`.

### Interface

- Left pane: suite launcher, new chat, conversation history, agents/workflows.
- Centre pane: streaming conversation, attachments, suggestion cards and
  contextual chips.
- Right pane: dynamic canvas for typed, interactive artifacts.
- Mobile: off-canvas left navigation; results/canvas opens on demand.

Initial artifact types:

- document preview and editable draft;
- spreadsheet table and formula proposal;
- chart and dashboard result;
- slide outline and deck preview;
- file search results;
- meeting and calendar plan;
- email draft;
- action plan and confirmation;
- structured error/partial-result state.

The model does not emit executable HTML. It returns validated artifact schemas
rendered by trusted FastOffice components.

### CRUD and safety

FastPilot supports create, read, update, and delete through explicit tools.

- Reads execute within the user's organisation and product permissions.
- Creates and updates show the proposed target and material changes.
- Deletes, sends, external shares, meeting invitations, and bulk mutations
  require an explicit confirmation step.
- Every mutation uses an idempotency key and produces an audit event.
- Tool results cite and deep-link their source resources.
- The orchestrator treats retrieved documents and emails as untrusted data and
  prevents their content from changing tool permissions.

### AI provider settings

Hosted defaults use xAI through runtime `XAI_API_KEY`. Settings support:

- platform-provided xAI;
- organisation bring-your-own provider key;
- optional user key if organisation policy permits;
- provider/model selection and usage limits;
- test connection, rotate, disable and delete;
- clear indication of which provider will process data.

BYOK secrets are encrypted at rest with a deployment master key or external
secret manager. They are write-only in the UI, never returned by APIs, never
logged, and never stored in browser code. Self-hosters configure the same
providers through environment variables or the encrypted settings store.

## Branding and distribution

FastOffice supports hosted SaaS and self-hosted distribution from the same
codebase.

Organisation branding includes:

- display name;
- logo and compact mark;
- primary/accent colours with contrast validation;
- optional support URL;
- email branding;
- custom domain in hosted plans.

Branding never changes security-sensitive issuer, cookie, callback, or service
identity values.

Provide:

- production Docker images;
- a local Docker Compose profile for FastOffice and selected products;
- documented external PostgreSQL and object-storage configuration;
- migrations, health checks, backup/restore and upgrade instructions;
- environment samples containing variable names only;
- feature flags for optional products and hosted-only integrations.

SQLite remains acceptable for local demonstration but not for hosted
multi-instance production. Use PostgreSQL for identity and tenant data, and
S3-compatible object storage for file content and branding assets.

## Landing page

Anonymous `/` presents the FastOffice landing page; authenticated `/` presents
the suite home.

Navigation has a top-right **Sign In** control. The hero uses:

> Your work. Your data. Your freedom.

Supporting line:

> Discover the freedom of an open-source workspace—documents, spreadsheets,
> presentations, files, meetings, mail, calendars, insights and AI in one
> connected suite.

Primary action: **Sign In**.

The page includes:

- suite hero and product UI preview;
- nine product cards with their established colours and direct subdomain links;
- FastPilot three-pane showcase;
- collaboration, ownership and self-hosting benefits;
- cloud versus self-hosted choices;
- security and data-control section;
- open-source repository links;
- responsive footer and legal/company details.

The visual direction follows the FastSME public surfaces: white, restrained,
product-specific colour accents, strong typography, one primary action, and a
keyboard-accessible mobile sign-in.

## Delivery sequence

### Phase 1: foundation

- Scaffold FastOffice with FastHTML, PostgreSQL migrations and tests.
- Build the anonymous landing and authenticated suite shell.
- Implement users, organisations, memberships, roles and bootstrap admin.
- Implement Google/local authentication and secure sessions.
- Implement invitation lifecycle and Postmark email templates.
- Add organisation branding and product registry.

Exit: a user can sign in, create or join an organisation, invite a member,
change roles, apply branding, and launch visible products.

### Phase 2: seamless suite identity

- Implement the suite ticket issuer and redemption contract.
- Add `/auth/suite/callback` to FastMail and the six existing products.
- Preserve each product's standalone local and Google sign-in.
- Add shared suite switcher/account navigation package.
- Add suite-wide and product-only logout.

Exit: one FastOffice login opens every entitled product without another login
prompt, while standalone deployments still authenticate independently.

### Phase 3: tenant-safe product APIs

- Move product data models from demo-global ownership to users and organisations.
- Replace public reads/global write token with scopes and service grants.
- Normalize API contracts and add idempotency/concurrency controls.
- Add product event outboxes and FastOffice adapters.
- Add cross-suite recents, favourites and search.

Exit: contract and tenant-isolation tests pass for every integrated service.

### Phase 4: FastPilot CRUD

- Build conversations, messages, streaming events and typed artifacts.
- Implement read tools and citations across all products.
- Implement previewed, confirmed and audited CRUD tools.
- Add xAI platform configuration and encrypted BYOK settings.
- Add usage limits, provider disclosure and failure recovery.

Exit: FastPilot completes cross-product workflows without exceeding the
authenticated user's permissions.

### Phase 5: FastCalendar and communications

- Create the FastCalendar repository and service.
- Implement calendars, events, recurring rules, attendees, availability,
  reminders, time zones and FastMeet links.
- Integrate production mail transport/storage behind FastMail.
- Connect invitation and notification delivery.

Exit: calendar and mail operate on real multi-user data rather than synthetic
fixtures.

### Phase 6: production and self-hosting

- Add PostgreSQL/object storage production profiles.
- Add backup, restore, retention, observability and admin operations.
- Package Docker Compose self-hosting and upgrade documentation.
- Add hosted custom domains and entitlement/billing hooks.
- Complete accessibility, security and failure-mode testing.

Exit: hosted and self-hosted installations pass the same release suite.

### Phase 7: deployment

- Register FastOffice and FastCalendar in FastDevOps service configuration.
- Configure `office.fastsme.com` and `calendar.fastsme.com`.
- Add Coolify applications and secret variables without committing values.
- Use a single automatic deployment trigger from `main`.
- Verify deployed commit, health, TLS, canonical host and OAuth callbacks.

Deployment mutations require a separate explicit authorization after read-only
validation and DNS resolution.

## Release gates

- No secret values, demo passwords or developer paths in committed files.
- Tenant isolation is tested at service and API levels.
- Authentication tickets cannot be replayed or redeemed by another audience.
- Invitations expire and can be revoked.
- FastPilot destructive/external actions require confirmation.
- BYOK values are encrypted, write-only and absent from logs.
- Anonymous and authenticated root behaviour is correct.
- Sign in and core navigation are keyboard accessible at desktop and mobile.
- Partial product outages degrade the suite home and FastPilot gracefully.
- Self-hosted startup, migration, backup and restore are documented and tested.
- Production health, TLS, domain, callback and deployed commit are verified.

## Immediate implementation order

1. Create the FastOffice application skeleton and landing.
2. Add PostgreSQL-backed identity, organisations, RBAC and invitations.
3. Add Google/local login and the configured bootstrap admin.
4. Add suite home, product registry, branding and settings.
5. Implement the session-handoff protocol in FastOffice and one pilot product.
6. Prove tenant-safe API access and FastPilot CRUD with that product.
7. Roll the shared contracts through the remaining services.
8. Build FastCalendar after identity and API contracts have stabilized.
