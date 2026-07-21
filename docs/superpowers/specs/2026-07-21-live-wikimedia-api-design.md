# Live Wikimedia FastAPI Design

## Goal

Provide a small live-data FastAPI service in `wikimedia_api/main.py`. Every
route returns the existing `wikimedia_content/page-results.schema.json`
envelope, including a text-only card and full plain-text page content.

## Scope and boundaries

- The service calls official Wikimedia APIs only. It never scrapes HTML pages.
- It is a development-facing adapter, separate from the future production
  backend gateway described in `backend/docs/wikimedia-integration.md`.
- It uses `wikimedia_content.models.PageResultsDataset` as its response model.
- It creates no JSON snapshot files and does not invoke the notebook generator.
- The only implementation artifact is `wikimedia_api/main.py`; it may import
  the existing Pydantic models.

## Runtime model

FastAPI creates one `httpx.AsyncClient` during application lifespan and closes
it during shutdown. The client sends the configured `WIKIMEDIA_CONTACT` in a
descriptive User-Agent, allows only Wikimedia hosts, uses explicit timeouts,
and adds `maxlag=5` to Action API queries.

The process-wide upstream coordinator permits at most 200 Wikimedia requests
per rolling minute and at most three concurrent upstream requests. It respects
`Retry-After` on `429` and `503`; a request that cannot be completed is mapped
to an appropriate FastAPI error rather than silently returning partial data.
The 200/minute setting implements Wikimedia's compliant User-Agent access
class, not a private reservation or a substitute for upstream responses.

## Shared response pipeline

Each discovery route yields ordered candidate titles and route-specific
discovery metadata. A shared hydrator resolves the candidates into the common
dataset shape:

1. fetch batched identity/card metadata without image properties;
2. fetch full plain-text content per accepted page, because Wikimedia's full
   extract response is single-page constrained;
3. create ranked `PageResult` values and one `PageResultsDataset` envelope;
4. set `expansion.shortfall` only when the route cannot naturally supply the
   requested number of pages.

Responses always contain at most ten pages. `count` parameters are constrained
to 1 through 10 where the source naturally yields a collection. Single-page
routes have no `count` parameter and return one page.

## Route groups and inputs

| Route group | Minimal inputs | Collection behavior |
| --- | --- | --- |
| Random | `count` | Random article candidates. |
| Most viewed: day | `day`, `count` | Articles for one UTC date. |
| Most viewed: month | `year`, `month`, `count` | Articles for one UTC month. |
| Most viewed: year | `year`, `count` | Aggregate completed months in that year. |
| Category name/index | `prefix`, `count` | Discover up to ten categories, then round-robin their article members. |
| Category members/subcategories | `category`, `count` | Direct member articles or articles from discovered subcategories. |
| Nearby | `latitude`, `longitude`, optional `radius_m`, `count` | Geosearch article candidates. |
| Featured | `day` | Today's featured article only. |
| On this day | `month`, `day`, optional event type, `count` | Article candidates from matching historical events. |
| Full-text/hydrated search | `query`, `count` | Search result article candidates. |
| Related | `title`, `count` | CirrusSearch `morelike:` candidates. |
| Prefix Action/Core REST | `prefix`, `count` | Title-prefix candidates from the respective API. |
| Page-card hydration | `title` | One text-only card and content record. |
| Content variants | `title` plus variant path | One page for intro, full text, parsed section, current HTML-derived text, or other properties. |

The route set corresponds to the tutorial examples: random, daily/monthly/yearly
views, four category examples, nearby, featured, on-this-day, both search
examples, related, two prefix examples, page-card hydration, and five content
variants.

## Category round-robin

For category-name and category-index routes, the service first discovers no
more than ten matching category titles. It loads a bounded member list for
each category, then takes one candidate from each category in discovered order,
repeating the cycle until `count` distinct articles are selected or all member
lists are exhausted. The response preserves selected-candidate order and
records each article's source category in `discovery`.

For example, `count=5` returns one article from each of the first five viable
categories. `count=10` takes one article from every viable category before a
second article from any category. A shortfall is explicit when there are fewer
than `count` distinct eligible articles.

## Error behavior

- Invalid query inputs return FastAPI validation errors.
- Unknown, missing, or non-article pages return `404`.
- Upstream `429`, `503`, `maxlag`, timeout, malformed response, and required
  hydration failures map to `502` or `503` with safe, non-upstream-specific
  messages.
- The service never returns an invalid common envelope or falls back to stored
  snapshots.

## Verification

Tests will use an injected/mock HTTP transport to assert the singleton-client
lifespan, User-Agent, rate coordinator, category selection order, input
constraints, and schema-valid response envelopes. A focused local smoke check
will validate the route OpenAPI document without calling Wikimedia.
