# Crew Ownership and Redundancy Audit

## Result

The registry contains no duplicate names or prefixes. The first failed bootstrap left no duplicate specs or prompts after the repaired factory run. Functional overlap exists, so ownership must be explicit.

## Retained crew

| Role | Unique responsibility |
|---|---|
| `architect` | Cross-surface boundaries, ADRs, and acceptance validation |
| `ui-specialist` | React features, Stitch-preserving integration, and frontend composition |
| `api-expert` | FastAPI endpoints, OpenAPI, auth/session, and error contracts |
| `data-expert` | PostgreSQL models, repositories, and migrations |
| `platform-expert` | Wikimedia API compliance, provenance, caching, and upstream limits |
| `qa-tests` | Automated contract/component/integration/E2E verification |
| `code-review` | Independent correctness/security review |
| `lean-review` | Inline overengineering/dead-code gate |
| `update-docs` | Canonical documentation synchronization |

## Redundant roles to retire

- `implementer`: generic write scope overlaps UI, API, data, and platform specialists and creates ambiguous ownership.
- `art-director`: a separate generative-art role is unnecessary because Stitch is the protected visual source and Wikipedia/Wikimedia supplies production media. Visual-system ownership belongs to `ui-specialist`, with architect approval for intentional changes.

`scrum-master` remains engine-provided governance, not a generated specialist. The pack's `general` fallback is infrastructure routing and should not own frontend paths.

## Frontend ownership

`ui-specialist` owns frontend production code. `api-expert` owns the backend OpenAPI producer; changes to generated frontend types are coordinated with UI. `qa-tests` owns frontend tests/fixtures, and `update-docs` owns documentation maintenance. `architect` arbitrates shared files. No two roles edit `App.tsx`, global CSS, package manifests, or generated contracts concurrently.
