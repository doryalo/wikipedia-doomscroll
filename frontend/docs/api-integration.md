# Frontend API Integration

The backend owns OpenAPI and Wikimedia normalization. The frontend generates transport types, calls FastAPI through one client, and maps DTOs into presentation-specific view models. Components never consume raw Wikimedia data or HTTP details.

## Module boundary

- `src/api/generated/**`: generated OpenAPI types; never hand-edit.
- `src/api/client.ts`: base URL, credentials, request IDs, decoding, cancellation, and normalized errors.
- `src/api/feed.ts`: typed endpoint calls.
- `src/features/feed/adapters.ts`: DTO-to-view-model mapping.
- `src/features/feed/fixtures/**`: explicit development/test adapter only.

## Feed requirements

A page contains stable items plus `next_cursor: string | null`. The cursor is opaque: the browser stores and returns it but never parses or constructs it. RFC 3339 timestamps become relative labels in the adapter. DTOs retain canonical URL, source, attribution/license, language, media metadata, and engagement fields supported by the backend.

Initial failure, empty feed, append failure, cancellation, rate limiting, and terminal feed are distinct. Preserve successful pages when an append fails. Honor `Retry-After`; do not retry non-idempotent mutations automatically.

## Runtime and sessions

- `VITE_API_BASE_URL` is public build-time configuration and never contains secrets.
- Prefer same-origin `/api`; otherwise configure an explicit local proxy and exact CORS origins.
- Cookie sessions use Secure, HttpOnly, SameSite cookies and `credentials: "include"`; JavaScript never stores session tokens.
- Centralize CSRF behavior, `401` reauthentication, `403` authorization errors, and `X-Request-ID` propagation.
- Every client request accepts an `AbortSignal`; cursor requests are deduplicated and stale responses ignored.

Production modules must not import the existing fake posts, timers, avatar URLs, or Unsplash URLs. Contract tests cover success, empty, terminal, malformed, `401`, `403`, `429`, `5xx`, timeout, and abort responses.
