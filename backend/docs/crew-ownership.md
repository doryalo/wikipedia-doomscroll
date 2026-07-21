# Backend Crew Ownership and Redundancy Audit

## Result

The active registry has unique names and prefixes. The generic `implementer` and separate `art-director` were already retired. No remaining project role is redundant when ownership is enforced. `ui-specialist` has no backend write scope but remains necessary project-wide as the OpenAPI consumer.

| Role | Backend ownership |
|---|---|
| Architect | Boundaries, ADRs, cross-surface contracts, arbitration |
| API expert | FastAPI, DTOs, services, auth/session/CSRF/CORS, OpenAPI/errors |
| Data expert | PostgreSQL, SQLAlchemy repositories/UoW, constraints, Alembic |
| Platform expert | Wikimedia client/normalization/provenance, Redis/cache/rate limits |
| QA | Unit/API/PostgreSQL/Redis/migration/security/upstream tests |
| Code review | Independent correctness/security/privacy/concurrency review |
| Lean review | Duplicate layers, speculative infrastructure, and dead-code gate |
| Docs | Canonical backend reference/operations/ADR synchronization |
| UI specialist | Frontend contract consumer; no backend production paths |

Do not add separate FastAPI, database, cache, security, or generic backend agents that duplicate these scopes. A new specialist requires a durable non-overlapping path and decision boundary.

For shared files—`main.py`, current flat modules, settings, `pyproject.toml`, lockfile, CI, and OpenAPI—name one writer, coordinate affected owners, hand off sequentially, regenerate artifacts once, and then run all applicable gates. Keep Forge backend parallel prefixes disabled while these remain shared coordination points.
