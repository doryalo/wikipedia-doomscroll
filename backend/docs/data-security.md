# Backend Data and Security Contract

## Current state

The backend currently uses synchronous SQLite and has no models, migrations, repositories, Redis, settings, auth, sessions, CSRF, or CORS. This is transitional scaffold code.

## Persistence

PostgreSQL is the durable system of record. Use SQLAlchemy 2 async with request-scoped sessions and use-case unit-of-work boundaries. Routes do not query or commit. Repositories expose domain operations rather than generic CRUD and never return HTTP responses or commit independently. Database constraints enforce durable uniqueness/foreign-key/value invariants.

Alembic is the only production schema-change mechanism. CI upgrades a fresh PostgreSQL database to head and tests representative upgrade paths. Startup never auto-creates or auto-migrates production schema. Destructive changes require an ADR and rollout/rollback notes.

Redis is non-authoritative, versioned, TTL-backed, and contains no unnecessary personal data. Durable likes, bookmarks, follows, comments, preferences, and history remain in PostgreSQL.

## Settings and privacy

Validate one typed settings model before serving. It owns database/Redis URLs, pool bounds, Wikimedia contact/timeouts, exact browser origins, session/CSRF keys and lifetimes, trusted hosts/proxies, environment, and logging. Never log settings wholesale or commit secrets.

Treat emails, sessions, comments, preferences, history, social actions, and security events as personal data. Define access, retention, export, deletion/anonymization, backup, and log-redaction behavior before production.

## Authentication and authorization

Use adaptive password hashing and server-managed revocable sessions. Rotate sessions after login/privilege changes. Enforce object-level authorization in services/repositories, not UI visibility. Cookie-authenticated mutations require CSRF protection and exact-origin policy. Bound comments/search/page sizes and validate canonical redirect/media hosts.

Emit structured JSON logs with request IDs, route templates, status, duration, and bounded dependency classifications. Never log authorization/cookies, tokens, password material, DSNs, full bodies, or unnecessary personal/search data.
