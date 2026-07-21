# Wikimedia Integration

## Status

No Wikimedia client, `httpx`, Redis, retry policy, or upstream tests exist today. This document defines the target boundary.

Use official APIs only. Allowlist Wikimedia projects/hosts; never turn user input into an upstream hostname. Require `WIKIMEDIA_CONTACT` and send a descriptive product/version/contact User-Agent.

One lifespan-managed `httpx.AsyncClient` uses explicit connect/read/write/pool timeouts, bounded pools, response-size/content-type validation, and restricted redirects. Retry only eligible idempotent transient failures within an overall deadline, using small attempt bounds, jitter, `Retry-After`, and MediaWiki `maxlag` handling. Never layer retries at multiple levels.

Bound outbound concurrency, coordinate aggregate rate limits through Redis when needed, deduplicate identical work, and stop amplification during overload. Map upstream `429`, `maxlag`, timeouts, `5xx`, malformed JSON/schema, and unapproved redirects to stable application errors.

Normalize upstream content into internal models containing safe plain text, page/revision identity, canonical URLs, project/language, retrieval time, and separate article/media license and attribution. Never invent engagement data or pass executable/raw upstream HTML to clients.

Redis entries use versioned namespaced keys, bounded values, TTLs, and all representation-varying inputs. Do not cache personal data in shared Wikimedia keys. Negative-cache only authoritative absence, never timeout/429/maxlag/malformed/5xx. Stale public content may be served only within documented limits while retaining original retrieval/provenance data.

Tests use `httpx.MockTransport` or injected fakes with controlled time/jitter. They cover success, empty/continuation, malformed/oversized payloads, timeouts, cancellation, 429/Retry-After, 5xx, maxlag, cache behavior, concurrency, User-Agent contact, canonical links, provenance, and distinct article/media licensing. CI never calls live Wikimedia.
