# Production deployment

For the public visitor-key workflow, use [the public demo guide](PUBLIC_DEMO.md).
This page describes the alternative private owner deployment.

This stack runs one owner-controlled workspace. Every page and API endpoint is behind
Caddy's password authentication and HTTPS. Anyone given the owner password can access
all sessions, database connections and dashboards. It is not a multi-tenant service.
Use a separate installation for each owner. Do not give public visitors this password.

Only the gateway publishes ports (80/443). PostgreSQL, nginx and the API stay on private
Docker networks. The gateway removes the owner's Authorization header and injects a
separate random token; the production API rejects requests without that token. A direct
API port must never be published. API writes also require the frontend's custom header
and reject foreign browser origins. OpenAPI documentation is disabled in production.

## Prepare the server

Use a Linux server with Docker Engine and Compose 2.24.4 or newer, a DNS name pointing
to it, and inbound TCP 80/443 (UDP 443 is optional). Start with at least 2 GB RAM and
monitor database/disk usage. This is a starting configuration, not a measured capacity
guarantee. Restrict SSH separately. Keep the Docker daemon private.

Clone the repository and install the configuration helper into a Python 3.12+ virtual
environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[ops]'
.venv/bin/python scripts/prepare_production.py \
  --access-mode owner \
  --domain analytics.example.com \
  --email owner@example.com \
  --database-targets analytics-db.example.com:5432
```

The helper prompts for a new owner password and the selected provider's key without echoing them. It
creates `.env.production` with a bcrypt password hash, a random PostgreSQL password,
a new Fernet encryption key, and a separate gateway token. It refuses to overwrite an
existing file. On Linux the file is owner-readable only; on Windows use a private
directory/ACL when preparing configuration. The default model can be changed with
`--provider groq|openai|anthropic` and `--model`; use a model available to that provider account
that supports the adapter's structured-output format. See [AI providers](AI_PROVIDERS.md).
Do not reuse the key pasted into chat for production: create a replacement Groq key
and revoke the old one after local testing is finished.

Keep `.env.production` private and back it up in a password manager or secret store.
Do not use `docker compose config` without `--quiet` in shared logs: its expanded
output contains secrets. Do not regenerate the encryption key after saving database
connections; losing it makes their stored passwords unrecoverable. Changing database
passwords in an environment file does not change an existing PostgreSQL role: rotate
the database role and application configuration together during maintenance.

## External database access

`EXTERNAL_DB_ALLOWED_TARGETS` is an exact comma-separated allowlist of DNS names and
ports. Configure only databases you control, using stable DNS and a network firewall
allowlist where possible. Do not include the application's own database or metadata
endpoints. Production connections require `verify-full` TLS with a trusted certificate.
Use the provider's public CA, or mount its CA read-only into the API and set
`PGSSLROOTCERT` in a local Compose override. Do not disable certificate verification.
DNS is an operator-controlled trust boundary; the application does not pin resolved IPs.

Each external database needs a dedicated read-only PostgreSQL role. The development
demo database and its published credentials are deliberately absent from production.
The production stack also sets result samples sent to the AI provider to zero. Schema,
SQL and user prompts are still sent to the selected AI provider; the owner must authorize that processing
before connecting customer data.

## Validate and deploy when ready

```sh
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml build --pull
docker compose --env-file .env.production -f compose.production.yml up -d --wait
docker compose --env-file .env.production -f compose.production.yml ps
```

Use this production file by itself, never merge it with `docker-compose.yml`.
Keep one API replica: startup runs Alembic migrations before accepting traffic, and
the request concurrency limit is per process. Scaling needs a separate migration job
and a shared rate/concurrency limiter. Caddy obtains and renews certificates and
redirects HTTP to HTTPS. Owner login is the browser's native password dialog; close
the browser session to clear its cached Basic credentials. For team accounts, SSO,
MFA or individual revocation, replace this gateway with an identity-aware proxy before
sharing access. Password authentication alone does not provide those features.

Verify that unauthenticated page/API requests return 401, valid owner login works,
the API/database ports are unreachable externally, and the first dashboard uses the
expected read-only database. The public gateway requires authentication even for
`/health`; the container health check is internal. Container health indicates process
availability; check a real authenticated session request to verify database availability.

## Backups and restore

```sh
.venv/bin/python scripts/production_database.py backup backups/insightforge-2026-11-08.dump
# Test this against a separate, empty installation before relying on the backup:
.venv/bin/python scripts/production_database.py restore backups/insightforge-2026-11-08.dump
```

The backup helper preserves binary data on both Windows and Linux and refuses to
overwrite a backup. Restore requires a typed confirmation, stops the application,
restores in one transaction, and restarts the stack. Only restore a trusted dump;
database restores execute database definitions. Keep encrypted off-server copies
of database backups and the matching environment secrets. A backup without its
Fernet key cannot decrypt saved database passwords. Schedule backups using the
server's scheduler and choose retention/storage according to your requirements.

Before upgrades, make a backup, record the current Git revision and image IDs, then
build and start the new release. Rolling back code across a migration may require
restoring the matching database backup. Never run `down --volumes` on a live stack.
Logs rotate automatically; monitor disk space, certificate renewal, health, failed
logins and Groq usage. Use provider-side spending limits. The gateway protects a
private workspace; it is not a public anonymous demo or a general abuse-prevention
service.

## Local production preflight

For verification without publishing a site, use a separate ignored environment file
with `DOMAIN=localhost`, disposable secrets and the `deploy/compose.preflight.yml`
overlay. Always pass a separate project name such as `insightforge-preflight`. The
overlay binds ports only to loopback and uses HTTPS on 18443. Caddy uses its local
CA for localhost; export and explicitly trust that CA in the test client rather than
disabling TLS verification. Do not reuse the local preflight CA on a public host.

References: [Caddy authentication](https://caddyserver.com/docs/caddyfile/directives/basic_auth),
[Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[Docker environment handling](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
