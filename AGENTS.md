# Bootstrap the architecture, documentation, and agent infrastructure for 'Wikipedia Doomscroll', a production-quality full-stack social discovery application that wraps public Wikimedia APIs in a continuously scrolling content feed. — Agent Context (AGENTS.md)

> Universal, tool-agnostic context. Active-voice rules. Keep under ~500 lines.
> This file is the single source of truth; tool-specific files point here.

## Project
- Objective: Bootstrap the architecture, documentation, and agent infrastructure for 'Wikipedia Doomscroll', a production-quality full-stack social discovery application that wraps public Wikimedia APIs in a continuously scrolling content feed.
- Target users: Users seeking a modern, social, continuous-scrolling discovery experience for Wikipedia content.
- Platforms: Web (Frontend shell provided), Backend API
- Stack: Python 3.11+, FastAPI, Pydantic v2, httpx, uvicorn, PostgreSQL, SQLAlchemy 2 async, Alembic, Redis

## Constraints (non-negotiable)
- Use official Wikimedia APIs only (no HTML scraping).
- Preserve the Stitch AI-generated frontend shell as the visual source of truth without redesigning.
- Output ONLY bootstrap infrastructure, documentation, and empty task boards (no implementation tickets yet).
- Sequential execution until file ownership boundaries are proven safe.
- Must include WIKIMEDIA_CONTACT header for API compliance.

## Non-functional requirements
- Modular monolith architecture with strong frontend/backend contract separation.
- Repository pattern for database access to allow isolated test fixtures.
- Bounded Redis caching and rate-limit coordination.
- Structured JSON logging to stdout, request IDs, health/readiness endpoints, and basic metrics hooks.
- Deterministic tests with mocked Wikimedia calls.
- Clear async service boundaries and typed API contracts with OpenAPI documentation.
- Robust error handling, request timeouts, and retries.

## Working agreement
- Read this file and the nearest scoped doc before acting.
- Out-of-scope work -> propose_task (triage queue), never add_task directly.
- One decision per ADR under docs/adr/; supersede, never edit accepted ADRs.
- Crew routing lives in `.forge/project-pack.yaml` — do not hardcode board prefixes in code.

## Parallel / single-writer zones
When using `forge flow3 --parallel`, no two concurrent tickets may edit the same
paths. Fill this table for your repo (examples only — replace with real ownership):

| Zone (paths) | Owning board prefix |
|--------------|---------------------|
| (e.g. `src/api/**`) | IM |
| (e.g. `tests/**`) | QA |
| (e.g. `docs/**`) | DC |

Keep `parallel_prefixes` in `.forge/project-pack.yaml` limited to boards whose
zones do not overlap. See forge `docs/RUNBOOK.md` §6.
