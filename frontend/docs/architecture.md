# Frontend Architecture

## Current implementation

```text
index.html -> src/main.tsx -> src/App.tsx -> components/ui/button.tsx
                            -> src/index.css
```

The app is one responsive feed screen. `App.tsx` combines header/navigation, cards, skeletons, expansion state, hard-coded content, a timer-based loader, and an `IntersectionObserver`. It has no backend transport, routing, session integration, complete empty/error/end state, or tests.

The shell shows search, profile, navigation, and social controls, but `prompt/design.md` describes them as display-only. They remain affordances until explicit product and API contracts support them.

## Direction

```text
src/app/                  application composition
src/api/                  typed client and generated contracts
src/features/feed/        cursor state and feed presentation
src/features/posts/       post view models and components
src/components/ui/        shared visual primitives
src/fixtures/             development/test-only data
src/lib/                  framework-independent utilities
```

Shared UI must not import features. Components must not issue raw `fetch` calls or depend on persistence/Wikimedia payloads. `App.tsx` should eventually compose features rather than orchestrate data.

## Data flow

```text
viewport/user event -> feature controller -> typed API client -> FastAPI
-> normalized DTO + opaque cursor -> view-model adapter -> Stitch components
```

Keep local UI state, server state, session state, and shareable URL state separate. Cursor values are opaque. Deduplicate requests and item IDs, cancel stale work, preserve loaded content after append failures, and stop observing when the cursor is null.

## Incremental extraction

1. Capture mobile/desktop visual baselines.
2. Extract presentation components without changing rendered output.
3. Move demo content behind an explicit fixture adapter.
4. Add typed transport, errors, and environment validation.
5. Replace simulated pagination with the cursor state machine.
6. Add only contracted sessions, search, routing, and social mutations.
7. Add contract, component, accessibility, responsive, and browser tests.

Every phase preserves the Stitch baseline unless a deliberate design decision says otherwise.
