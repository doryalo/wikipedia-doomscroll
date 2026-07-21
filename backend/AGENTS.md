# Backend Working Agreement

Read the repository root `AGENTS.md`, then this file and `docs/architecture.md`.

## Current truth

- The checked-in backend is a minimal FastAPI health scaffold.
- It exposes only `GET /live` and `GET /ready`.
- `app/db.py` uses synchronous SQLite and readiness may create `data/app.db`.
- The package currently requires Python 3.12+, while root instructions say 3.11+.
- PostgreSQL, SQLAlchemy async, Alembic, Redis, httpx/Wikimedia, typed settings, auth, structured logging, and tests are not implemented.

Never describe a target capability as implemented. SQLite is transitional scaffold code, not an approved production datastore.

## Target rules

1. Use official Wikimedia APIs only and identify every request with required `WIKIMEDIA_CONTACT` configuration.
2. FastAPI routes validate transport and call application services; they do not issue SQL or expose raw upstream payloads.
3. PostgreSQL is durable truth through SQLAlchemy 2 async repositories and explicit Alembic migrations.
4. Redis is bounded, TTL-backed cache/rate-limit coordination and never durable user state.
5. Manage DB, Redis, and `httpx.AsyncClient` through FastAPI lifespan and dependency injection.
6. Use typed Pydantic v2 DTOs, explicit response models, stable errors, request IDs, and OpenAPI drift checks.
7. Use server-managed HttpOnly cookie sessions with explicit CSRF/CORS policy.
8. Tests never call live Wikimedia and never substitute SQLite for PostgreSQL integration behavior.

## Single-writer zones

| Path | Primary owner |
|---|---|
| `app/api/**`, `app/services/**` | API expert |
| `app/db/**`, repositories, Alembic | Data expert |
| `app/integrations/wikimedia/**`, cache/rate limits | Platform expert |
| `tests/**` | QA |
| `docs/**` | Docs owner with subject-owner review |

The current flat `main.py`, `router.py`, `db.py`, `logger.py`, `pyproject.toml`, lockfile, settings, and generated OpenAPI are serialization points. Assign one writer and use sequential handoffs.

## Verification

Only checked-in commands count as active gates. See `docs/quality-gates.md`; do not create placeholder commands that pass without performing the promised check.
