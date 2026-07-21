# Backend Quality Gates

## Current reality

Poetry install/start and `/live`/`/ready` are the only documented behaviors. There are no test, lint, typecheck, coverage, PostgreSQL/Redis, Alembic, OpenAPI drift, security, or structured-observability gates. Python is also inconsistent: backend requires 3.12+, root says 3.11+.

## Target pull-request gates

1. Locked Poetry environment on the selected Python matrix.
2. Deterministic formatting/lint and strict typing.
3. Unit tests for services, DTO/errors, cursors, settings, retries, cache keys, and UoW behavior.
4. Disposable PostgreSQL tests for mappings, constraints, concurrency, rollback, and Alembic upgrade-to-head.
5. Redis tests for namespaces, TTL, isolation, rate-limit atomicity, outage behavior, and recovery.
6. ASGI API tests for response models, auth/CSRF/CORS, pagination, request IDs, errors, rate limits, and health semantics.
7. Deterministic OpenAPI generation and schema-drift/frontend compatibility checks.
8. Fully mocked Wikimedia tests for identification, normalization, timeouts/retries/maxlag, provenance, and cache behavior.
9. Dependency, secret, and Python security scans with documented exception policy.
10. Documentation/ADR consistency plus independent code, lean, architecture, and QA review.

Tests never use live Wikimedia, wall-clock sleeps, shared state, or SQLite as a PostgreSQL substitute. A `200` from `/ready` alone is not release evidence. Roll gates out in that order and never add placeholder commands that do not perform their advertised check.
