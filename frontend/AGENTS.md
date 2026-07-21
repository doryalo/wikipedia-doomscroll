# Frontend Working Agreement

Read the repository root `AGENTS.md`, then this file and `docs/architecture.md`.

## Current truth

- React 18, TypeScript, Vite 6, and Tailwind CSS 4.
- `src/App.tsx` currently owns the shell, demo data, simulated pagination, and feed state.
- `prompt/design.md` is the original prompt; the rendered Stitch shell is the visual source of truth.
- There is no API client, router, authentication integration, production state layer, or test suite yet.
- Posts, engagement, remote media, delays, navigation, search, and social actions are demo-only.

## Rules

1. Preserve Stitch layout, tokens, typography, breakpoints, and component anatomy unless an approved design decision changes them.
2. Never present fixtures or simulated interactions as production behavior.
3. Use a typed client checked against FastAPI OpenAPI. Browser components never call Wikimedia directly.
4. Preserve canonical URLs, attribution, licensing, language, and media provenance in view models.
5. Model loading, empty, error/retry, pagination-error, and end-of-feed states explicitly.
6. Require semantic controls, keyboard access, visible focus, meaningful alternatives, reduced motion, and announced async states.
7. Do not create tickets here; route work through Forge triage.

## Target boundaries

| Path | Responsibility |
|---|---|
| `src/app/**` | Providers and composition |
| `src/features/feed/**` | Feed state, pagination, and views |
| `src/features/posts/**` | Post models, cards, and interactions |
| `src/components/ui/**` | Shared visual primitives |
| `src/api/**` | Typed transport, generated contracts, and errors |
| `src/fixtures/**` | Development/test data only |
| `tests/**` | Cross-feature and browser tests |

Extract incrementally; do not create speculative empty layers.

## Single-writer zones

`App.tsx`, global CSS, package manifests, generated contracts, and shared types are serialization points. Only one active agent may edit any of them. UI owns feed/post presentation, API owns `src/api/**`, QA owns tests/fixtures, and architect/docs owns `frontend/docs/**`.

## Verification

Run the currently available gates with `npm run lint` and `npm run build`. Also compare changed UI at mobile and desktop widths against the Stitch baseline.
