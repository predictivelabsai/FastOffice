# Self-hosting FastOffice

FastOffice can run independently while its product applications remain on
their own subdomains or deployments.

## Required production secrets

Create an ignored `.env` file from `.env.sample` and set:

- `FASTOFFICE_SESSION_SECRET` to a long random value;
- `FASTOFFICE_ENCRYPTION_KEY` to a Fernet key;
- Google OAuth client credentials and the exact HTTPS callback;
- `POSTMARK_API_TOKEN` for invitations;
- `XAI_API_KEY` for the hosted FastPilot provider.

Generate a Fernet key without printing or committing other environment values:

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Start the service:

```bash
docker compose up --build
```

FastOffice is served at `http://localhost:5020`; `/health` is the container
health endpoint.

The current local release uses a persisted SQLite database. Hosted
multi-instance production must use the planned PostgreSQL backend before
horizontal scaling.
