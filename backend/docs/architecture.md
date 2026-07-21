# Backend Architecture

## Current implementation

```text
app/main.py -> app/router.py -> app/db.py -> synchronous SQLite file
           -> app/logger.py -> plain-text logging
```

This is a health-only scaffold, not the approved production architecture. The readiness probe is synchronous, state-mutating, and proves only local SQLite access. No product endpoints, repository layer, upstream integration, cache, settings, migrations, auth, or tests exist.

## Target modular monolith

```text
app/api/                 FastAPI routers, dependencies, DTOs, errors
app/services/            use-case orchestration and authorization
app/domain/              framework-independent models and policies
app/db/                  async session/UoW and repository implementations
app/integrations/        Wikimedia gateway and normalization
app/cache/               bounded Redis policies and coordination
app/settings/            typed configuration
app/observability/       JSON logging, request IDs, bounded metrics
alembic/                 explicit schema migrations
tests/                   unit, API, PostgreSQL, Redis, and upstream tests
```

Dependencies point inward: transport calls services; services depend on repository/gateway protocols; infrastructure implements those protocols. ORM models, FastAPI objects, and raw Wikimedia JSON do not cross boundaries.

## Runtime lifecycle

FastAPI lifespan validates settings, creates async PostgreSQL/Redis/httpx resources, wires dependencies, and closes them gracefully. Liveness has no dependency checks. Readiness uses short, non-mutating checks for required local dependencies and schema compatibility; it does not call Wikimedia on every probe.

Do not hold database transactions across upstream calls. Normalize Wikimedia data outside the transaction, then perform the smallest durable write transaction.

## Migration phases

1. Resolve the Python 3.11/3.12 contract.
2. Add honest lint/type/test/OpenAPI gates.
3. Introduce typed settings and lifespan-managed resources.
4. Replace SQLite with PostgreSQL, async repositories/UoW, and Alembic.
5. Add Wikimedia gateway, normalization, Redis policy, and deterministic tests.
6. Add versioned product APIs and frontend contract generation.
7. Add sessions, CSRF/CORS, authorization, privacy, and social persistence only with tested contracts.

Remove `app/db.py` and the SQLite data path only in the coherent PostgreSQL migration; deleting them earlier would break the only current readiness route.
