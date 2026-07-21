# Backend API Contract

## Status

Only `GET /live` and `GET /ready` exist today. Everything below is target architecture.

Product routes use `/api/v1`; health routes remain unversioned. Pydantic v2 models define requests/responses and generate the authoritative OpenAPI document. Frontend types are generated from OpenAPI and raw Wikimedia payloads never become public DTOs.

## Feed

```http
GET /api/v1/feed?cursor=<opaque>&limit=20&language=en&mode=discovery
```

The response contains `items`, `next_cursor: string | null`, and `request_id`. Each item carries stable identity, title/excerpt, RFC 3339 timestamps, canonical HTTPS URL, language/project/revision identity, media metadata, attribution/license provenance, and authoritative engagement state.

Cursors are backend-created, integrity-protected, bounded, scoped to the feed query/principal, and opaque to clients. They never expose database keys or raw Wikimedia continuation state. Invalid/expired/mismatched cursors return `400 invalid_cursor`; null is terminal.

## Errors and request IDs

Every response returns `X-Request-ID`. Application errors use:

```json
{"error":{"code":"rate_limited","message":"Try again later.","request_id":"01J...","details":{"retry_after_seconds":15}}}
```

Use stable mappings for validation, authentication, authorization, conflicts, rate limits, invalid upstream responses, dependency failures, and timeouts. Never expose framework `detail`, stack traces, SQL, secrets, or upstream bodies. Include `Retry-After` for meaningful `429`/availability delays.

## Sessions and browser policy

Use server-managed Secure/HttpOnly/SameSite cookies with rotation, expiry, and revocation. State-changing cookie-authenticated requests require one documented CSRF mechanism. Prefer same-origin `/api`; otherwise use exact CORS origins, minimal methods/headers, credentials only for trusted origins, and tested preflight behavior.

State-setting `PUT`/`DELETE` mutations are idempotent. Non-idempotent creation is never automatically retried without a supported idempotency key.
