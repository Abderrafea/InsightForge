# FastAPI Cloud Hobby and Neon Free

FastAPI Cloud Hobby currently advertises free hosting without a payment card.
Use the Hobby plan and the existing separate Neon Free application database.
This is a demonstration deployment with free quotas and scale-to-zero, not an
availability guarantee. Check current plan terms before using valuable data.

## Prepare a release

Install the official CLI with `python -m pip install -e "backend[deploy]"` and
sign in using `fastapi cloud login`. The browser lets the account owner review
GitHub login and authorize the CLI. Run `npm ci` from `frontend` on a fresh
checkout, then run this from the repository root:

```sh
python scripts/prepare_cloud_frontend.py
```

The deployment root is **backend**, with entry point `app.cloud:app` configured
in its `pyproject.toml`. Its `.fastapicloudignore` allows only application code,
project metadata and the generated `dist/` UI. Local environment files, credentials,
tests, caches, migrations and unrelated workspace files are excluded. The generated
UI remains ignored by Git, but is included in the cloud upload. The source GitHub
integration alone does not build this frontend; use a local release or a CI build.

## Configure the application

Create an application in the Hobby team and record its generated HTTPS URL.
Configure these before its first deployment:

- `PUBLIC_ORIGIN`: that exact HTTPS origin.
- `APP_DATABASE_URL`: the direct Neon URL; mark this variable as a **secret**.
- `SECRET_ENCRYPTION_KEY`: a unique Fernet key; mark this as a **secret** and save
  a private copy for restoring encrypted database credentials.
- `APP_ENV=production`, `ACCESS_MODE=public`, `DEPLOYMENT_MODE=direct`.

For CLI secret entry, use `fastapi cloud env set NAME --value-stdin --secret
--no-redeploy --app-id APP_ID`; feed the value privately on stdin. Do not put it in
command-line arguments or shell history. Set ordinary variables without `--secret`.
No owner AI key belongs on the service. The entry point clears server provider keys
and enforces PostgreSQL certificate verification, visitor isolation and request limits.

## Migrate and deploy

Apply `alembic upgrade head` from `backend` against the direct Neon connection before
deploying. Supply the same production environment, including the normalized
`postgresql+psycopg` URL, `sslmode=verify-full`, and `sslrootcert` pointing to the
maintained CA bundle returned by `certifi.where()`. The hosted entry point chooses
that bundle automatically unless an explicit CA file is supplied. Migrations are
run once by the release operator, never concurrently in each autoscaled replica.
Keep changes compatible with the previous release during rolling deployments.
On Windows, psycopg async migrations require a selector event loop; running migrations
from a Linux environment avoids the Windows event-loop limitation.

Deploy the prepared **backend directory** using the linked app or explicit app ID:

```sh
cd backend
fastapi deploy --app-id APP_ID
```

After deployment verify `/health`, `/`, direct dashboard routes, secure visitor
cookies, isolation between two browsers and visitor erasure. Test the external
read-only analysis database and each AI provider with a visitor-supplied key. The
application's Neon administrator connection is not an analysis database for visitors.

The pool defaults to three connections per replica. Expired visitor data is cleaned
on startup, during visitor initialization and hourly while a replica remains awake.
For backup and restore precautions, follow the Neon section in [RENDER.md](RENDER.md).
An independent automatic off-site backup is not enabled by this guide.

References: [Hobby pricing](https://fastapicloud.com/pricing/),
[full-stack deployment](https://fastapicloud.com/docs/builds-and-deployments/frontend/),
[environment secrets](https://fastapicloud.com/docs/builds-and-deployments/environment-variables/).
