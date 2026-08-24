# Public demo with visitor-supplied API keys

Visitors choose Groq, OpenAI or Anthropic, enter their provider's API key, select a suggested
or custom model, and connect an authorized PostgreSQL database using a read-only role.
See [provider and model selection](AI_PROVIDERS.md). There is no shared server-side AI key
in public mode. The welcome form asks for explicit consent to send database context
to the selected provider. The key stays in page memory, travels over HTTPS in the Authorization header
only for agent requests, and is never stored in browser storage, cookies or the database.
Reloading the page requires entering it again. Gateway logs omit request headers.

A signed, HttpOnly, SameSite=Strict cookie identifies each visitor. Cookies are Secure
in production and expire after eight hours by default. Every session and database
connection is scoped to that identity; old owner-mode data is not exposed to visitors.
This is browser-session isolation, not account authentication. Anyone using the same
browser profile can use that workspace; use a private window on a shared computer.

Database passwords remain encrypted at rest so chat and dashboard refreshes work.
The sidebar's **Erase my private session** removes that visitor's saved connections,
messages, dashboards and query history. Backups may retain earlier copies until their
retention period ends. Expired visitor workspaces are also purged in small batches
when a new visitor starts. For timely cleanup without traffic, run the following
hourly from the repository directory on the Linux Docker host. It executes the
helper inside the API container with its database configuration:

```sh
docker compose --env-file .env.production -f compose.production.yml \
  -f deploy/compose.public.yml exec -T api python - < scripts/cleanup_visitors.py
```

Public connections require verify-full TLS, a public IP address and port 5432 or 6543.
Private, loopback, link-local and mixed public/private DNS results are rejected. The
checked IP is pinned while the original hostname is preserved for TLS verification.
The operator can further restrict hosts with EXTERNAL_DB_ALLOWED_TARGETS. Private
databases reachable only through a VPN cannot be used by public visitors.

Demo limits: up to 20 sessions and 3 saved connections per visitor, 100 messages per session;
1000 visitor workspaces globally by default. Global API concurrency/body limits still
apply. These limits cap casual use; a larger public service needs platform-level
rate limiting and bot protection. Access expires; users do not get permanent accounts.

## Docker server configuration

```sh
.venv/bin/python scripts/prepare_production.py \
  --access-mode public --domain analytics.example.com --email owner@example.com
docker compose --env-file .env.production -f compose.production.yml \
  -f deploy/compose.public.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml \
  -f deploy/compose.public.yml up -d --build --wait
```

The public overlay removes the owner password gate; it does not publish API/database
ports or remove the internal gateway token. Never expose the API directly. Use the
public overlay for backup/restore too (`--override deploy/compose.public.yml`).
Local development defaults to public mode in docker-compose.yml; set ACCESS_MODE=owner
to return to the private owner workflow. Local cookies work over loopback HTTP only
for development; real visitor credentials require the production HTTPS gateway.

This configuration is for a Docker server. Render's free service needs a separate
single-container packaging and a managed database such as Neon. This change does not
create hosting accounts or deploy a public URL.
