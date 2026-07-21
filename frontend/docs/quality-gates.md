# Frontend Quality Gates

## Current gates

| Command | Reality today |
|---|---|
| `npm run dev` | Vite development server; not a CI gate |
| `npm run lint` | Declared, but ESLint configuration must be verified/added |
| `npm run build` | TypeScript project build plus Vite production build |
| `npm run preview` | Local built-output preview; not a CI gate |

There are currently no unit, component, accessibility, or end-to-end scripts. The following are required targets, not claims of existing tooling.

## Required pull-request gates

1. Locked install with `npm ci`.
2. Lint with no errors.
3. Strict no-emit typecheck.
4. Deterministic unit/component tests for adapters and all feed states.
5. Automated accessibility checks for serious/critical violations.
6. Production build with environment validation and no bundled fixtures/secrets.
7. Controlled browser tests for initial feed, cursor append, terminal cursor, retry, session expiry, responsive layout, and keyboard behavior.
8. OpenAPI type regeneration/schema-drift check before typecheck.

Freeze time, seed randomness, mock network boundaries, and avoid sleeps/live Wikimedia. Test abort-on-unmount, cursor deduplication, stale-response ordering, and preservation of loaded pages after failure. Add bundle/performance reporting before setting measured blocking budgets.
