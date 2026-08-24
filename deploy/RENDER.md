# Render Free and Neon Free

This deployment runs the built React frontend and FastAPI in one Docker web service.
Use `deploy/render.Dockerfile`, repository root as the build context, region Frankfurt,
plan **Free**, and `/health` as the health-check path. Keep automatic deploys off
until a release has passed verification. `render.yaml` describes the same setup.
No paid disk, Render PostgreSQL instance, background worker or cron job is required.

Create a separate Neon project in an organization on its **Free** plan, preferably
in the matching region. Keep autosuspend enabled and use its direct connection URL
(pooling disabled) for `APP_DATABASE_URL`. Set `SECRET_ENCRYPTION_KEY` to a new Fernet
key and save it in a password manager. Never commit either value. No owner AI key
belongs in this service: each visitor supplies their own key for the chosen provider.

The image supplies `APP_ENV=production`, `ACCESS_MODE=public` and
`DEPLOYMENT_MODE=render`. Render supplies `PORT` and `RENDER_EXTERNAL_URL`; startup
uses the latter as the public origin. A custom domain requires `PUBLIC_ORIGIN` to
be updated to its HTTPS origin. PostgreSQL connections enforce `verify-full` TLS
with system certificate roots. Startup applies Alembic migrations before listening.
Run one instance and one worker; this avoids concurrent startup migrations.

The database pool has three connections and no overflow. Requests are limited to
two concurrent operations. These defaults suit a small demonstration, not high
traffic. Render Free sleeps when idle and can take time to wake. The filesystem is
temporary: all persistent application state lives in Neon, never local SQLite.
Check both accounts' free quotas before publishing; exhausted quotas can interrupt
availability. Do not enable paid upgrades to keep this installation free.

Visitor cookies expire after eight hours. Expired records are cleaned at startup,
when a visitor opens the application, and hourly while the process is awake. This
does not promise hourly execution while Render is sleeping. Visitors can erase
their own workspace immediately from the application.

## Verification

After deployment, verify HTTPS, `/health`, the home page and a direct dashboard URL.
Create a visitor workspace and confirm its cookie is Secure and HttpOnly. A fresh
browser must not see the first visitor's sessions. Exercise database connection,
schema inspection and dashboard generation with a disposable read-only database
and your own provider key. Mocked adapter tests do not replace a live test for each
provider you intend to advertise. Never use the app's Neon administrator credentials
as a visitor's analysis database connection.

## Backups and rollback

Before migrations, export the Neon database with a matching-version PostgreSQL
`pg_dump` client using the direct URL. Pass credentials through an environment or
protected connection file, not command-line arguments or shell history. Encrypt
the dump before storing it outside Neon and keep the matching Fernet key separately.
Test restoration into a separate disposable database. A backup without its Fernet
key cannot recover saved database passwords. Free hosting does not itself provide
an independently scheduled off-site backup; arrange and verify one before storing
valuable data. `scripts/production_database.py` targets the separate Docker Compose
installation and is not a Neon backup command.

Record the deployed Git revision. Revert code through a new commit and deploy that
revision; a database migration may also require restoring the matching backup.
Never reset or delete an existing Neon project to troubleshoot a deployment.

References: [Render Free](https://render.com/docs/free),
[Docker services](https://render.com/docs/docker),
[Neon connections](https://neon.com/docs/connect/connect-from-any-app).
