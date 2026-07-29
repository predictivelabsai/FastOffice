# FastOffice

FastOffice is the open-source productivity suite and control plane for
FastDocs, FastSheets, FastSlides, FastDrive, FastMeet, FastInsights, FastMail,
FastCalendar, and FastPilot.

The suite is designed for both the hosted `fastsme.com` service and self-hosted
installations, with shared identity, organisations, RBAC, invitations,
white-labelling, and AI provider configuration.

See [the architecture and delivery plan](docs/ARCHITECTURE_PLAN.md).

FastPilot supports live xAI responses through the hosted runtime key and
encrypted organisation BYOK. Its product adapters are intentionally
contract-driven: unsupported mutations are blocked instead of being reported
as successful.

## Run locally

```bash
uv sync
uv run uvicorn app:app --host 127.0.0.1 --port 5020
```

Open `http://127.0.0.1:5020`. Development email sign-in is enabled locally and
is forcibly disabled when `FASTOFFICE_ENV=production`.

Run the test suite with:

```bash
uv run pytest
```

Local browser verification captures are stored in
[`output/playwright`](output/playwright).

For container deployment and required secret variables, see
[the self-hosting guide](docs/SELF_HOSTING.md).
