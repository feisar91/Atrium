# Atrium

Multi-tenant captive portal admin for UniFi networks. Flask + Postgres backend,
React/Vite admin SPA served by nginx, VitePress docs site. See README.md for the
product and DEVELOPMENT.md for local setup.

## Layout

- `backend/` - Flask app factory in `app/__init__.py`. Blueprints: `app/api/`
  (admin JSON API, `/api`), `app/portal/` (guest-facing captive portal pages,
  `/p`, Jinja templates in `app/templates/portal/`). Models in `app/models/`,
  Alembic migrations in `migrations/versions/`.
- `frontend/` - admin SPA, built into the web image and served at `/admin`.
- `nginx/` - web image: multi-stage build of `frontend/`, then nginx proxying
  `/api`, `/p`, `/static`, `/guest` and `/` to the backend.
- `docs-src/` - VitePress site, deployed to GitHub Pages by `pages.yml`.

## Commands

Backend tests need a real Postgres (there is no SQLite fallback). Via the dev stack:

```sh
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml exec backend pip install -r requirements-dev.txt
docker compose -f docker-compose.dev.yml exec backend pytest
```

Outside Compose, set `TEST_DATABASE_URL=postgresql://user:pw@host:5432/dbname`.
The test DB is created if missing. Use Python 3.12 to match the image.

Frontend: `cd frontend && npm ci && npm run build` (runs `tsc` then `vite build`).
There are no frontend tests, so the build is the type check.

Migrations: `flask db migrate -m "..."` inside the backend container, then
review the generated file before committing. `entrypoint.sh` runs
`flask db upgrade` on every container start.

## Conventions and gotchas

- **Tenant isolation is enforced by hand in each endpoint.** Use the decorators
  in `app/api/decorators.py` (`require_admin`, `require_superadmin`,
  `tenant_access_required`) and check that the resource's tenant matches the
  caller's unless the caller is a superadmin (see `_assert_portal_access` in
  `api/uploads.py`). Every new endpoint needs this; `tests/test_tenant_isolation.py`
  covers it.
- Record admin actions with `app.audit.record(...)`.
- JWT failures are remapped to 401 in `create_app` because the frontend's axios
  interceptor only treats 401 as an auth error.
- **gunicorn runs with `workers = 1` on purpose.** APScheduler (`app/scheduler.py`)
  runs in-process and Flask-Limiter uses `memory://` storage, so adding workers
  would duplicate scheduled jobs and split rate-limit counters.
- `Config.SQLALCHEMY_DATABASE_URI` hard-codes host `db` (the Compose service name).
  Only the credentials come from env.
- `conftest.py` sets env vars at import time, before collection, because
  `TestingConfig` reads them when the class is defined. Keep it that way.

## Dependencies

- Backend pins are exact in `requirements.txt`. **Keep SQLAlchemy on 2.0.x:**
  2.1 makes `postgresql://` default to psycopg 3, but only `psycopg2-binary`
  is installed.
- The backend image installs with `--only-binary=:all:` and no compiler or
  `libpq-dev`, so every new Python dependency must ship a cp312 manylinux wheel.
- Audit with `pip-audit -s osv` (the default PyPI source misses advisories) run
  inside a `python:3.12-slim` container, and with `npm audit` in `frontend/`
  and `docs-src/`.
- The known `docs-src` advisories (vite/esbuild, dev server only) are pinned
  by vitepress 1.x and have no stable fix.

## Releases

Pushing a `vX.Y.Z` tag runs `publish.yml`: backend tests, then build and push
`ghcr.io/feisar91/atrium-backend` and `atrium-web` as `X.Y.Z` and `latest`.
Tag main only after the change is merged. `docker-compose.yml` pulls `:latest`.
`APP_VERSION` comes from the tag; `frontend/package.json`'s version is not kept
in sync.
